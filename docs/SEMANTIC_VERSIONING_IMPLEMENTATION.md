# Semantic Versioning Implementation Summary

## System Overview

gleplot releases are handled by [Python Semantic Release](https://python-semantic-release.readthedocs.io/):

1. **Analyzes git commits** using conventional commits (`feat`, `fix`, `perf`, breaking changes)
2. **Updates version** in `pyproject.toml` and `src/gleplot/__init__.py`
3. **Prepends release notes** to `docs/CHANGELOG.md` (update mode preserves hand-written history)
4. **Builds** sdist and wheel via `python -m build`
5. **Tags and publishes** a GitHub Release with distribution artifacts attached
6. **Optionally uploads to PyPI** when `PYPI_PUBLISH` is enabled

## Components

### GitHub Actions

| Workflow | Role |
|----------|------|
| [`.github/workflows/test.yml`](../.github/workflows/test.yml) | Test matrix on push/PR to `main` |
| [`.github/workflows/release.yml`](../.github/workflows/release.yml) | Runs after Tests succeed; semantic release + optional PyPI |

Configuration: `[tool.semantic_release]` in [`pyproject.toml`](../pyproject.toml).

### Documentation

- [VERSIONING.md](VERSIONING.md) — commit format and release flow
- [guides/VERSIONING.md](guides/VERSIONING.md) — contributor guide
- [guides/VERSIONING_QUICK_REF.md](guides/VERSIONING_QUICK_REF.md) — quick reference
- [guides/DEVELOPMENT_WORKFLOW.md](guides/DEVELOPMENT_WORKFLOW.md) — publishing and PyPI setup

### Examples

- [`examples/example_versioning_workflow.py`](../examples/example_versioning_workflow.py) — illustrated scenarios (stdout only)

## Conventional Commits Support

| Commit Type | Bump Type |
|---|---|
| `feat:` | MINOR |
| `fix:`, `perf:` | PATCH |
| `feat!:` / `BREAKING CHANGE:` | MAJOR |
| `docs:`, `test:`, `style:`, `chore:`, `refactor:`, `ci:`, `build:` | NONE |

## Typical Release Flow

```bash
git commit -m "feat: add new marker types"
git push origin main
```

1. **Tests** workflow runs on the push.
2. **Release** workflow runs on success.
3. If commits since the last tag warrant a bump, a new `vX.Y.Z` tag and GitHub Release appear.

Manual override: **Actions** → **Release** → **Run workflow**.

## PyPI

PyPI publishing is wired but disabled until:

- PyPI Trusted Publisher is configured for `release.yml` / environment `pypi`
- Repository variable `PYPI_PUBLISH` is `true`

See [DEVELOPMENT_WORKFLOW.md](guides/DEVELOPMENT_WORKFLOW.md#6-publishing).

## References

- [Semantic Versioning 2.0](https://semver.org/)
- [Conventional Commits 1.0](https://www.conventionalcommits.org/)
- [Python Semantic Release docs](https://python-semantic-release.readthedocs.io/)