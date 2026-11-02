"""Tests for the entry point and file checks."""

from __future__ import annotations

import unittest

from helpers import BASE_PROJECT, ProjectTestCase


class EntryPointTests(ProjectTestCase):
    def test_valid_entry_point_passes(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.scripts]\nsample = "sample.cli:main"\n'
        self.project(
            pyproject=pyproject,
            files={"src/sample/cli.py": "def main() -> int:\n    return 0\n"},
        )
        self.assertEqual(self.codes(), set())

    def test_missing_module_is_an_error(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.scripts]\nsample = "sample.nope:main"\n'
        self.project(pyproject=pyproject)
        self.assertIn("ENT001", self.codes())

    def test_missing_attribute_is_an_error(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.scripts]\nsample = "sample.cli:entry"\n'
        self.project(
            pyproject=pyproject,
            files={"src/sample/cli.py": "def main() -> int:\n    return 0\n"},
        )
        findings = [f for f in self.findings() if f.code == "ENT002"]
        self.assertEqual(len(findings), 1)
        self.assertIn("entry", findings[0].message)

    def test_flat_layout_is_supported(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.scripts]\nsample = "sample.cli:main"\n'
        self.project(
            pyproject=pyproject,
            files={"sample/cli.py": "main = lambda: 0\n"},
        )
        self.assertNotIn("ENT002", self.codes())

    def test_gui_scripts_are_checked(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.gui-scripts]\nsample-gui = "sample.cli:main"\n'
        self.project(pyproject=pyproject)
        self.assertIn("ENT001", self.codes())

    def test_dynamic_getattr_is_not_flagged(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.scripts]\nsample = "sample.cli:anything"\n'
        self.project(
            pyproject=pyproject,
            files={"src/sample/cli.py": "def __getattr__(name):\n    raise AttributeError(name)\n"},
        )
        self.assertNotIn("ENT002", self.codes())

    def test_colonless_value_is_an_error(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.scripts]\nsample = "sample.cli"\n'
        self.project(pyproject=pyproject, files={"src/sample/cli.py": "x = 1\n"})
        self.assertIn("ENT001", self.codes())


class FileTests(ProjectTestCase):
    def test_missing_readme_file_is_an_error(self) -> None:
        self.project()
        (self.root / "README.md").unlink()
        self.assertIn("FIL001", self.codes())

    def test_undeclared_readme_warns(self) -> None:
        pyproject = BASE_PROJECT.replace('readme = "README.md"\n', "")
        self.project(pyproject=pyproject)
        self.assertIn("FIL002", self.codes())

    def test_license_string_without_file_warns(self) -> None:
        pyproject = BASE_PROJECT.replace(
            'readme = "README.md"', 'readme = "README.md"\nlicense = "MIT"'
        )
        self.project(pyproject=pyproject)
        self.assertIn("FIL004", self.codes())

    def test_license_file_missing_is_an_error(self) -> None:
        pyproject = BASE_PROJECT.replace(
            'readme = "README.md"', 'readme = "README.md"\nlicense = { file = "LICENSE" }'
        )
        self.project(pyproject=pyproject)
        self.assertIn("FIL003", self.codes())

    def test_license_file_present_passes(self) -> None:
        pyproject = BASE_PROJECT.replace(
            'readme = "README.md"', 'readme = "README.md"\nlicense = "MIT"'
        )
        self.project(pyproject=pyproject, files={"LICENSE": "MIT License\n"})
        self.assertEqual(self.codes(), set())
