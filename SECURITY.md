# Security Policy

This file is GitHub's expected location for a vulnerability-reporting
policy. For the actual security review of the application (auth model,
injection surface, the local-app trust boundary), see
[docs/SECURITY.md](docs/SECURITY.md).

## Supported versions

CAMCO Coordinator is deployed as internal tooling with a single rolling
release - only the latest commit on `main` is supported. There are no
maintained older versions to patch separately.

## Reporting a vulnerability

If you find a security issue in this application (not a general bug -
see the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) for
those), please **do not** open a public issue. Instead, report it
privately:

- Open a [private security advisory](https://github.com/ichbinsakib/camco-coordinator/security/advisories/new)
  on this repository, or
- Contact the repository owner ([@ichbinsakib](https://github.com/ichbinsakib)) directly.

Please include:

- A description of the issue and its potential impact
- Steps to reproduce it
- The version/commit you tested against

You should get an initial response within a few days. Once a fix is
confirmed, it will be merged and this policy's "supported versions" note
means everyone is expected to update by pulling `main`.

## Scope

This is a single-user local desktop application (see
[docs/SECURITY.md](docs/SECURITY.md)'s trust-boundary note) - reports about
the local SQLite file being readable by someone with access to the same
Windows user account are expected behavior, not a vulnerability, unless
they describe a way to escalate beyond that account's own access.
