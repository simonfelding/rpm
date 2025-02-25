import os, yaml, requests, requests_cache, re, logging, jinja2, dateutil.parser
from tempfile import mkdtemp
from .classes import *
from pathlib import Path

requests_cache.install_cache(backend="sqlite", expire_after=43200)

def get(url) -> requests.models.Response:
    r = requests.get(url)
    r.raise_for_status()
    return r

def get_source(source: Source, metadata: Metadata) -> set[set[Path], Metadata]:
    workdir = Path(mkdtemp())
    output = []

    def template(source: Source) -> list[Path]:
        logging.debug(f".. Using template for {source.name}")
        logging.debug(source)
        #assert source.files_regex.match(source.source)
        file = Path(source.source)
        metadata.name       = source.name
        metadata.summary    = source.extra['summary']
        metadata.version    = source.extra['version']
        metadata.url        = source.extra['url']
        
        assert file.exists(), f".. {file.absolute()} does not exist"
        with open(workdir/metadata.name, "w") as f:
            jinja = jinja2.Environment()
            j2 = jinja.from_string(file.read_text())
            f.write(j2.render(metadata=metadata))
            output.append(Path(f.name))

    def github(source: Source) -> list[Path]:
        release = get(f"https://api.github.com/repos/{source.source}/releases/latest").json()
        logging.debug(f".. got release {release['tag_name']}\n.. with assets {[asset['name'] for asset in release['assets']]}")
        
        metadata.name = source.name
        metadata.summary = release["name"]
        metadata.version = re.sub(r"^v(\d)", r"\1" , release["tag_name"], count=1) # if version starts with v and a number, remove the v.
        if "-" in release["tag_name"]:
            metadata.release = release["tag_name"].split("-")[1]
        metadata.url = f"https://github.com/{source.source}"
        metadata.description = release["body"]
        metadata.changelog = [{"none": "empty"}]
        metadata.created_at = dateutil.parser.parse(release["created_at"])

        if Path(metadata.release) not in Path("repo/").glob(metadata.name):
            for asset in release["assets"]:
                if source.files_regex.match(asset["name"]):
                    if source.files_regex.match(asset["name"])['arch'] == metadata.arch:
                        file = Path(workdir/metadata.name)
                        logging.info(f"Downloading {asset['name']} for arch {metadata.arch} to {file}")
                        with open(file, "wb") as f:
                            f.write(get(asset["url"]).content)
                            output.append(Path(f.name))
                    else:
                        logging.debug(f".. Skipping {asset['name']} because it's not for {metadata.arch}")
        else:
            logging.debug(f".. {source.name} is up to date")
    
    logging.debug(f"SOURCE: {source}")
    logging.info(f"Getting source files for {source.name}")
    if source.type == Srctype.github:
        github(source)
    if source.type == Srctype.template:
        template(source)
    
    logging.debug(f".. Got {len(output)} files: {output}")
    return (set(output), metadata)

def build_package(target: Targets, files: set[Path], config: Config, metadata: Metadata, workdir = Path(mkdtemp())) -> Path:

    def rpm() -> Path:
        logging.info(f".. Building .rpm")
        jinja = jinja2.Environment()
        template = jinja.from_string(Path("rpm_spec.j2").read_text())
        specfile = Path(workdir/f"{metadata.name}.spec")
        with open(specfile, "w") as f:
            spec = template.render(files=[str(file.absolute()) for file in files], config=config, metadata=metadata)
            f.write(spec)
            logging.debug(f".. Wrote specfile \n{spec}\n")
        
        assert os.system(f"rpmbuild --define '_topdir {workdir.absolute()}' --target {metadata.arch} -bb {specfile}") == 0, f"rpmbuild failed for {metadata.name}"
        rpm = Path(f"{workdir.absolute()}/RPMS/{metadata.arch}/{metadata.name}-{metadata.version}-{metadata.release}.{metadata.arch}.rpm")
        assert rpm.exists(), f"{metadata.name} did not build to the right path"
        logging.debug(f".. Built {rpm} size {rpm.stat().st_size} bytes")
        return rpm

    try:
        logging.debug(metadata.created_at)
        os.environ.update({"SOURCE_DATE_EPOCH": str(int(metadata.created_at.timestamp()))})
        for file in files:
            file.chmod(644)
        if target == Targets.rpm:
            return rpm()
        if target == Targets.template:
            return template()
    except Exception as e:
        logging.error(f".. {e}")
    finally:
        os.environ.pop("SOURCE_DATE_EPOCH")

def generate_repo(target: Targets, repobase: Path, filelist: Path) -> int:
    def rpm(repo: Path) -> Path:
        logging.debug(f".. repo: {repo}")
        return os.system(f"createrepo -i {str(filelist.absolute())} --update {repo} --skip-stat")
    
    if target == Targets.rpm:
        logging.info(f".. Generating repo for {target} in {repobase}")
        logging.debug(f".. Filelist: {filelist}\n.. Content:\n{filelist.read_text()}\n")
        return rpm(repobase.absolute())

def generate_index(filelist: Path, repo: Path) -> Path:
    logging.info(f".. Generating index.html")
    jinja = jinja2.Environment()
    template = jinja.from_string(Path("file_index.j2").read_text())
    index = Path(repo/"index.html")
    with open(index, "w") as f:
        f.write(template.render(files=filelist.read_text().splitlines()))
        logging.debug(f".. Wrote index.html\n{index.read_text()}\n")
    return index

def generate_setup_instructions(files: list, root: Path, repo_url: str) -> Path:
    setup = Path(root/"index.html")
    logging.debug(f".. Generating setup instructions")
    jinja = jinja2.Environment()
    template = jinja.from_string(Path("setup_instructions.j2").read_text())
    rpm_repofile = [file for file in files if re.match(r"^the.repo.*\.rpm$", file)][0]
    assert Path(rpm_repofile).exists(), f"The repofile from the filelist does not exist: {rpm_repofile}"
    with open(setup, "w") as f:
        f.write(template.render(rpm_repofile=rpm_repofile, repo_url=repo_url))
        logging.info(f".. Wrote {setup}\n")
    return setup