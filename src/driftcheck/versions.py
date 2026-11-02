"""Collecting every version number a project declares."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .pyproject import find_key_in_section, find_line

_INIT_RE = re.compile(r"^__version__\s*=\s*[\"'](?P<value>[^\"']+)[\"']", re.MULTILINE)
_DYNAMIC_RE = re.compile(r"importlib\.metadata|importlib_metadata")
_CONF_RE = re.compile(r"^(?:release|version)\s*=\s*[\"'](?P<value>[^\"']+)[\"']", re.MULTILINE)
_CITATION_RE = re.compile(r"^version\s*:\s*[\"']?(?P<value>[^\"'\s#]+)", re.MULTILINE)
_SETUP_CFG_RE = re.compile(r"^version\s*=\s*(?P<value>\S+)", re.MULTILINE)


@dataclass(frozen=True)
class VersionSource:
    """One place a project states its version."""

    label: str
    file: str
    line: int | None
    value: str

    @property
    def where(self) -> str:
        if self.line:
            return f"{self.file}:{self.line}"
        return self.file


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def package_init(root: Path, name: str | None) -> Path | None:
    """Find the package ``__init__.py`` for ``name`` in src or flat layout."""
    if not name:
        return None
    candidates = {name, name.replace("-", "_"), name.replace("_", "-").replace("-", "_")}
    for base in ("src", ""):
        for candidate in candidates:
            path = root / base / candidate / "__init__.py" if base else root / candidate / "__init__.py"
            if path.is_file():
                return path
    return None


def _from_init(path: Path, root: Path) -> VersionSource | None:
    text = _read(path)
    if text is None:
        return None
    if _DYNAMIC_RE.search(text):
        return None
    match = _INIT_RE.search(text)
    if match is None:
        return None
    return VersionSource(
        label=f"__version__ in {path.name}",
        file=_relative(path, root),
        line=text.count("\n", 0, match.start()) + 1,
        value=match.group("value"),
    )


def collect(
    root: Path,
    project: dict,
    poetry: dict,
    pyproject_text: str,
) -> list[VersionSource]:
    """Return every version declaration found, de-duplicated by location."""
    sources: list[VersionSource] = []
    name = project.get("name") if isinstance(project.get("name"), str) else None

    version = project.get("version")
    if isinstance(version, str) and version:
        sources.append(
            VersionSource(
                label="project.version",
                file="pyproject.toml",
                line=find_key_in_section(pyproject_text, "project", "version"),
                value=version,
            )
        )

    poetry_version = poetry.get("version")
    if isinstance(poetry_version, str) and poetry_version:
        sources.append(
            VersionSource(
                label="tool.poetry.version",
                file="pyproject.toml",
                line=find_key_in_section(pyproject_text, "tool.poetry", "version"),
                value=poetry_version,
            )
        )

    init_path = package_init(root, name)
    if init_path is not None:
        from_init = _from_init(init_path, root)
        if from_init is not None:
            sources.append(from_init)

    citation = root / "CITATION.cff"
    if citation.is_file():
        text = _read(citation) or ""
        match = _CITATION_RE.search(text)
        if match is not None:
            sources.append(
                VersionSource(
                    label="CITATION.cff",
                    file="CITATION.cff",
                    line=text.count("\n", 0, match.start()) + 1,
                    value=match.group("value"),
                )
            )

    conf = root / "docs" / "conf.py"
    if conf.is_file():
        text = _read(conf) or ""
        match = _CONF_RE.search(text)
        if match is not None:
            sources.append(
                VersionSource(
                    label="docs/conf.py",
                    file="docs/conf.py",
                    line=text.count("\n", 0, match.start()) + 1,
                    value=match.group("value"),
                )
            )

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(_read(package_json) or "{}")
        except ValueError:
            data = {}
        value = data.get("version")
        if isinstance(value, str) and value:
            sources.append(
                VersionSource(
                    label="package.json",
                    file="package.json",
                    line=find_line(_read(package_json) or "", r'"version"\s*:'),
                    value=value,
                )
            )

    setup_cfg = root / "setup.cfg"
    if setup_cfg.is_file():
        text = _read(setup_cfg) or ""
        section = _setup_cfg_version(text)
        if section is not None:
            sources.append(
                VersionSource(
                    label="setup.cfg",
                    file="setup.cfg",
                    line=section[0],
                    value=section[1],
                )
            )

    seen: set[tuple[str, int | None, str]] = set()
    unique: list[VersionSource] = []
    for source in sources:
        key = (source.file, source.line, source.value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def _setup_cfg_version(text: str) -> tuple[int, str] | None:
    in_metadata = False
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("["):
            in_metadata = stripped.strip("[]").strip() == "metadata"
            continue
        if in_metadata:
            match = _SETUP_CFG_RE.match(stripped)
            if match is not None:
                return index, match.group("value")
    return None


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize(value: str) -> str:
    """Normalise a version string for comparison (``v1.2.3`` == ``1.2.3``)."""
    cleaned = value.strip().strip("\"'").strip()
    if cleaned[:1] in {"v", "V"} and cleaned[1:2].isdigit():
        cleaned = cleaned[1:]
    return cleaned
