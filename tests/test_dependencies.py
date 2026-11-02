"""Tests for the dependency check and requirements parsing."""

from __future__ import annotations

import unittest

from driftcheck import requirements
from driftcheck.checks import Config
from helpers import ProjectTestCase, with_requirement


class RequirementParsingTests(unittest.TestCase):
    def test_comments_and_blank_lines_are_ignored(self) -> None:
        parsed = requirements.parse_requirements("# a comment\n\nhttpx>=0.27  # inline\n")
        self.assertEqual([item.name for item in parsed], ["httpx"])
        self.assertEqual(parsed[0].line, 3)

    def test_options_and_urls_are_skipped(self) -> None:
        text = "-r base.txt\n--index-url https://example.com\n-e git+https://example.com/x.git#egg=x\n"
        self.assertEqual(requirements.parse_requirements(text), [])

    def test_extras_are_captured(self) -> None:
        parsed = requirements.parse_requirement("uvicorn[standard,uvloop]>=0.30")
        assert parsed is not None
        self.assertEqual(parsed.name, "uvicorn")
        self.assertEqual(parsed.extras, ("standard", "uvloop"))
        self.assertEqual(parsed.specifier, ">=0.30")

    def test_specifiers_are_canonicalised(self) -> None:
        parsed = requirements.parse_requirement("pkg<3,>=2")
        assert parsed is not None
        self.assertEqual(parsed.specifier, "<3,>=2")

    def test_markers_are_not_part_of_the_specifier(self) -> None:
        parsed = requirements.parse_requirement('pkg>=1 ; python_version < "3.12"')
        assert parsed is not None
        self.assertEqual(parsed.specifier, ">=1")

    def test_names_are_normalised(self) -> None:
        parsed = requirements.parse_requirement("My_Package.Name>=1")
        assert parsed is not None
        self.assertEqual(parsed.name, "my-package-name")

    def test_unparseable_lines_are_skipped(self) -> None:
        self.assertIsNone(requirements.parse_requirement("not a requirement at all"))
        self.assertIsNone(requirements.parse_requirement(""))


class DependencyCheckTests(ProjectTestCase):
    def test_no_requirements_file_means_no_findings(self) -> None:
        self.project(pyproject=with_requirement("httpx>=0.27"))
        self.assertEqual(self.codes(), set())

    def test_matching_dependencies_pass(self) -> None:
        self.project(
            pyproject=with_requirement("httpx>=0.27"),
            files={"requirements.txt": "httpx>=0.27\n"},
        )
        self.assertEqual(self.codes(), set())

    def test_missing_from_requirements_warns(self) -> None:
        self.project(
            pyproject=with_requirement("httpx>=0.27"),
            files={"requirements.txt": "httpcore>=1.0\n"},
        )
        self.assertIn("DEP001", self.codes())
        self.assertIn("DEP002", self.codes())

    def test_conflicting_specifier_is_an_error(self) -> None:
        self.project(
            pyproject=with_requirement("httpx>=0.27"),
            files={"requirements.txt": "httpx>=0.25\n"},
        )
        findings = [f for f in self.findings() if f.code == "DEP003"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")
        self.assertEqual(findings[0].line, 1)

    def test_requirements_includes_are_followed(self) -> None:
        self.project(
            pyproject=with_requirement("httpx>=0.27"),
            files={
                "requirements.txt": "-r base.txt\n",
                "base.txt": "httpx>=0.27\n",
            },
        )
        self.assertNotIn("DEP003", self.codes())

    def test_optional_group_file_is_checked(self) -> None:
        pyproject = with_requirement("httpx>=0.27") + (
            "\n[project.optional-dependencies]\ndev = [\"ruff>=0.6\"]\n"
        )
        self.project(
            pyproject=pyproject,
            files={"requirements-dev.txt": "ruff>=0.5\n"},
        )
        self.assertIn("DEP003", self.codes())

    def test_custom_requirements_mapping(self) -> None:
        pyproject = with_requirement("httpx>=0.27") + (
            "\n[project.optional-dependencies]\ndev = [\"ruff>=0.6\"]\n"
            "\n[tool.driftcheck.requirements]\ndev = \"ci/requirements.txt\"\n"
        )
        self.project(
            pyproject=pyproject,
            files={"ci/requirements.txt": "ruff>=0.4\n"},
        )
        self.assertIn("DEP003", self.codes())

    def test_missing_mapped_file_warns(self) -> None:
        pyproject = with_requirement("httpx>=0.27") + (
            "\n[project.optional-dependencies]\ndev = [\"ruff>=0.6\"]\n"
            "\n[tool.driftcheck.requirements]\ndev = \"nope.txt\"\n"
        )
        self.project(pyproject=pyproject)
        self.assertIn("DEP004", self.codes())

    def test_poetry_dependencies_compare_names_only(self) -> None:
        pyproject = """\
[build-system]
requires = ["poetry-core>=2.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "sample"
version = "0.1.0"
description = "A sample project."

[tool.poetry.dependencies]
python = ">=3.11"
httpx = "^0.27"

[project]
name = "sample"
version = "0.1.0"
description = "A sample project."
readme = "README.md"
requires-python = ">=3.11"
"""
        self.project(pyproject=pyproject, files={"requirements.txt": "httpx>=0.1\n"})
        self.assertNotIn("DEP003", self.codes())

    def test_ignore_config_suppresses_a_code(self) -> None:
        self.project(
            pyproject=with_requirement("httpx>=0.27"),
            files={"requirements.txt": "httpx>=0.25\n"},
        )
        codes = self.codes(Config(ignore=frozenset({"DEP003"})))
        self.assertNotIn("DEP003", codes)
