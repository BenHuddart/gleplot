# Semantic Versioning

gleplot uses **Semantic Versioning 2.0** with [Python Semantic Release](https://python-semantic-release.readthedocs.io/). Version bumps are driven by conventional commit messages on `main`.

## Version Format

`MAJOR.MINOR.PATCH` (e.g., `1.2.3`)

- **MAJOR**: Breaking API changes
- **MINOR**: New backward-compatible features
- **PATCH**: Bug fixes and performance improvements

## Conventional Commits

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

### Commit Types that Trigger Version Bumps

| Type | Bump | Example |
|------|------|---------|
| `feat:` | MINOR | `feat(colors): add support for RGB hex codes` |
| `fix:` | PATCH | `fix(axes): correct log scale calculation` |
| `perf:` | PATCH | `perf(writer): reduce string concatenation` |
| `feat!:` or `BREAKING CHANGE:` | MAJOR | `feat!: change default font to 'rm'` |

### Non-bumping Commits

`docs:`, `style:`, `refactor:`, `test:`, `build:`, `ci:`, and `chore:` do not trigger
a release by themselves.

## Local Preview

```bash
pip install -e ".[dev]"

# Preview the next version without writing files
semantic-release version --noop

# Force a bump type (local only)
semantic-release version --patch --noop
semantic-release version --minor --noop
semantic-release version --major --noop
```

## Automated Release (GitHub Actions)

Workflow: [`.github/workflows/release.yml`](../../.github/workflows/release.yml)

1. A push to `main` runs **Tests**. Pull requests do not cut a release.
2. When that push's **Tests** succeed, and the commit is still the tip of `main`, **Release** runs on that branch.
3. python-semantic-release may bump version, update the changelog, build wheels, tag, and
   open a GitHub Release.
4. If `vars.PYPI_PUBLISH` is `true`, the **Publish to PyPI** job uploads artifacts via
   Trusted Publishing (OIDC).

Manual trigger: **Actions** → **Release** → **Run workflow** (optional force bump).

## Version Locations

The version is maintained in two places (kept in sync by releases):

1. `pyproject.toml` — `project.version`
2. `src/gleplot/__init__.py` — `__version__`

## Best Practices

1. Use meaningful commit types and scopes (`feat(writer):`, `fix(parser):`).
2. Mark breaking changes with `feat!:` or a `BREAKING CHANGE:` footer.
3. Run `semantic-release version --noop` before a large release if you are unsure what will ship.

## References

- [Semantic Versioning 2.0](https://semver.org/)
- [Conventional Commits 1.0](https://www.conventionalcommits.org/)
- [VERSIONING.md](../VERSIONING.md) (repository root guide)
- [VERSIONING_QUICK_REF.md](VERSIONING_QUICK_REF.md)