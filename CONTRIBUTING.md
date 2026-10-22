# Contributing to kubeman

Thanks for your interest in improving kubeman!

## Development setup

kubeman uses [uv](https://github.com/astral-sh/uv) for environment and
dependency management.

```bash
# Install all dependencies (runtime + dev toolchain) into a local venv
uv sync

# Install the pre-commit hooks (ruff + black run automatically on commit)
uv run pre-commit install
```

## Quality checks

CI runs all of these; run them locally before opening a PR:

```bash
uv run pytest                  # tests (or: make test)
uv run ruff check .            # lint
uv run black --check .         # formatting
uv run mypy kubeman/           # type checking
```

Tests must keep total coverage at or above the gate enforced in CI
(`--cov-fail-under`). Run with coverage locally via:

```bash
uv run pytest --cov=kubeman --cov-report=term-missing
```

## Supported Python versions

kubeman targets Python 3.11+ and is tested in CI on 3.11–3.14. Avoid syntax or
stdlib features newer than 3.11.

## Versioning and releases

The version lives in a single place: `kubeman/__init__.py` (pyproject reads it
via `[tool.hatch.version]`). Bump it with the Makefile:

```bash
make bump-patch         # 0.6.0 -> 0.6.1
make bump-minor         # 0.6.0 -> 0.7.0
make bump VERSION=1.0.0 # explicit
```

Publishing to PyPI happens automatically when a GitHub Release is published
(see `.github/workflows/publish.yml`).

## Pull requests

- Keep changes focused; one logical change per PR where practical.
- Update `CHANGELOG.md` (the `[Unreleased]` section) for user-facing changes.
- Make sure the full CI suite (lint + types + tests on all supported Python
  versions + coverage gate) is green.
