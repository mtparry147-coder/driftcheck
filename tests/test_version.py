"""Tests for the version check."""

from __future__ import annotations


from helpers import BASE_PROJECT, ProjectTestCase


class VersionCheckTests(ProjectTestCase):
    def test_consistent_versions_pass(self) -> None:
        self.project(files={"src/sample/__init__.py": '__version__ = "0.1.0"\n'})
        self.assertEqual(self.codes(), set())

    def test_mismatch_between_pyproject_and_package(self) -> None:
        self.project(files={"src/sample/__init__.py": '__version__ = "0.2.0"\n'})
        findings = self.findings()
        self.assertIn("VER001", {finding.code for finding in findings})
        mismatch = next(f for f in findings if f.code == "VER001")
        self.assertEqual(mismatch.severity, "error")
        self.assertIn("0.2.0", mismatch.message)
        self.assertIsNotNone(mismatch.line)

    def test_v_prefix_is_tolerated(self) -> None:
        self.project(files={"src/sample/__init__.py": '__version__ = "v0.1.0"\n'})
        self.assertNotIn("VER001", self.codes())

    def test_citation_file_is_compared(self) -> None:
        self.project(
            files={
                "src/sample/__init__.py": '__version__ = "0.1.0"\n',
                "CITATION.cff": "cff-version: 1.2.0\nversion: 0.2.0\n",
            }
        )
        self.assertIn("VER001", self.codes())

    def test_docs_conf_is_compared(self) -> None:
        self.project(
            files={
                "docs/conf.py": 'project = "sample"\nrelease = "0.3.0"\n',
            }
        )
        self.assertIn("VER001", self.codes())

    def test_changelog_entry_present(self) -> None:
        self.project(
            files={"CHANGELOG.md": "# Changelog\n\n## [0.1.0] - 2026-01-01\n\n- initial\n"}
        )
        self.assertNotIn("VER003", self.codes())

    def test_changelog_entry_missing_is_a_warning(self) -> None:
        self.project(
            files={"CHANGELOG.md": "# Changelog\n\n## [0.0.9] - 2025-01-01\n\n- old\n"}
        )
        findings = [f for f in self.findings() if f.code == "VER003"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warning")

    def test_no_version_anywhere(self) -> None:
        pyproject = BASE_PROJECT.replace('version = "0.1.0"\n', "")
        self.project(pyproject=pyproject)
        self.assertIn("VER002", self.codes())

    def test_dynamic_dunder_version_is_ignored(self) -> None:
        self.project(
            files={
                "src/sample/__init__.py": (
                    "from importlib.metadata import version\n"
                    '__version__ = version("sample")\n'
                )
            }
        )
        self.assertNotIn("VER001", self.codes())

    def test_package_json_is_compared(self) -> None:
        self.project(files={"package.json": '{"name": "sample", "version": "0.4.0"}\n'})
        self.assertIn("VER001", self.codes())
