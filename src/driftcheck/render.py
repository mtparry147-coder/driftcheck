"""Rendering findings as text, JSON, or GitHub Actions annotations."""

from __future__ import annotations

import json
from pathlib import Path

from .findings import CHECKS, ERROR, Finding, count_severities

_COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "green": "\033[32m",
}


def _paint(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_COLORS[color]}{text}{_COLORS['reset']}"


def render_text(findings: list[Finding], root: Path, version: str, *, color: bool = False) -> str:
    """Human-readable report grouped by check."""
    lines = [
        _paint(f"driftcheck {version}", "bold", color)
        + _paint(f" - {root}", "dim", color),
        "",
    ]

    if not findings:
        lines.append(f"  no drift found across {len(CHECKS)} checks")
        return "\n".join(lines)

    by_check: dict[str, list[Finding]] = {}
    for finding in findings:
        by_check.setdefault(finding.check, []).append(finding)

    ordered = [check for check in CHECKS if check in by_check]
    ordered.extend(sorted(check for check in by_check if check not in CHECKS))

    for check in ordered:
        group = by_check[check]
        lines.append(_paint(check, "bold", color))
        for finding in group:
            label = "error" if finding.severity == ERROR else "warning"
            tint = "red" if finding.severity == ERROR else "yellow"
            location = _location(finding)
            lines.append(
                f"  {_paint(f'{label:<7}', tint, color)} {finding.code}  "
                f"{_paint(location, 'dim', color)}  {finding.message}"
            )
            if finding.hint:
                lines.append(f"      {_paint('hint:', 'dim', color)} {finding.hint}")
        lines.append("")

    errors, warnings = count_severities(findings)
    summary = _summary(errors, warnings)
    lines.append(_paint(summary, "red" if errors else "yellow", color))
    return "\n".join(lines)


def _location(finding: Finding) -> str:
    if finding.file and finding.line:
        return f"{finding.file}:{finding.line}"
    if finding.file:
        return finding.file
    return ""


def _summary(errors: int, warnings: int) -> str:
    parts = []
    if errors:
        parts.append(f"{errors} error{'s' if errors != 1 else ''}")
    if warnings:
        parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
    return f"{', '.join(parts)} across {len(CHECKS)} checks"


def render_json(findings: list[Finding], root: Path, version: str, *, strict: bool = False) -> str:
    """Machine-readable report, stable enough to diff in CI."""
    errors, warnings = count_severities(findings)
    payload = {
        "tool": "driftcheck",
        "version": version,
        "root": str(root),
        "strict": strict,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "findings": len(findings),
            "checks": list(CHECKS),
        },
        "findings": [finding.as_dict() for finding in findings],
    }
    return json.dumps(payload, indent=2, sort_keys=False)


def render_github(findings: list[Finding]) -> str:
    """GitHub Actions workflow commands, so findings appear inline on a PR."""
    lines: list[str] = []
    for finding in findings:
        level = "error" if finding.severity == ERROR else "warning"
        properties = []
        if finding.file:
            properties.append(f"file={_escape_property(finding.file)}")
        if finding.line:
            properties.append(f"line={finding.line}")
        properties.append(f"title={finding.code}")
        message = _escape_data(f"{finding.message}" + (f" Hint: {finding.hint}" if finding.hint else ""))
        lines.append(f"::{level} {','.join(properties)}::{message}")
    return "\n".join(lines)


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")
