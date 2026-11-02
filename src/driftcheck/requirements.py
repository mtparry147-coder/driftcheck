"""Parsing requirement strings from ``pyproject.toml`` and requirements files.

Only the parts that matter for drift detection are kept: the normalised
project name, a canonicalised version specifier, and extras. Environment
markers are preserved in the raw text but ignored when comparing, because a
difference in markers alone is rarely drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_COMMENT_RE = re.compile(r"(?:^|\s)#.*$")
_NAME_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?\s*(?P<rest>.*)$"
)
#: Anything that is a direct reference rather than a registry requirement.
_URL_HINTS = ("://", "git+", "hg+", "svn+", "bzr+", "file:", "cvs+")

#: Lines starting with these are pip options, not requirements.
_OPTION_PREFIXES = ("-r", "--requirement", "-c", "--constraint", "-e", "--editable", "-f", "--find-links")


def normalize_name(name: str) -> str:
    """Normalise a distribution name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def canonical_specifier(specifier: str) -> str:
    """Sort specifier clauses so ``>=2,<3`` equals ``<3,>=2``."""
    clauses = [clause.strip() for clause in specifier.split(",") if clause.strip()]
    return ",".join(sorted(clauses))


@dataclass(frozen=True)
class Requirement:
    """One dependency declaration."""

    name: str
    specifier: str = ""
    extras: tuple[str, ...] = ()
    raw: str = ""
    line: int | None = None
    file: str | None = None

    @property
    def display(self) -> str:
        extras = f"[{','.join(self.extras)}]" if self.extras else ""
        return f"{self.name}{extras}{self.specifier}"

    @property
    def where(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        return self.file or ""


def parse_requirement(
    text: str,
    *,
    line: int | None = None,
    file: str | None = None,
) -> Requirement | None:
    """Parse a single requirement line.

    Returns ``None`` for blank lines, comments, pip options, and direct URLs,
    which are valid in requirements files but are not comparable constraints.
    """
    raw = text
    stripped = _COMMENT_RE.sub("", text).strip()
    if not stripped or stripped.startswith("#"):
        return None
    lowered = stripped.lower()
    if lowered.startswith(_OPTION_PREFIXES):
        return None
    if any(hint in lowered for hint in _URL_HINTS):
        return None

    match = _NAME_RE.match(stripped)
    if match is None:
        return None

    name = normalize_name(match.group("name"))
    if not name:
        return None

    extras_raw = match.group("extras") or ""
    extras = tuple(
        sorted(part.strip() for part in extras_raw.strip("[]").split(",") if part.strip())
    )

    rest = match.group("rest").strip()
    specifier = rest.split(";", 1)[0].strip()
    if specifier.startswith("(") and specifier.endswith(")"):
        specifier = specifier[1:-1].strip()
    if specifier.startswith("@"):
        # ``pkg @ https://...`` — a direct reference, not a version constraint.
        specifier = ""
    if specifier and specifier[0] not in "<>=!~*":
        # Not a requirement we understand; better to stay silent than to guess.
        return None

    return Requirement(
        name=name,
        specifier=canonical_specifier(specifier),
        extras=extras,
        raw=raw.strip(),
        line=line,
        file=file,
    )


def parse_requirements(text: str, *, file: str | None = None) -> list[Requirement]:
    """Parse the body of a requirements file, ignoring unsupported lines."""
    found: list[Requirement] = []
    for index, line in enumerate(text.splitlines(), start=1):
        requirement = parse_requirement(line, line=index, file=file)
        if requirement is not None:
            found.append(requirement)
    return found


def requirements_file(path: Path, root: Path) -> list[Requirement]:
    """Parse ``path``, following ``-r`` includes one level deep."""
    return _read_requirements(path, root, seen=set())


def _read_requirements(path: Path, root: Path, seen: set[Path]) -> list[Requirement]:
    resolved = path.resolve()
    if resolved in seen or not path.is_file():
        return []
    seen.add(resolved)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    relative = _relative(path, root)
    found: list[Requirement] = []
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        include = re.match(r"^(?:-r|--requirement)\s+(\S+)", stripped)
        if include is not None:
            found.extend(_read_requirements(path.parent / include.group(1), root, seen))
            continue
        requirement = parse_requirement(line, line=index, file=relative)
        if requirement is not None:
            found.append(requirement)
    return found


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def from_pep508_list(entries: list[str], *, file: str | None = "pyproject.toml") -> dict[str, Requirement]:
    """Parse a PEP 508 list from ``[project] dependencies``."""
    declared: dict[str, Requirement] = {}
    for entry in entries:
        requirement = parse_requirement(entry, file=file)
        if requirement is not None:
            declared.setdefault(requirement.name, requirement)
    return declared
