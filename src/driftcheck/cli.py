"""Command-line interface for driftcheck."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .checks import Config, ProjectError, evaluate, load_config, load_project
from .findings import CHECKS, ERROR
from .render import render_github, render_json, render_text

_DESCRIPTION = (
    "Check that a project's version numbers, dependency declarations, Python "
    "support claims, and entry points agree with each other."
)

_EPILOG = """exit codes:
  0  no problems found
  1  problems found (or warnings, with --strict)
  2  the project could not be analysed

examples:
  driftcheck
  driftcheck path/to/project --strict
  driftcheck --format json | jq '.findings[].code'
  driftcheck --ignore PY003
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driftcheck",
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="project directory containing pyproject.toml (default: .)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "github"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit with status 1 when only warnings are found",
    )
    parser.add_argument(
        "--select",
        action="append",
        default=[],
        metavar="CODE",
        help="only report these codes, prefixes, or check names (repeatable)",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="CODE",
        help="never report these codes, prefixes, or check names (repeatable)",
    )
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colour")
    parser.add_argument(
        "--list-checks", action="store_true", help="list the checks and exit"
    )
    parser.add_argument("--version", action="version", version=f"driftcheck {__version__}")
    return parser


def _split(values: list[str]) -> list[str]:
    entries: list[str] = []
    for value in values:
        entries.extend(part.strip() for part in value.split(",") if part.strip())
    return entries


def _wants_color(args: argparse.Namespace) -> bool:
    if args.no_color or args.format != "text":
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_checks:
        for name, description in CHECKS.items():
            print(f"  {name:<13} {description}")
        return 0

    root = Path(args.path).expanduser()
    if not root.is_dir():
        print(f"driftcheck: {root} is not a directory", file=sys.stderr)
        return 2

    try:
        project = load_project(root)
        config = load_config(project.data)
    except ProjectError as exc:
        print(f"driftcheck: {exc}", file=sys.stderr)
        return 2

    select = _split(args.select)
    ignore = _split(args.ignore)
    config = Config(
        ignore=config.ignore | frozenset(ignore),
        select=frozenset(select) if select else config.select,
        strict=config.strict or args.strict,
        requirements=config.requirements,
    )

    findings = evaluate(project, config)

    if args.format == "json":
        print(render_json(findings, root.resolve(), __version__, strict=config.strict))
    elif args.format == "github":
        report = render_github(findings)
        if report:
            print(report)
    else:
        print(render_text(findings, root.resolve(), __version__, color=_wants_color(args)))

    errors = sum(1 for finding in findings if finding.severity == ERROR)
    warnings = sum(1 for finding in findings if finding.severity != ERROR)
    if errors or (warnings and config.strict):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
