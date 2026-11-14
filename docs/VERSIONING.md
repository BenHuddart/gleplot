# Semantic Versioning Guide for gleplot

This project uses [Python Semantic Release](https://python-semantic-release.readthedocs.io/) for automated version management.

## How It Works

A push to `main` runs the **Tests** workflow. When that run succeeds, and the commit
is still the tip of `main`, the **Release** workflow
([`.github/workflows/release.yml`](../.github/workflows/release.yml)) checks commits
since the last tag. Pull requests do not cut a release. If a `feat`, `fix`, `perf`, or breaking change warrants a bump,
python-semantic-release updates `pyproject.toml`, `src/gleplot/__init__.py`, and
`docs/CHANGELOG.md`, builds sdist/wheel artifacts, pushes the release commit and tag, and
creates a GitHub Release with those artifacts attached.

PyPI upload is a separate job in the same workflow, enabled only when the repository
variable `PYPI_PUBLISH` is `true` and PyPI Trusted Publishing is configured (see
[DEVELOPMENT_WORKFLOW.md](guides/DEVELOPMENT_WORKFLOW.md#publishing)).

## Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature (triggers MINOR version bump)
- **fix**: A bug fix (triggers PATCH version bump)
- **docs**: Documentation only changes (no bump)
- **style**: Code style changes (no bump)
- **refactor**: Code refactoring without changing functionality (no bump)
- **perf**: Performance improvements (triggers PATCH version bump)
- **test**: Adding or correcting tests (no bump)
- **build**: Changes to build system or dependencies (no bump)
- **ci**: Changes to CI configuration files (no bump)
- **chore**: Other changes that don't modify releasable behaviour (no bump)
- **revert**: Reverts a previous commit (parsed like the reverted commit)

Bump rules are configured in `pyproject.toml` under `[tool.semantic_release.commit_parser_options]`.

### Breaking Changes

To trigger a MAJOR version bump, include `BREAKING CHANGE:` in the commit footer or add `!` after the type:

```
feat!: remove deprecated plot_old() function

BREAKING CHANGE: The plot_old() function has been removed. Use plot() instead.
```

## Examples

### Feature (minor version bump)
```bash
git commit -m "feat: add support for histogram plots"
```

### Bug Fix (patch version bump)
```bash
git commit -m "fix: correct color mapping for hex codes"
```

### Documentation
```bash
git commit -m "docs: update installation instructions"
# No release on docs-only pushes
```

## Creating a Release

### Automatic (recommended)

Push conventional commits to `main`. After **Tests** pass, **Release** runs and cuts a
version when warranted.

### Manual local preview

```bash
pip install -e ".[dev]"
semantic-release version --noop
```

### Manual release from GitHub Actions

Go to **Actions** → **Release** → **Run workflow**, then choose **auto** or force
**major** / **minor** / **patch**.

### Manual local release

```bash
pip install -e ".[dev]"
semantic-release version
git push origin main --follow-tags
```

## Viewing the Current Version

```bash
grep '^version' pyproject.toml
python -c "import gleplot; print(gleplot.__version__)"
```

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the full version history.