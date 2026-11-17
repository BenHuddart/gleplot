# Versioning and releases

gleplot follows [Semantic Versioning 2.0](https://semver.org/). Releases are
cut automatically by
[Python Semantic Release](https://python-semantic-release.readthedocs.io/)
from [conventional commit](https://www.conventionalcommits.org/) messages on
`main`.

## Commit messages

```
<type>(<optional scope>): <subject>

<optional body>

<optional footer>
```

| Type | Version bump |
|------|--------------|
| `feat` | minor |
| `fix`, `perf` | patch |
| `feat!`, `fix!`, or a `BREAKING CHANGE:` footer | major |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore` | none |

Examples:

```bash
git commit -m "feat: add support for histogram plots"
git commit -m "fix(writer): handle edge case in scale auto"
git commit -m "docs: update installation instructions"
```

A breaking change:

```
feat!: remove deprecated plot_old() function

BREAKING CHANGE: plot_old() has been removed. Use plot() instead.
```

The bump rules live in `pyproject.toml` under
`[tool.semantic_release.commit_parser_options]`.

## How a release happens

1. A push to `main` runs the **Tests** workflow. Pull requests never cut a
   release.
2. When Tests succeed and that commit is still the tip of `main`, the
   **Release** workflow
   ([`.github/workflows/release.yml`](../../.github/workflows/release.yml))
   looks at the commits since the last tag.
3. If they warrant a bump, python-semantic-release updates the version,
   prepends release notes to [`docs/CHANGELOG.md`](../CHANGELOG.md), builds
   the sdist and wheel, pushes the release commit and `vX.Y.Z` tag, and
   creates a GitHub Release with the artifacts attached.
4. If the repository variable `PYPI_PUBLISH` is `true`, a separate job uploads
   to PyPI through Trusted Publishing; see
   [Publishing to PyPI](#publishing-to-pypi).

The version is stored in two places, which the release keeps in sync:
`project.version` in `pyproject.toml` and `__version__` in
`src/gleplot/__init__.py`. Do not edit either by hand.

## Previewing and forcing a release

Preview what the next release would be, without writing anything:

```bash
pip install -e ".[dev]"
semantic-release version --noop
```

To release by hand, go to **Actions → Release → Run workflow** and choose
`auto` or force `major`, `minor` or `patch`.

Maintainers can also release locally, which is rarely needed:

```bash
semantic-release version
git push origin main --follow-tags
```

## Publishing to PyPI

Each release attaches the sdist and wheel to its GitHub Release. Upload to
PyPI is off until a maintainer enables it:

1. Register the gleplot project on PyPI. The workflow uploads to PyPI only,
   not TestPyPI.
2. Add a **Trusted Publisher** on PyPI for this repository, workflow file
   `release.yml`, environment `pypi`.
3. Create a GitHub **Environment** named `pypi` (approval rules are
   recommended).
4. Set the repository variable `PYPI_PUBLISH` to `true`.

The **Publish to PyPI** job authenticates through OIDC
(`pypa/gh-action-pypi-publish`), so no long-lived API token is stored in the
repository.

To check a build locally:

```bash
pip install build twine
python -m build
twine check dist/*
```

## If the Release workflow does nothing

- No commit since the last tag has a bumping type. `docs:`, `test:`, `ci:`
  and the like never release on their own.
- A newer commit reached `main` before Tests finished; that commit's run cuts
  the release instead.
- Tests failed.
