"""Reading ``pyproject.toml`` and locating the lines it declares things on.

``tomllib`` gives us values but not positions, so the helpers here re-scan the
raw text when a finding needs a ``file:line`` that points at the offending key.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_HEADER_RE = re.compile(r"^\s*\[\[?(?P<name>[^\]]+)\]\]?\s*$")


class ProjectError(Exception):
    """Raised when a project cannot be analysed at all."""


def load(path: Path) -> dict:
    """Load a TOML file, raising :class:`ProjectError` on malformed input."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        raise ProjectError(f"{path} does not exist") from None
    except tomllib.TOMLDecodeError as exc:
        raise ProjectError(f"{path} is not valid TOML: {exc}") from None
    except OSError as exc:
        raise ProjectError(f"cannot read {path}: {exc}") from None


def table(data: dict, *keys: str) -> dict:
    """Return a nested table, or an empty dict when the path is missing."""
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return current if isinstance(current, dict) else {}


def find_line(text: str, pattern: str) -> int | None:
    """1-based line number of the first ``pattern`` match, or ``None``."""
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        return None
    return text.count("\n", 0, match.start()) + 1


def find_key_in_section(text: str, section: str, key: str) -> int | None:
    """1-based line of ``key =`` inside ``[section]``.

    The scan stops at the next table header, so a key that only appears in a
    sibling table is not reported.
    """
    base: int | None = None
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index, line in enumerate(text.splitlines(), start=1):
        header = _HEADER_RE.match(line)
        if header is not None:
            if base is not None:
                return None
            if header.group("name").strip() == section:
                base = index
            continue
        if base is not None and pattern.match(line):
            return index
    return None


def find_value_line(text: str, value: str) -> int | None:
    """1-based line where a quoted ``value`` appears, for pointing at strings."""
    return find_line(text, re.escape(f'"{value}"'))
