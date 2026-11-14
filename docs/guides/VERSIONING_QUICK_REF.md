# Semantic Versioning Quick Reference

## Common Commit Patterns

### Bug Fixes (Patch Bump)
```bash
git commit -m "fix: correct line width calculation"
git commit -m "fix(writer): handle edge case in scale auto"
```

### New Features (Minor Bump)
```bash
git commit -m "feat: add support for custom markers"
git commit -m "feat(config): add GlobalConfig for project-wide settings"
```

### Breaking Changes (Major Bump)
```bash
git commit -m "feat!: redesign figure API"

git commit -m "refactor: simplify configuration system

BREAKING CHANGE: GlobalConfig API changed"
```

### Non-bumping Commits
```bash
git commit -m "docs: update README examples"
git commit -m "test: add unit tests for colors module"
git commit -m "chore: update dependencies"
```

## Version Bump Automation

| Commit Type | Version Impact |
|---|---|
| `feat:` | MINOR ↑ |
| `feat!:` | MAJOR ↑ |
| `fix:` | PATCH ↑ |
| `perf:` | PATCH ↑ |
| `BREAKING CHANGE:` | MAJOR ↑ |
| `docs:`, `style:`, `test:`, `chore:`, `refactor:`, `ci:`, `build:` | None |

## Commands

**Show current version:**
```bash
grep __version__ src/gleplot/__init__.py
```

**Preview next release (no changes):**
```bash
pip install -e ".[dev]"
semantic-release version --noop
```

**Push to trigger CI release:**
```bash
git push origin main
# Tests → Release (if commits warrant a bump)
```

**Force release from GitHub:** Actions → Release → Run workflow → pick bump type.

## Tips

- Good commit messages drive versioning; you rarely need to bump by hand locally.
- PyPI upload stays off until `PYPI_PUBLISH` is set on the repository.
- See [VERSIONING.md](VERSIONING.md) for the full guide.