"""Finding which Python versions CI actually runs.

This deliberately avoids a YAML dependency: the goal is to read version
literals from the handful of places workflows declare them, not to validate
the workflow file.
"""

from __future__ import annotations

import re
from pathlib import Path

from .classifiers import Version

_VERSION_RE = re.compile(r"(?<![\d.])(\d+)\.(\d+)(?![\d.])")
_MATRIX_KEY_RE = re.compile(r"^(?P<indent>\s*)(?:python-version|python)\s*:\s*(?P<value>.*)$")
_TOX_RE = re.compile(r"\bpy(?P<major>\d)(?P<minor>\d+)\b")

_WORKFLOW_GLOBS = ("*.yml", "*.yaml")


def _versions_in(value: str) -> list[Version]:
    return [(int(major), int(minor)) for major, minor in _VERSION_RE.findall(value)]


def _matrix_versions(lines: list[str], start: int, indent: int) -> list[Version]:
    """Read a block list that follows ``python-version:`` on its own line."""
    versions: list[Version] = []
    for line in lines[start:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= indent:
            break
        if line.lstrip().startswith("-"):
            versions.extend(_versions_in(line))
    return versions


def _workflow_versions(path: Path) -> list[Version]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    versions: list[Version] = []
    for index, line in enumerate(lines):
        match = _MATRIX_KEY_RE.match(line)
        if match is None:
            continue
        value = match.group("value").strip()
        if value.startswith("#") or not value:
            versions.extend(_matrix_versions(lines, index + 1, len(match.group("indent"))))
            continue
        if value.startswith("["):
            versions.extend(_versions_in(value))
        elif value.startswith(("${{", '"${{', "'${{")):
            # Dynamic matrix built elsewhere; nothing reliable to compare.
            continue
        else:
            versions.extend(_versions_in(value))
    return versions


def _tox_versions(root: Path) -> list[Version]:
    path = root / "tox.ini"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    versions: set[Version] = set()
    for major, minor in _TOX_RE.findall(text):
        versions.add((int(major), int(minor)))
    return sorted(versions)


def ci_python_versions(root: Path) -> tuple[list[Version], str]:
    """Return the Python versions CI runs, plus a label describing where.

    The label is used in messages, so it stays stable and short (for example
    ``.github/workflows/ci.yml`` or ``tox.ini``). Versions from every workflow
    file and ``tox.ini`` are unioned, since a project may split its matrix.
    """
    versions: set[Version] = set()
    sources: list[str] = []

    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.is_dir():
        for pattern in _WORKFLOW_GLOBS:
            for path in sorted(workflows_dir.glob(pattern)):
                found = _workflow_versions(path)
                if found:
                    versions.update(found)
                    sources.append(f".github/workflows/{path.name}")

    tox = _tox_versions(root)
    if tox:
        versions.update(tox)
        sources.append("tox.ini")

    if not sources:
        return [], "CI"
    if len(sources) == 1:
        return sorted(versions), sources[0]
    return sorted(versions), "CI"
