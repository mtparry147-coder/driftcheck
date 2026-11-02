"""Tests for the command-line interface."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from driftcheck import __version__, cli
from helpers import BASE_PROJECT, ProjectTestCase


def run_cli(*args: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(list(args))
    return code, stdout.getvalue(), stderr.getvalue()


class CliTests(ProjectTestCase):
    def test_clean_project_exits_zero(self) -> None:
        self.project()
        code, out, _ = run_cli(str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("no drift found", out)

    def test_findings_exit_one(self) -> None:
        self.project(files={"src/sample/__init__.py": '__version__ = "9.9.9"\n'})
        code, out, _ = run_cli(str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("VER001", out)

    def test_json_output_is_valid(self) -> None:
        self.project(files={"src/sample/__init__.py": '__version__ = "9.9.9"\n'})
        code, out, _ = run_cli("--format", "json", str(self.root))
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["tool"], "driftcheck")
        self.assertEqual(payload["version"], __version__)
        self.assertEqual(payload["summary"]["errors"], 1)
        self.assertEqual(payload["findings"][0]["code"], "VER001")

    def test_github_format(self) -> None:
        self.project(files={"src/sample/__init__.py": '__version__ = "9.9.9"\n'})
        code, out, _ = run_cli("--format", "github", str(self.root))
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("::error "))
        self.assertIn("title=VER001", out)

    def test_strict_elevates_warnings(self) -> None:
        pyproject = BASE_PROJECT.replace('readme = "README.md"\n', "")
        self.project(pyproject=pyproject)
        self.assertEqual(run_cli(str(self.root))[0], 0)
        self.assertEqual(run_cli("--strict", str(self.root))[0], 1)

    def test_missing_pyproject_exits_two(self) -> None:
        code, _, err = run_cli(str(self.root))
        self.assertEqual(code, 2)
        self.assertIn("no pyproject.toml", err)

    def test_missing_directory_exits_two(self) -> None:
        code, _, err = run_cli(str(self.root / "nope"))
        self.assertEqual(code, 2)
        self.assertIn("not a directory", err)

    def test_select_limits_output(self) -> None:
        pyproject = BASE_PROJECT + '\n[project.scripts]\nsample = "sample.nope:main"\n'
        self.project(
            pyproject=pyproject,
            files={"src/sample/__init__.py": '__version__ = "9.9.9"\n'},
        )
        code, out, _ = run_cli("--select", "ENT", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("ENT001", out)
        self.assertNotIn("VER001", out)

    def test_ignore_removes_a_code(self) -> None:
        self.project(files={"src/sample/__init__.py": '__version__ = "9.9.9"\n'})
        code, out, _ = run_cli("--ignore", "VER001", str(self.root))
        self.assertEqual(code, 0)
        self.assertNotIn("VER001", out)

    def test_list_checks(self) -> None:
        code, out, _ = run_cli("--list-checks")
        self.assertEqual(code, 0)
        for name in ("version", "dependencies", "python", "entrypoints", "files"):
            self.assertIn(name, out)

    def test_path_defaults_to_current_directory(self) -> None:
        self.project()
        import os

        previous = os.getcwd()
        os.chdir(self.root)
        try:
            code, _, _ = run_cli()
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0)


class RepositoryTests(unittest.TestCase):
    def test_repository_checks_itself_cleanly(self) -> None:
        from driftcheck import checks

        root = Path(__file__).resolve().parents[1]
        findings = checks.run(root)
        self.assertEqual(
            findings,
            [],
            "driftcheck reports findings on its own repository: "
            + ", ".join(f"{finding.code} {finding.message}" for finding in findings),
        )
