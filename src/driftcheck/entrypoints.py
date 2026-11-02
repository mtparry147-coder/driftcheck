"""Resolving ``[project.scripts]`` entry points against the source tree."""

from __future__ import annotations

import ast
from pathlib import Path

from .findings import ERROR, Finding
from .pyproject import find_value_line


def _module_path(root: Path, module: str) -> Path | None:
    parts = module.split(".")
    for base in (root / "src", root):
        candidate = base.joinpath(*parts)
        if candidate.with_suffix(".py").is_file():
            return candidate.with_suffix(".py")
        if (candidate / "__init__.py").is_file():
            return candidate / "__init__.py"
    return None


def _top_level_names(path: Path) -> set[str] | None:
    """Names defined at module level, or ``None`` when the file will not parse."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None

    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    if "__getattr__" in names:
        # Dynamic module attributes cannot be verified statically.
        return None
    return names


def check(root: Path, scripts: dict[str, str], pyproject_text: str) -> list[Finding]:
    """Verify that every console script points at something importable."""
    findings: list[Finding] = []
    for name, value in sorted(scripts.items()):
        line = find_value_line(pyproject_text, value)
        if not isinstance(value, str) or ":" not in value:
            findings.append(
                Finding(
                    "ENT001",
                    ERROR,
                    f"entry point '{name}' must use the form 'module:attribute', got '{value}'",
                    "pyproject.toml",
                    line,
                    hint="for example: driftcheck = \"driftcheck.cli:main\"",
                )
            )
            continue

        module, _, attribute = value.partition(":")
        module_path = _module_path(root, module)
        if module_path is None:
            findings.append(
                Finding(
                    "ENT001",
                    ERROR,
                    f"entry point '{name}' points at module '{module}', which does not exist",
                    "pyproject.toml",
                    line,
                    hint="check the module path, and that the package is under src/ or the project root",
                )
            )
            continue

        names = _top_level_names(module_path)
        if names is None:
            continue

        first = attribute.split(".")[0]
        if first and first not in names:
            findings.append(
                Finding(
                    "ENT002",
                    ERROR,
                    f"entry point '{name}' points at '{attribute}', which is not defined in {module_path.name}",
                    "pyproject.toml",
                    line,
                    hint="define the function, or fix the attribute name",
                )
            )
    return findings
