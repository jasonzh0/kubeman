# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `kubeman --version` and a proper `kubeman` program name in help output.
- `apply` now supports `--dry-run` (`kubectl apply --dry-run=server`),
  `--context`, and an interactive confirmation prompt (skipped in
  non-interactive use or with `-y`/`--yes`).
- Configurable subprocess timeouts on `CommandExecutor` (default 300s).
- `TemplateRegistry.run_build_steps()` to run build/load steps explicitly.
- Type checking with mypy, a CI lint job (ruff + black + mypy), and a test
  coverage gate.
- `CONTRIBUTING.md` and this changelog; documentation for the `plan` command,
  common flags, and the `MANIFESTS_DIR` environment variable.

### Changed
- **Build and load steps now run only during `apply`**, as an explicit phase
  rather than a side effect of importing the templates file. `render`, `plan`,
  and `visualize` never run them.
- `plan` renders into a temporary directory and no longer writes to the user's
  manifests directory.
- Minimum supported Python is now 3.10 (3.8/3.9 are EOL); CI tests 3.10–3.13.
- Single-sourced the package version from `kubeman/__init__.py`.
- Removed the no-op `--skip-build` flag from `render`/`plan`/`visualize`.

### Fixed
- Manifest filenames are validated to prevent path traversal via crafted
  `metadata.name` values.
- Credentials embedded in URLs (e.g. `git clone https://user:token@host`) are
  redacted from logs.
- Extracted CRD temp files are written to the system temp dir and cleaned up,
  instead of leaking into (and being re-applied from) the manifests directory.
- `visualize` now links Services to `Job` workloads (the kind list was
  inconsistent across the module).
- Unexpected CLI errors now produce a clean message and exit code instead of a
  traceback.

## [0.6.0]

- Baseline release prior to the changes above. See the Git history for details.
