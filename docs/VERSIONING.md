# Semantic Versioning Guide for gleplot

This project uses [Python Semantic Release](https://python-semantic-release.readthedocs.io/) for automated version management.

## How It Works

The version number is automatically updated using a two-stage strategy:

1. **Conventional Commits first** (recommended)
2. **File-change fallback heuristics** when commit messages do not include semantic prefixes

This makes releases more robust when commits are valid but not perfectly formatted.

## Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature (triggers MINOR version bump: 0.0.1 → 0.1.0)
- **fix**: A bug fix (triggers PATCH version bump: 0.0.1 → 0.0.2)
- **docs**: Documentation only changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring without changing functionality
- **perf**: Performance improvements (triggers PATCH version bump)
- **test**: Adding or correcting tests
- **build**: Changes to build system or dependencies
- **ci**: Changes to CI configuration files
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

### Intelligent Fallback (when commit prefixes are missing)

If no `feat:`, `fix:`, `perf:`, or breaking-change marker is found, the version script inspects changed files since the last tag:

- **MINOR bump**: New Python module added under `src/gleplot/`
- **PATCH bump**: Existing source changes under `src/gleplot/`, or packaging/runtime script changes (`pyproject.toml`, `scripts/`)
- **NO bump**: Documentation/tests/examples/output-only changes (`docs/`, `tests/`, `examples/`, markdown/rst/text files, generated graphics output folders)

This fallback is conservative and avoids silent missed releases for source code changes.

### Breaking Changes

To trigger a MAJOR version bump (0.0.1 → 1.0.0), include `BREAKING CHANGE:` in the commit footer or add `!` after the type:

```
feat!: remove deprecated plot_old() function

BREAKING CHANGE: The plot_old() function has been removed. Use plot() instead.
```

## Examples

### Feature (minor version bump)
```bash
git commit -m "feat: add support for histogram plots"
# Version: 0.0.1 → 0.1.0
```

### Bug Fix (patch version bump)
```bash
git commit -m "fix: correct color mapping for hex codes"
# Version: 0.0.1 → 0.0.2
```

### Documentation
```bash
git commit -m "docs: update installation instructions"
# Version: No change
```

### Breaking Change (major version bump)
```bash
git commit -m "feat!: redesign figure API

BREAKING CHANGE: Figure.save() renamed to Figure.savefig() for matplotlib compatibility"
# Version: 0.0.1 → 1.0.0
```

## Creating a Release

### Manual Release

1. Make sure all changes are committed with proper commit messages
2. Run semantic-release to create a new version:
   ```bash
   pip install python-semantic-release
   semantic-release version
   ```
3. Push the changes and tags:
   ```bash
   git push origin main --follow-tags
   ```

### Automated Release (GitHub Actions)

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    branches:
      - main

jobs:
  release:
    runs-on: ubuntu-latest
    concurrency: release
    permissions:
      contents: write
      
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          
      - name: Python Semantic Release
        uses: python-semantic-release/python-semantic-release@v8.0.0
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

## Viewing the Current Version

```bash
# From pyproject.toml
grep version pyproject.toml

# From Python
python -c "import gleplot; print(gleplot.__version__)"
```

## Version History

See [CHANGELOG.md](CHANGELOG.md) for the full version history.
