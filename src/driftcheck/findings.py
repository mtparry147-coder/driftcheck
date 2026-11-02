"""Finding model, severities, and the check registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

ERROR = "error"
WARNING = "warning"

#: Human-readable description of every check family, used by ``--list-checks``.
CHECKS: dict[str, str] = {
    "version": "version numbers agree across every file that declares one",
    "dependencies": "declared dependencies match your requirements files",
    "python": "Python support claims match classifiers and CI",
    "entrypoints": "console entry points resolve to importable objects",
    "files": "files referenced by pyproject.toml exist",
}

#: Maps a finding code (``VER001``) to the check family that produced it.
CODE_PREFIXES: dict[str, str] = {
    "VER": "version",
    "DEP": "dependencies",
    "PY": "python",
    "ENT": "entrypoints",
    "FIL": "files",
}


def check_for(code: str) -> str:
    """Return the check family for a finding code (``PY001`` -> ``python``)."""
    prefix = code.rstrip("0123456789").upper()
    return CODE_PREFIXES.get(prefix, "other")


@dataclass(frozen=True)
class Finding:
    """A single problem found in a project.

    ``file`` is relative to the project root so that output stays stable between
    machines, and ``line`` is 1-based when known.
    """

    code: str
    severity: str
    message: str
    file: str | None = None
    line: int | None = None
    hint: str | None = None

    @property
    def check(self) -> str:
        return check_for(self.code)

    @property
    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.file or "", self.line or 0, self.code, self.message)

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "hint": self.hint,
            "check": self.check,
        }


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Sort findings by file, then line, then code."""
    return sorted(findings, key=lambda finding: finding.sort_key)


def count_severities(findings: Iterable[Finding]) -> tuple[int, int]:
    """Return ``(errors, warnings)``."""
    errors = warnings = 0
    for finding in findings:
        if finding.severity == ERROR:
            errors += 1
        else:
            warnings += 1
    return errors, warnings
