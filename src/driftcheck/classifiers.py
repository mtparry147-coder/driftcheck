"""Interpreting Python version claims: classifiers, ``requires-python``, CI."""

from __future__ import annotations

import re

_CLASSIFIER_RE = re.compile(r"^Programming Language :: Python :: (?P<major>\d+)\.(?P<minor>\d+)$")
_REQUIRES_RE = re.compile(r"^(?P<op>>=|~=|==|>|<=|<)\s*(?P<major>\d+)(?:\.(?P<minor>\d+))?$")

Version = tuple[int, int]


def format_version(version: Version) -> str:
    """``(3, 11)`` -> ``"3.11"``."""
    return f"{version[0]}.{version[1]}"


def python_versions(classifiers: list[str]) -> list[Version]:
    """Extract the Python versions a project claims support for."""
    versions: set[Version] = set()
    for classifier in classifiers:
        match = _CLASSIFIER_RE.match(classifier.strip())
        if match is not None:
            versions.add((int(match.group("major")), int(match.group("minor"))))
    return sorted(versions)


def parse_requires_python(specifier: str) -> Version | None:
    """Return the minimum Python version implied by ``requires-python``.

    ``>=3.11`` and ``~=3.11`` both mean 3.11; ``>3.10`` means 3.11; ``<4``
    alone says nothing about the floor, so it is ignored.
    """
    if not specifier:
        return None
    floors: list[Version] = []
    for clause in specifier.split(","):
        match = _REQUIRES_RE.match(clause.strip())
        if match is None:
            continue
        operator = match.group("op")
        major = int(match.group("major"))
        minor = int(match.group("minor") or 0)
        if operator in {">=", "~=", "=="}:
            floors.append((major, minor))
        elif operator == ">":
            floors.append((major, minor + 1))
    return min(floors) if floors else None
