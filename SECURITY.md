# Security policy

## Supported versions

`driftcheck` is a local, offline analysis tool. It reads files in the project you
point it at and never sends data anywhere. There is no server component and no
credential handling.

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## Reporting a vulnerability

Please report suspected vulnerabilities privately, using GitHub's
[private vulnerability reporting](https://github.com/mtparry147-coder/driftcheck/security/advisories/new)
rather than a public issue.

Useful reports include:

- a `pyproject.toml`, workflow file, or source file that causes `driftcheck` to
  execute code, hang, or read files outside the scanned project
- a crash caused by crafted input (please include the smallest example)
- anything that would make the tool unsafe to run in CI on an untrusted pull
  request

You can expect an acknowledgement within a few days. If the report is valid, a
fix and a release will follow, with credit unless you prefer otherwise.

## Scope

`driftcheck` parses files; it does not import the project it analyses. The one
place source files are read is entry point resolution, which uses `ast.parse`
and never executes the module. Findings are advisory: the tool does not modify
files, so a malicious input cannot corrupt a repository through it.
