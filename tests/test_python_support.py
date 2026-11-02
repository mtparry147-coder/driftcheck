"""Tests for the Python support check."""

from __future__ import annotations

import unittest

from helpers import BASE_PROJECT, ProjectTestCase

WORKFLOW = """\
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: {value}
    steps:
      - uses: actions/checkout@v4
"""


def build(*, classifiers: tuple[str, ...] = (), requires: str | None = ">=3.11") -> str:
    pyproject = BASE_PROJECT
    if requires is None:
        pyproject = pyproject.replace('requires-python = ">=3.11"\n', "")
    else:
        pyproject = pyproject.replace('requires-python = ">=3.11"', f'requires-python = "{requires}"')
    if classifiers:
        block = "classifiers = [\n" + "".join(f'  "{item}",\n' for item in classifiers) + "]\n"
        pyproject = pyproject.replace("dependencies = []", block + "dependencies = []")
    return pyproject


def ci_versions(*versions: str, block: bool = False) -> str:
    if block:
        items = "".join(f'          - "{version}"\n' for version in versions)
        value = "\n" + items.rstrip("\n")
    else:
        value = "[" + ", ".join(f'"{version}"' for version in versions) + "]"
    return WORKFLOW.format(value=value)


class PythonSupportTests(ProjectTestCase):
    def test_consistent_claims_pass(self) -> None:
        self.project(
            pyproject=build(
                classifiers=(
                    "Programming Language :: Python :: 3.11",
                    "Programming Language :: Python :: 3.12",
                )
            ),
            files={".github/workflows/ci.yml": ci_versions("3.11", "3.12")},
        )
        self.assertEqual(self.codes(), set())

    def test_classifier_below_floor_is_an_error(self) -> None:
        self.project(
            pyproject=build(classifiers=("Programming Language :: Python :: 3.9",)),
        )
        findings = [f for f in self.findings() if f.code == "PY001"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")
        self.assertIsNotNone(findings[0].line)

    def test_ci_below_floor_is_an_error(self) -> None:
        self.project(
            files={".github/workflows/ci.yml": ci_versions("3.10", "3.11")},
        )
        self.assertIn("PY002", self.codes())

    def test_untested_classifier_is_a_warning(self) -> None:
        self.project(
            pyproject=build(
                classifiers=(
                    "Programming Language :: Python :: 3.11",
                    "Programming Language :: Python :: 3.13",
                )
            ),
            files={".github/workflows/ci.yml": ci_versions("3.11")},
        )
        findings = [f for f in self.findings() if f.code == "PY003"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warning")

    def test_missing_requires_python_warns(self) -> None:
        self.project(
            pyproject=build(
                classifiers=("Programming Language :: Python :: 3.11",),
                requires=None,
            )
        )
        self.assertIn("PY004", self.codes())

    def test_block_style_matrix_is_parsed(self) -> None:
        self.project(
            files={".github/workflows/ci.yml": ci_versions("3.10", "3.11", block=True)},
        )
        self.assertIn("PY002", self.codes())

    def test_tox_envlist_is_parsed(self) -> None:
        self.project(files={"tox.ini": "[tox]\nenvlist = py310,py311\n"})
        self.assertIn("PY002", self.codes())

    def test_no_ci_and_no_claims_is_quiet(self) -> None:
        self.project()
        self.assertEqual(self.codes(), set())
