# Contributing to driftcheck

Thanks for helping. This project is small on purpose: one CLI, one pass over a
project's files, no network, no dependencies. Changes that keep it that way are
the easiest to review.

## Getting set up

```console
git clone https://github.com/mtparry147-coder/driftcheck
cd driftcheck
python -m pip install -e ".[dev]"
```

Python 3.11 or newer. The test suite uses `unittest` from the standard library,
so you can run it without installing anything:

```console
python -m unittest discover -s tests -v
```

Run the tool against itself before opening a pull request:

```console
python -m driftcheck . --strict
```

That command is also a CI step, so a clean local run is the fastest way to know
CI will pass. The suite is plain `unittest`, so `pytest` collects it too if you
prefer that runner, but pytest is not required.

## Adding a check

Each check is a function in `src/driftcheck/checks.py` that returns a list of
`Finding` objects. The pattern:

1. Pick a code prefix and add it to `CODE_PREFIXES` in `findings.py`
   (`PY` -> `python`, for example).
2. Write `check_something(project: Project) -> list[Finding]` in `checks.py`.
   Use the parsing helpers instead of re-reading files: `project.text` is the
   raw `pyproject.toml`, and `project.root` is the project directory.
3. Register the code and severity in the README table.
4. Add tests in `tests/`, using `ProjectTestCase` from `tests/helpers.py` so the
   fixture project is built in a temporary directory.
5. Add a `CHANGELOG.md` entry under `## [Unreleased]`.

Rules that keep the output trustworthy:

- **Skip instead of guessing.** If a value cannot be read statically, return no
  finding. A false positive costs more trust than a missed check.
- **Point at the evidence.** Every finding should carry a `file`, and a `line`
  when it is cheap to find one.
- **Explain the fix.** The `hint` is what makes a finding actionable.
- **Errors mean "this will break"; warnings mean "this is probably wrong".**
  `--strict` promotes warnings, so do not use warnings for matters of taste.

## Style

- Standard library only in `src/`. The dev extra (`ruff`, `build`) is for
  tooling, not runtime.
- Type hints on public functions; `from __future__ import annotations` at the
  top of each module.
- British or American spelling is fine, but be consistent within a file.
- Keep messages lowercase after the code, and free of trailing punctuation.

Run the linter:

```console
python -m ruff check .
```

## Commit messages

Imperative mood, one line, then a body when the reason is not obvious:

```text
Report missing changelog entries as VER003

A release with no changelog entry is the most common documentation gap, and it
is cheap to detect from the version already parsed by the version check.
```

## Pull requests

- One concern per pull request.
- Include the test that would have failed before the change.
- If behaviour changes, update the README and `CHANGELOG.md`.
- CI must be green; the `driftcheck` self-check is part of CI.

## Reporting bugs

Open an issue with the output of:

```console
driftcheck --format json . > driftcheck-report.json
```

Attach the report and the smallest `pyproject.toml` that reproduces the problem.
Please do not paste proprietary file contents; the structure is usually enough.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be decent.
