# Semantic Versioning Quick Reference

## Common Commit Patterns

### Bug Fixes (Patch Bump)
```bash
git commit -m "fix: correct line width calculation"
git commit -m "fix(writer): handle edge case in scale auto"
git commit -m "fix: resolve GLE syntax error in bar charts"
```

### New Features (Minor Bump)
```bash
git commit -m "feat: add support for custom markers"
git commit -m "feat(config): add GlobalConfig for project-wide settings"
git commit -m "feat(colors): implement color palette system"
```

### Breaking Changes (Major Bump)
```bash
# Option 1: Exclamation mark
git commit -m "feat!: redesign figure API"

# Option 2: BREAKING CHANGE footer
git commit -m "refactor: simplify configuration system

BREAKING CHANGE: GlobalConfig API changed"
```

### Non-bumping Commits
```bash
git commit -m "docs: update README examples"
git commit -m "test: add unit tests for colors module"
git commit -m "style: format code with black"
git commit -m "chore: update dependencies"
git commit -m "refactor: rename internal variables"
```

## Version Bump Automation

| Commit Type | Version Impact |
|---|---|
| `feat:` | MINOR ↑ |
| `feat!:` | MAJOR ↑ |
| `fix:` | PATCH ↑ |
| `BREAKING CHANGE:` | MAJOR ↑ |
| `docs:`, `style:`, `test:`, `chore:`, `refactor:` | None |

## Commands

**Show current version:**
```bash
cat src/gleplot/__init__.py | grep __version__
```

**Check what commit history looks like:**
```bash
git log --oneline -10
```

**Dry run version bump:**
```bash
python scripts/bump_version.py --dry-run
```

**Actually bump version:**
```bash
python scripts/bump_version.py
# Then push to remote with:
git push origin main --follow-tags
```

**Force specific bump type:**
```bash
python scripts/bump_version.py --major
python scripts/bump_version.py --minor
python scripts/bump_version.py --patch
```

## Tips

✓ Focus on writing good commit messages - version bumping is automatic  
✓ Use scopes to clarify what changed: `feat(config)`, `fix(writer)`  
✓ Keep commits atomic (one logical change per commit)  
✓ First-time users can use `--dry-run` to preview changes  
✓ GitHub Actions automatically versions on pushes to main  
✓ You can manually trigger version bump via GitHub Actions UI  

## Examples

### Scenario: Three commits, auto-detection
```bash
git commit -m "feat(markers): add diamond marker type"
git commit -m "fix(colors): correct RGB conversion"
git commit -m "docs: update marker documentation"

python scripts/bump_version.py --dry-run
# → Detects MINOR (from feat:), creates v0.1.0
```

### Scenario: Only fixes
```bash
git commit -m "fix: correct scale calculation"
git commit -m "fix: handle empty dataset"

python scripts/bump_version.py --dry-run
# → Detects PATCH, creates v0.0.2
```

### Scenario: Breaking change
```bash
git commit -m "feat!: change default figure size

BREAKING CHANGE: figure size changed from 10x8 to 12x9"

python scripts/bump_version.py --dry-run
# → Detects MAJOR, creates v1.0.0
```
