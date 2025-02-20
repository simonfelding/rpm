import os, yaml, logging, platform
from pathlib import Path
from tempfile import mkdtemp
from rich.logging import RichHandler
from build.classes import *
from build.functions import *

logging.basicConfig(
    level=logging.DEBUG, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)

if __name__ == "__main__":
    config = Config(**yaml.safe_load(Path("config.yaml").read_text()))
    logging.info(f"Config: \n{config}")
    sources = [Source(**source) for source in yaml.safe_load(Path("sources.yaml").read_text())]
    logging.info(f"Sources: \n{sources}")

    for target in config.targets:
        packages = []
        for source in sources:
            logging.debug(f"platform.machine(): {platform.machine()}")
            for arch in source.arch:
                if arch not in ["noarch", platform.machine()]:
                    continue
                metadata = Metadata()
                metadata.packager = ", ".join([f"{maintainer.name} <{maintainer.email}>" for maintainer in config.maintainers])
                metadata.arch = arch if arch not in source.arch_translation else source.arch_translation[arch]
                files, metadata = get_source(source, metadata)
                logging.debug(f"Metadata: \n{metadata}")
                if files:
                    metadata.arch = arch
                    packages.append(build_package(target, files, config, metadata))

        repo = Path(config.repobase/target.value)
        repo.mkdir(exist_ok=True, parents=True)
        logging.debug(packages)
        os.system(f"mv {' '.join([str(package) for package in packages])} {repo}")
        filelist = Path(mkdtemp())/"filelist"
        filelist.write_text("\n".join([str(package.name) for package in packages]))
        assert generate_repo(target, repo, filelist) == 0, f"Failed to generate {target} repository"
        generate_index(filelist, repo)
        logging.info(f"== {target} repository generated at {repo}\n")
    
    files = [str(x) for x in config.repobase.rglob('*') if x.is_file()]
    if os.environ.get("DO_PUSH"):
        logging.info("== Pushing to git")
        if os.system(f"git add {" ".join(files)}"):
            os.system("git commit -m 'Update repo'")
            os.system("git push")
            logging.info(".. Done!")
        else:
            logging.info("== No files to push. Exiting.\n")
    else:
        logging.warning("== env variable 'DO_PUSH' not set, not pushing to git\n")
        logging.info(f"\nWould have pushed files:\n- {"\n- ".join(files)}\n")
