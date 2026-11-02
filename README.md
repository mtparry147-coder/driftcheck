# driftcheck

**Catch drift between your version numbers, dependency lists, and Python support claims — before CI or a release does.**

[![CI](https://github.com/mtparry147-coder/driftcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/mtparry147-coder/driftcheck/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

Every Python project ends up with the same information in more than one place:

- the version in `pyproject.toml`, and again in `__init__.py`, and again in the docs
- the dependencies in `pyproject.toml`, and again in `requirements.txt`
- the supported Python versions in a classifier, in `requires-python`, and in a CI matrix

Nothing forces those copies to agree. They drift one small commit at a time, and the failure shows up at the worst moment: a release tagged with the wrong version, a "works locally" bug from a constraint that only changed in one file, or a green CI matrix that quietly stopped testing a version you still claim to support.

`driftcheck` reads those files, compares them, and tells you exactly where they disagree — with a `file:line` you can click. It runs offline, has no dependencies, and takes about a second.

## What it catches

| Code | Severity | Meaning |
| --- | --- | --- |
| `VER001` | error | Version numbers disagree between files |
| `VER002` | warning | No version found anywhere |
| `VER003` | warning | `CHANGELOG.md` has no entry for the current version |
| `DEP001` | warning | Dependency declared in `pyproject.toml` but missing from a requirements file |
| `DEP002` | warning | Dependency in a requirements file but not declared in `pyproject.toml` |
| `DEP003` | error | Same dependency, different version specifier |
| `DEP004` | warning | `[tool.driftcheck]` maps a group to a requirements file that does not exist |
| `PY001` | error | Classifier claims a Python version below your `requires-python` floor |
| `PY002` | error | CI runs a Python version below your `requires-python` floor |
| `PY003` | warning | Classifier claims a Python version that CI never tests |
| `PY004` | warning | Classifiers claim Python versions but `requires-python` is missing |
| `ENT001` | error | `[project.scripts]` points at a module that does not exist |
| `ENT002` | error | Entry point points at an attribute that is not defined |
| `FIL001` | error | `readme` points at a file that does not exist |
| `FIL002` | warning | No readme declared |
| `FIL003` | error | `license.file` points at a file that does not exist |
| `FIL004` | warning | An SPDX licence is declared but there is no licence file |

## Demo

Run against [`examples/broken-project`](examples/broken-project), a deliberately inconsistent project in this repository:

```console
$ driftcheck examples/broken-project

driftcheck 0.1.0 - /home/you/driftcheck/examples/broken-project

version
  warning VER003  CHANGELOG.md  CHANGELOG.md has no entry for 0.2.0
      hint: add '## [0.2.0] - YYYY-MM-DD' so release notes are not skipped
  error   VER001  pyproject.toml:7  version numbers disagree: pyproject.toml:7 says 0.2.0, src/demo_pkg/__init__.py:3 says 0.2.1
      hint: keep one source of truth, or update every file before tagging a release

dependencies
  error   DEP003  requirements.txt:2  httpx has conflicting specifiers: pyproject.toml says '>=0.27', requirements.txt says '>=0.25'
      hint: let one file own the constraint; drift here is how 'works locally' happens
  warning DEP002  requirements.txt:3  tabulate is listed in requirements.txt but not declared in pyproject.toml
      hint: declare it under [project] dependencies, or remove it

python
  error   PY002  .github/workflows/ci.yml  CI tests Python 3.10, below the declared floor '>=3.11'
      hint: raise the matrix, or lower requires-python
  error   PY001  pyproject.toml:12  classifier claims Python 3.9 support, but requires-python is '>=3.11'
      hint: drop the classifier, or lower the floor

entrypoints
  error   ENT002  pyproject.toml:24  entry point 'demo' points at 'mian', which is not defined in cli.py
      hint: define the function, or fix the attribute name

5 errors, 2 warnings across 5 checks
```

Exit status is `1`, so this is a failing CI step without any extra configuration.

## Install

```console
pip install driftcheck
```

Requires Python 3.11 or newer. There are no runtime dependencies.

Try it without installing anything from PyPI:

```console
git clone https://github.com/mtparry147-coder/driftcheck
cd driftcheck
python -m driftcheck examples/broken-project
```

## Usage

```console
driftcheck                  # check the current directory
driftcheck path/to/project  # check somewhere else
driftcheck --strict         # treat warnings as failures
driftcheck --format json    # machine-readable output
driftcheck --list-checks    # show the check families
```

| Option | Description |
| --- | --- |
| `--format {text,json,github}` | `github` emits workflow commands, so findings appear inline on a pull request |
| `--select CODE` | Only report matching codes, prefixes (`VER`), or check names (`dependencies`) |
| `--ignore CODE` | Never report these; same matching rules as `--select` |
| `--strict` | Exit `1` when only warnings are found |
| `--no-color` | Disable ANSI colour (also respects [`NO_COLOR`](https://no-color.org/)) |

Exit codes: `0` clean, `1` problems, `2` the project could not be analysed.

### pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/mtparry147-coder/driftcheck
    rev: v0.1.0
    hooks:
      - id: driftcheck
```

### GitHub Actions

```yaml
- uses: mtparry147-coder/driftcheck@v0.1.0
  with:
    args: --strict
```

Or, if you already install your project in CI, skip the action and run `python -m driftcheck . --strict`.

## Configuration

Configuration lives in `pyproject.toml`, so there is no extra file to keep in sync:

```toml
[tool.driftcheck]
# Match by exact code ("VER001"), prefix ("VER"), or check name ("version").
ignore = ["PY003"]
strict = true

# Extra requirements files to compare optional dependency groups against.
# requirements-<group>.txt and requirements/<group>.txt are found automatically.
[tool.driftcheck.requirements]
docs = "docs/requirements.txt"
```

## Design principles

**Offline and dependency-free.** `driftcheck` parses files; it does not resolve dependency graphs or contact an index. That keeps it fast enough for a pre-commit hook and deterministic enough for CI, and it means installing it cannot break your environment. Only the standard library is used.

**No guessing.** When a file cannot be parsed, or a value comes from a dynamic mechanism the tool cannot follow (`__version__ = importlib.metadata.version(...)`, a `${{ }}` matrix expression, a `__getattr__` in a module), the check is skipped rather than reported. A linter that cries wolf gets removed from CI.

**Actionable output.** Every finding names the file, the line, the two values that disagree, and what to do about it. There is no "something is wrong somewhere" mode.

**One source of truth is a decision you make, not one the tool makes.** `driftcheck` never rewrites your files. It tells you where the copies disagree; which one wins is your call.

## Limits

Worth knowing before you adopt it:

- Dependency *specifiers* are compared, not resolved ranges. `>=2.0` and `>=2.1` conflict because the text differs, even where the ranges overlap.
- Poetry-style constraints (`^0.27`) are compared by name only, because caret syntax does not translate to a PEP 440 specifier without a resolver.
- CI detection reads version literals from `.github/workflows/*.yml` and `tox.ini`. Matrices generated at runtime are skipped.
- Only `[project.scripts]` and `[project.gui-scripts]` are resolved; arbitrary `[project.entry-points]` groups are not.
- There is no auto-fix. That is deliberate: a tool that silently rewrites your release metadata is a bigger risk than the drift it fixes.

## Roadmap

Ideas that fit the design, roughly in order:

- `[dependency-groups]` ([PEP 735](https://peps.python.org/pep-0735/)) compared against requirements files
- lock file awareness: confirm `uv.lock` / `poetry.lock` were produced by the current `pyproject.toml`
- SARIF output, so findings appear in code scanning as well as on the diff
- monorepo mode: check every `pyproject.toml` under a path

If you want one of these, open an issue and say what it would have caught.

## Development

```console
git clone https://github.com/mtparry147-coder/driftcheck
cd driftcheck
python -m pip install -e ".[dev]"

python -m unittest discover -s tests -v   # test suite, standard library only
python -m driftcheck . --strict           # the repository checks itself
```

The project holds itself to its own rules: CI runs `driftcheck . --strict`, and the test suite includes a test that the repository is clean.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a check.

## License

MIT — see [LICENSE](LICENSE).
