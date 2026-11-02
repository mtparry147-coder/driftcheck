"""Shared helpers for the test suite."""

from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
import unittest
import uuid
from pathlib import Path

from driftcheck import checks
from driftcheck.checks import Config

BASE_PROJECT = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "sample"
version = "0.1.0"
description = "A sample project used by the tests."
readme = "README.md"
requires-python = ">=3.11"
dependencies = []
"""

_REPO_ROOT = Path(__file__).resolve().parents[1]


def with_requirement(*entries: str) -> str:
    """Return ``BASE_PROJECT`` with a populated dependency list."""
    body = ", ".join(f'"{entry}"' for entry in entries)
    return BASE_PROJECT.replace("dependencies = []", f"dependencies = [{body}]")


def _candidate_bases():
    configured = os.environ.get("DRIFTCHECK_TEST_TMP")
    if configured:
        yield Path(configured)
    yield Path(tempfile.gettempdir()) / "driftcheck-tests"
    yield _REPO_ROOT / ".tmp"
    yield Path.cwd() / ".tmp"


def make_scratch() -> Path:
    """Create an empty directory that this process can actually write into.

    Some sandboxes deny writes to directories created with restrictive
    permissions, so each candidate is probed before it is used instead of
    assuming the system temp directory is usable.
    """
    errors: list[str] = []
    for base in _candidate_bases():
        try:
            base.mkdir(parents=True, exist_ok=True)
            target = base / uuid.uuid4().hex[:12]
            target.mkdir()
            probe = target / ".probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            errors.append(f"{base}: {exc}")
            continue
        return target
    raise RuntimeError("no writable scratch directory found: " + "; ".join(errors))


class ProjectTestCase(unittest.TestCase):
    """Builds a throwaway project in a writable scratch directory."""

    def setUp(self) -> None:
        self.root = make_scratch()
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
        return path

    def project(
        self,
        pyproject: str = BASE_PROJECT,
        files: dict[str, str] | None = None,
    ) -> Path:
        self.write("pyproject.toml", pyproject)
        self.write("README.md", "# sample\n")
        for name, content in (files or {}).items():
            self.write(name, content)
        return self.root

    def findings(self, config: Config | None = None):
        return checks.run(self.root, config)

    def codes(self, config: Config | None = None) -> set[str]:
        return {finding.code for finding in self.findings(config)}
