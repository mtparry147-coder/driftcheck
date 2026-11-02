"""The checks themselves, and the code that runs them."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import classifiers, entrypoints, requirements, versions, workflows
from .findings import ERROR, WARNING, Finding, sort_findings
from .pyproject import ProjectError, find_key_in_section, find_line, load, table


@dataclass
class Config:
    """``[tool.driftcheck]`` plus command-line overrides."""

    ignore: frozenset[str] = frozenset()
    select: frozenset[str] = frozenset()
    strict: bool = False
    requirements: dict[str, str] = field(default_factory=dict)


@dataclass
class Project:
    """Everything the checks need to know about one project."""

    root: Path
    data: dict
    text: str
    project: dict
    poetry: dict


def load_config(data: dict) -> Config:
    """Read ``[tool.driftcheck]`` from a parsed ``pyproject.toml``."""
    raw = table(data, "tool", "driftcheck")
    mapping: dict[str, str] = {}
    configured = raw.get("requirements")
    if isinstance(configured, dict):
        mapping = {
            str(group): str(path)
            for group, path in configured.items()
            if isinstance(path, str)
        }
    return Config(
        ignore=_entries(raw.get("ignore")),
        select=_entries(raw.get("select")),
        strict=bool(raw.get("strict", False)),
        requirements=mapping,
    )


def _entries(value: object) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(str(item) for item in value if isinstance(item, str))


def load_project(root: Path) -> Project:
    """Load ``root/pyproject.toml``."""
    path = root / "pyproject.toml"
    if not path.is_file():
        raise ProjectError(f"no pyproject.toml found in {root}")
    data = load(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectError(f"cannot read {path}: {exc}") from None
    return Project(
        root=root,
        data=data,
        text=text,
        project=table(data, "project"),
        poetry=table(data, "tool", "poetry"),
    )


def run(root: Path, config: Config | None = None) -> list[Finding]:
    """Run every check against ``root`` and return filtered findings."""
    return evaluate(load_project(root), config)


def evaluate(project: Project, config: Config | None = None) -> list[Finding]:
    """Run every check against an already-loaded project."""
    if config is None:
        config = load_config(project.data)

    findings: list[Finding] = []
    findings.extend(check_files(project))
    findings.extend(check_version(project))
    findings.extend(check_dependencies(project, config))
    findings.extend(check_python(project))
    findings.extend(check_entrypoints(project))
    return filter_findings(findings, config)


def filter_findings(findings: list[Finding], config: Config) -> list[Finding]:
    """Apply ``select``/``ignore`` and sort the result."""
    selected = list(config.select)
    ignored = list(config.ignore)

    kept: list[Finding] = []
    for finding in sort_findings(findings):
        if selected and not any(_matches(entry, finding) for entry in selected):
            continue
        if any(_matches(entry, finding) for entry in ignored):
            continue
        kept.append(finding)
    return kept


def _matches(entry: str, finding: Finding) -> bool:
    entry = entry.strip()
    if not entry:
        return False
    upper = entry.upper()
    if upper == finding.code.upper():
        return True
    if upper.isalpha() and finding.code.upper().startswith(upper):
        return True
    return entry.lower() == finding.check


# --------------------------------------------------------------------------
# files
# --------------------------------------------------------------------------


def check_files(project: Project) -> list[Finding]:
    """Check that files referenced by pyproject.toml exist."""
    findings: list[Finding] = []

    readme = project.project.get("readme")
    declared: str | None = None
    if isinstance(readme, str):
        declared = readme
    elif isinstance(readme, dict) and isinstance(readme.get("file"), str):
        declared = readme["file"]

    if declared is None:
        findings.append(
            Finding(
                "FIL002",
                WARNING,
                "pyproject.toml does not declare a readme",
                "pyproject.toml",
                find_line(project.text, r"^\[project\]"),
                hint="add readme = \"README.md\" so PyPI shows your documentation",
            )
        )
    elif not (project.root / declared).is_file():
        findings.append(
            Finding(
                "FIL001",
                ERROR,
                f"readme is set to '{declared}', but that file does not exist",
                "pyproject.toml",
                find_key_in_section(project.text, "project", "readme"),
                hint="update the readme field, or add the missing file",
            )
        )

    license_value = project.project.get("license")
    license_file: str | None = None
    if isinstance(license_value, dict) and isinstance(license_value.get("file"), str):
        license_file = license_value["file"]
    if license_file is not None:
        if not (project.root / license_file).is_file():
            findings.append(
                Finding(
                    "FIL003",
                    ERROR,
                    f"license.file points at '{license_file}', which does not exist",
                    "pyproject.toml",
                    find_key_in_section(project.text, "project", "license"),
                    hint="add the licence text, or use an SPDX string such as license = \"MIT\"",
                )
            )
    elif isinstance(license_value, str) and not _has_license_file(project.root):
        findings.append(
            Finding(
                "FIL004",
                WARNING,
                f"license is '{license_value}', but no LICENSE file was found",
                "pyproject.toml",
                find_key_in_section(project.text, "project", "license"),
                hint="add a LICENSE file; it is what most consumers actually check",
            )
        )
    return findings


def _has_license_file(root: Path) -> bool:
    return any(
        (root / name).is_file()
        for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md")
    )


# --------------------------------------------------------------------------
# version
# --------------------------------------------------------------------------


def check_version(project: Project) -> list[Finding]:
    """Check that every declared version agrees with the others."""
    sources = versions.collect(project.root, project.project, project.poetry, project.text)
    if not sources:
        return [
            Finding(
                "VER002",
                WARNING,
                "no version number found in pyproject.toml, the package, or metadata files",
                "pyproject.toml",
                None,
                hint="declare version = \"0.1.0\" under [project]",
            )
        ]

    distinct = {versions.normalize(source.value) for source in sources}
    findings: list[Finding] = []
    if len(distinct) > 1:
        detail = ", ".join(f"{source.where} says {source.value}" for source in sources)
        findings.append(
            Finding(
                "VER001",
                ERROR,
                f"version numbers disagree: {detail}",
                sources[0].file,
                sources[0].line,
                hint="keep one source of truth, or update every file before tagging a release",
            )
        )

    findings.extend(_check_changelog(project, sources[0].value))
    return findings


_RELEASE_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?(?:[.\-+].*)?$")


def _check_changelog(project: Project, version: str) -> list[Finding]:
    changelog = project.root / "CHANGELOG.md"
    if not changelog.is_file():
        return []
    try:
        text = changelog.read_text(encoding="utf-8")
    except OSError:
        return []

    normalized = versions.normalize(version)
    if not _RELEASE_RE.match(normalized):
        return []
    if re.search(rf"^##\s*\[?v?{re.escape(normalized)}\]?", text, re.MULTILINE | re.IGNORECASE):
        return []
    return [
        Finding(
            "VER003",
            WARNING,
            f"CHANGELOG.md has no entry for {normalized}",
            "CHANGELOG.md",
            None,
            hint=f"add '## [{normalized}] - YYYY-MM-DD' so release notes are not skipped",
        )
    ]


# --------------------------------------------------------------------------
# dependencies
# --------------------------------------------------------------------------


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if isinstance(item, str)}


def _poetry_requirements(table_data: dict) -> dict[str, requirements.Requirement]:
    """Poetry constraints use caret/tilde syntax, so only names are compared."""
    declared: dict[str, requirements.Requirement] = {}
    for name, constraint in table_data.items():
        if not isinstance(name, str) or name.lower() == "python":
            continue
        if isinstance(constraint, dict):
            # Git, path, or url dependencies are not registry constraints.
            if any(key in constraint for key in ("git", "path", "url", "file")):
                continue
        declared.setdefault(
            requirements.normalize_name(name),
            requirements.Requirement(
                name=requirements.normalize_name(name),
                raw=name,
                file="pyproject.toml",
            ),
        )
    return declared


def _declared(project: Project) -> tuple[dict[str, requirements.Requirement], bool]:
    """Return declared core dependencies and whether specifiers are comparable."""
    core = requirements.from_pep508_list(_string_list(project.project.get("dependencies")))
    if core:
        return core, True
    poetry = _poetry_requirements(table(project.poetry, "dependencies"))
    if poetry:
        return poetry, False
    return {}, True


def _optional_groups(project: Project) -> dict[str, dict[str, requirements.Requirement]]:
    groups: dict[str, dict[str, requirements.Requirement]] = {}
    for group, entries in table(project.data, "project", "optional-dependencies").items():
        groups[str(group)] = requirements.from_pep508_list(_string_list(entries))

    poetry_groups = table(project.poetry, "group")
    for group, payload in poetry_groups.items():
        deps = _poetry_requirements(table(payload, "dependencies"))
        if deps:
            groups[f"poetry:{group}"] = deps
    legacy_dev = _poetry_requirements(table(project.poetry, "dev-dependencies"))
    if legacy_dev:
        groups.setdefault("dev", legacy_dev)
    return groups


def _default_requirements_file(root: Path, group: str) -> str | None:
    for candidate in (f"requirements-{group}.txt", f"requirements/{group}.txt"):
        if (root / candidate).is_file():
            return candidate
    return None


def check_dependencies(project: Project, config: Config) -> list[Finding]:
    """Check that declared dependencies and requirements files agree."""
    core, compare_specifiers = _declared(project)
    optional = _optional_groups(project)
    if not core and not optional:
        return []

    findings: list[Finding] = []

    core_file = project.root / "requirements.txt"
    if core and core_file.is_file():
        findings.extend(
            _compare(
                core,
                requirements.requirements_file(core_file, project.root),
                "requirements.txt",
                compare_specifiers=compare_specifiers,
            )
        )

    for group, declared in optional.items():
        configured = config.requirements.get(group)
        relative = configured or _default_requirements_file(project.root, group)
        if relative is None:
            continue
        path = project.root / relative
        if not path.is_file():
            findings.append(
                Finding(
                    "DEP004",
                    WARNING,
                    f"[tool.driftcheck] maps group '{group}' to '{relative}', which does not exist",
                    "pyproject.toml",
                    None,
                    hint="fix the path, or remove the mapping",
                )
            )
            continue
        findings.extend(
            _compare(
                declared,
                requirements.requirements_file(path, project.root),
                relative,
                compare_specifiers=compare_specifiers,
            )
        )
    return findings


def _compare(
    declared: dict[str, requirements.Requirement],
    listed: list[requirements.Requirement],
    file_label: str,
    *,
    compare_specifiers: bool,
) -> list[Finding]:
    if not listed:
        return []

    listed_by_name = {requirement.name: requirement for requirement in listed}
    findings: list[Finding] = []

    for name, requirement in declared.items():
        if name not in listed_by_name:
            findings.append(
                Finding(
                    "DEP001",
                    WARNING,
                    f"{name} is declared in pyproject.toml but missing from {file_label}",
                    file_label,
                    None,
                    hint="add it to the requirements file, or drop the file if pyproject.toml is the only source",
                )
            )
            continue

        if not compare_specifiers:
            continue
        other = listed_by_name[name]
        if requirement.specifier and other.specifier and requirement.specifier != other.specifier:
            findings.append(
                Finding(
                    "DEP003",
                    ERROR,
                    f"{name} has conflicting specifiers: pyproject.toml says '{requirement.specifier}', "
                    f"{file_label} says '{other.specifier}'",
                    other.file,
                    other.line,
                    hint="let one file own the constraint; drift here is how 'works locally' happens",
                )
            )

    for name, requirement in listed_by_name.items():
        if name not in declared:
            findings.append(
                Finding(
                    "DEP002",
                    WARNING,
                    f"{name} is listed in {file_label} but not declared in pyproject.toml",
                    requirement.file,
                    requirement.line,
                    hint="declare it under [project] dependencies, or remove it",
                )
            )
    return findings


# --------------------------------------------------------------------------
# python support
# --------------------------------------------------------------------------


def check_python(project: Project) -> list[Finding]:
    """Check that classifiers, ``requires-python``, and CI agree."""
    requires = project.project.get("requires-python")
    requires = requires if isinstance(requires, str) else ""
    claimed = classifiers.python_versions(_string_list(project.project.get("classifiers")))
    tested, ci_label = workflows.ci_python_versions(project.root)
    minimum = classifiers.parse_requires_python(requires)

    findings: list[Finding] = []

    if minimum is not None:
        for version in claimed:
            if version < minimum:
                findings.append(
                    Finding(
                        "PY001",
                        ERROR,
                        f"classifier claims Python {classifiers.format_version(version)} support, "
                        f"but requires-python is '{requires}'",
                        "pyproject.toml",
                        _classifier_line(project, version),
                        hint="drop the classifier, or lower the floor",
                    )
                )
        for version in tested:
            if version < minimum:
                findings.append(
                    Finding(
                        "PY002",
                        ERROR,
                        f"CI tests Python {classifiers.format_version(version)}, "
                        f"below the declared floor '{requires}'",
                        ci_label if ci_label != "CI" else None,
                        None,
                        hint="raise the matrix, or lower requires-python",
                    )
                )

    if claimed and minimum is not None and tested:
        expected = {version for version in claimed if version >= minimum}
        for version in sorted(expected - set(tested)):
            findings.append(
                Finding(
                    "PY003",
                    WARNING,
                    f"claims support for Python {classifiers.format_version(version)}, "
                    f"but {ci_label} never tests it",
                    "pyproject.toml",
                    _classifier_line(project, version),
                    hint="add it to the CI matrix, or drop the classifier",
                )
            )

    if claimed and minimum is None:
        findings.append(
            Finding(
                "PY004",
                WARNING,
                "classifiers claim Python versions, but requires-python is missing",
                "pyproject.toml",
                find_line(project.text, r"^\[project\]"),
                hint="add requires-python so installers know the floor",
            )
        )
    return findings


def _classifier_line(project: Project, version: tuple[int, int]) -> int | None:
    classifier = f"Programming Language :: Python :: {classifiers.format_version(version)}"
    return find_line(project.text, re.escape(f'"{classifier}"'))


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------


def check_entrypoints(project: Project) -> list[Finding]:
    """Check that ``[project.scripts]`` resolve to real modules and attributes."""
    scripts: dict[str, str] = {}
    for key in ("scripts", "gui-scripts"):
        scripts.update(_string_dict(project.project.get(key)))
    if not scripts:
        return []
    return entrypoints.check(project.root, scripts, project.text)
