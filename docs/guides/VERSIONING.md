# Semantic Versioning

gleplot uses **Semantic Versioning 2.0** for automatic version management. The versioning is fully automated based on your commit messages.

## Version Format

`MAJOR.MINOR.PATCH` (e.g., `1.2.3`)

- **MAJOR**: Breaking changes to the API
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## Conventional Commits

Automatic version bumping uses [Conventional Commits](https://www.conventionalcommits.org/) format:

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
| `feat!:` or `BREAKING CHANGE:` | MAJOR | `feat!: change default font to 'rm'` |

### Non-bumping Commits

- `docs:` - Documentation only
- `style:` - Formatting/style changes  
- `refactor:` - Code refactoring without behavior change
- `test:` - Test additions/changes
- `chore:` - Build, CI, dependencies
- Regular commit messages (no type prefix)

## Manual Version Bumping

### Using the Script

For manual control without waiting for automated workflow:

```bash
# Auto-detect version bump from commits since last tag
python scripts/bump_version.py

# Force specific version bump
python scripts/bump_version.py --major     # Bump major version
python scripts/bump_version.py --minor     # Bump minor version
python scripts/bump_version.py --patch     # Bump patch version

# Preview changes without modifying files
python scripts/bump_version.py --dry-run
```

### What the Script Does

1. **Analyzes commits** since the last git tag
2. **Determines version bump** based on conventional commit messages
3. **Updates version** in:
   - `pyproject.toml`
   - `src/gleplot/__init__.py`
4. **Creates git commit** with message `chore: bump version to X.Y.Z`
5. **Creates git tag** `vX.Y.Z`
6. **Outputs instructions** for pushing to remote

### Example Workflow

```bash
# Make commits with proper types
git commit -m "feat: add new plotting functionality"
git commit -m "fix: correct calculation error"
git commit -m "docs: update README"

# Check what would be bumped (dry run)
python scripts/bump_version.py --dry-run
# Output: Version bump: minor (from one feat: commit)

# Actually bump version
python scripts/bump_version.py
# Output updates both files, creates tag, shows push instructions

# Push to remote
git push origin main
git push origin v0.1.0
```

## Automated Versioning

### GitHub Actions Workflow

A GitHub Actions workflow automatically bumps versions on pushes to `main`:

1. On each push to `main`, the workflow:
   - Checks for new commits since last tag
   - Analyzes commit messages
   - Bumps version if changes detected
   - Pushes version commit and tag back to repository

2. Manual trigger available:
   - Go to **Actions** → **Semantic Versioning**
   - Click **Run workflow**
   - Select bump type (auto, major, minor, patch)
   - Click **Run**

### Disabling Auto-Versioning

To disable automatic versioning temporarily, add `[skip-version]` to your commit message:

```bash
git commit -m "feat: minor change [skip-version]"
```

## Version Locations

The version is maintained in two places (kept in sync automatically):

1. `pyproject.toml`:
   ```toml
   [project]
   version = "0.1.0"
   ```

2. `src/gleplot/__init__.py`:
   ```python
   __version__ = '0.1.0'
   ```

## First Release

For the first release (starting from v0.0.1):

```bash
# After initial commits with proper types
python scripts/bump_version.py
# Will bump to v0.1.0 if there's a feat: commit
# Or v0.0.2 if only fix: commits
```

## Best Practices

1. **Use meaningful commit messages**:
   ```bash
   git commit -m "feat(config): make font configurable"  # Good
   git commit -m "updated font settings"                  # Bad
   ```

2. **Use scopes for clarity** (optional):
   ```bash
   git commit -m "fix(writer): correct GLE syntax"
   git commit -m "feat(colors): add new color palette"
   ```

3. **Mark breaking changes clearly**:
   ```bash
   git commit -m "feat!: redesign API"
   # or
   git commit -m "feat: redesign API

   BREAKING CHANGE: old API removed"
   ```

4. **Group related changes** when possible (fewer, larger commits are often cleaner than many tiny ones)

5. **Only bump for user-facing changes** - the versioning is automatic, so focus on good commit messages

## References

- [Semantic Versioning 2.0](https://semver.org/)
- [Conventional Commits 1.0](https://www.conventionalcommits.org/)
- [Python Packaging](https://packaging.python.org/specifications/version-identifiers/)
