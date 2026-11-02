# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-02

### Added

- Version check: compares the version declared in `pyproject.toml` with
  `__version__`, `CITATION.cff`, `docs/conf.py`, `package.json`, and
  `setup.cfg`, and warns when `CHANGELOG.md` has no entry for it.
- Dependency check: compares `[project] dependencies` and optional groups with
  `requirements*.txt`, following `-r` includes, and reports missing, extra, and
  conflicting entries.
- Python support check: compares `requires-python`, trove classifiers, and the
  versions CI actually runs.
- Entry point check: resolves `[project.scripts]` and `[project.gui-scripts]`
  to real modules and attributes.
- File check: confirms the readme and licence files referenced by
  `pyproject.toml` exist.
- CLI with `text`, `json`, and `github` output formats, `--select`, `--ignore`,
  and `--strict`.
- pre-commit hook and composite GitHub Action.
