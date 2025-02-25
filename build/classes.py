import re
from pathlib import Path
from enum import Enum
from tempfile import mkdtemp
from typing import Annotated
from datetime import datetime
from pydantic import BaseModel, BeforeValidator, EmailStr, HttpUrl, Field

class Maintainer(BaseModel):
    name: str
    email: EmailStr

class Srctype(str, Enum):
    github = "github"
    template = "template"
    #file = "file"

class Targets(Enum):
    rpm = "rpm"
    #deb = "deb"

class Source(BaseModel):
    source: str # git repo release like api.github.com/repos/mikefarah/yq/releases/latest
    files_regex: Annotated[re.Pattern, BeforeValidator(re.compile)] # use named groups [arch, name] to match files by $arch and rename them to $name. example: ^(?P<name>yq)_linux_(?P<arch>\w+)$ matches a file named yq_linux_x86_64 and renames it to yq - if arch == x86_64
    type: Srctype
    arch: list[str]
    name: str
    arch_translation: dict[str, str] = Field(default={"x86_64": "x86_64"})
    extra: dict = Field(default={})

class Config(BaseModel):
    maintainers: list[Maintainer]
    targets: list[Targets]
    repobase: Path
    repo_url: HttpUrl

class Metadata(BaseModel):
    name: str = Field(default="Example package")
    summary: str = Field(default="Example summary")
    arch: str = Field(default="x86_64")
    version: str = Field(default="0.0.1")
    release: str = Field(default="0")
    url: HttpUrl = Field(default="https://example.com")
    group: str = Field(default="System")
    license: str = Field(default="unknown")
    packager: str = Field(default="Example Team")
    requires: list = Field(default=["bash"])
    created_at: datetime = Field(default_factory=datetime.now)
    buildroot: Path = Field(default=Path(mkdtemp()))
    description: str = Field(default="Example description")
    destination: str = Field(default="/usr/bin")
    changelog: list[dict[str, str]] = Field(default=[{"Thu Jun 17 2021 alex <alex@earthly.dev>": "initial example"}])