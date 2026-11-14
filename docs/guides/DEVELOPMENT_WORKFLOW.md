# Development Workflow Guide

This guide integrates all gleplot development practices: configuration, versioning, testing, and commits.

## Complete Development Cycle

### 1. Planning & Setup

```bash
# Clone and install in development mode
git clone https://github.com/your-repo/gleplot.git
cd gleplot
pip install -e .
pip install -e ".[dev]"  # Installs test dependencies

# Verify setup
python -m pytest tests/ -q  # Should pass all tests
python examples/run_and_compile.py  # Should compile all examples
```

### 2. Making Changes

#### Write Code with Intent

```python
# examples/my_new_feature.py
import gleplot as glp
import numpy as np

# Use global configuration for project-wide styling
glp.config.GlobalConfig.style.font = 'rm'
glp.config.GlobalConfig.style.fontsize = 10

# Or create figure-specific config
fig = glp.figure(figsize=(10, 8))
fig.style.default_linewidth = 0.05  # cm

# Rest of implementation...
```

#### Write Tests As You Go

```python
# tests/unit/test_my_feature.py
import pytest
import gleplot as glp

def test_my_feature():
    """Test the new feature."""
    # Test code...
    assert result == expected
```

#### Commit with Semantic Intent

```bash
# Edit files
echo "new code" > src/gleplot/newmodule.py
echo "tests" > tests/unit/test_newmodule.py

# Stage changes
git add src/gleplot/newmodule.py tests/unit/test_newmodule.py

# Commit with semantic prefix (feat:, fix:, docs:)
git commit -m "feat: add new plotting feature

This adds support for advanced plotting options:
- Option A: description
- Option B: description

See docs/guides/CONFIGURATION_API.md for usage"
```

**Semantic Commit Types:**

| Type | Use When | Version Impact |
|------|----------|--------|
| `feat:` | Adding new feature | MINOR ↑ |
| `fix:` | Bug fix | PATCH ↑ |
| `docs:` | Documentation change | None |
| `test:` | Test addition/change | None |
| `refactor:` | Code refactoring | None |
| `style:` | Code formatting | None |
| `chore:` | Maintenance | None |

**Breaking Changes:**

```bash
# Option 1: Exclamation point
git commit -m "feat!: redesign API"

# Option 2: Footer
git commit -m "refactor: remove deprecated functions

BREAKING CHANGE: old API is no longer available"
```

### 3. Testing & Validation

```bash
# Run full test suite
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/gleplot --cov-report=html

# Run specific test file
python -m pytest tests/unit/test_my_feature.py -v

# Run graphics compilation tests (slower)
python -m pytest tests/integration/test_graphics_compilation.py -v
```

### 4. Configuration Integration

#### User-Facing Customization

```python
# examples/using_config.py
import gleplot as glp
from gleplot.config import GlobalConfig, GLEStyleConfig

# Option 1: Global configuration
GlobalConfig.style.font = 'texcmr'
GlobalConfig.style.fontsize = 11
GlobalConfig.style.default_linewidth = 0.04

# Option 2: Per-figure configuration
style = GLEStyleConfig(
    font='rm',
    fontsize=10,
    default_linewidth=0.05
)
fig = glp.figure(figsize=(10, 8), style=style)

# Option 3: Per-element styling
ax.plot(x, y, color='blue', linewidth=0.06)
```

#### Configuration Documentation

- See [docs/guides/CONFIGURATION.md](../docs/guides/CONFIGURATION.md) for tutorial
- See [docs/guides/CONFIGURATION_API.md](../docs/guides/CONFIGURATION_API.md) for complete API reference
- See [examples/example_configuration.py](../examples/example_configuration.py) for examples

### 5. Version Management

Releases use [Python Semantic Release](https://python-semantic-release.readthedocs.io/)
via [`.github/workflows/release.yml`](../../.github/workflows/release.yml). After **Tests**
pass on `main`, the release workflow decides whether conventional commits since the last
tag warrant a bump.

#### Preview locally

```bash
pip install -e ".[dev]"
semantic-release version --noop
```

#### Performing a Release

```bash
# Automatic (recommended): push conventional commits to main
git push origin main
# Tests → Release (GitHub Release + wheel/sdist when a bump is needed)

# Manual workflow: Actions → Release → Run workflow (optional force bump)

# Manual local release (maintainers only)
semantic-release version
git push origin main --follow-tags
```

#### Versioning Documentation

- See [docs/guides/VERSIONING.md](../docs/guides/VERSIONING.md) for detailed guide
- See [docs/guides/VERSIONING_QUICK_REF.md](../docs/guides/VERSIONING_QUICK_REF.md) for quick reference
- See [examples/example_versioning_workflow.py](../examples/example_versioning_workflow.py) for examples

### 6. Publishing

#### Build Distribution

```bash
pip install build twine
python -m build
twine check dist/*
```

#### GitHub Actions Release and PyPI

The **Release** workflow builds distributions and attaches them to the GitHub Release.

PyPI upload is **off by default**. To enable it:

1. Register the gleplot project on PyPI (or TestPyPI first).
2. Add a **Trusted Publisher** on PyPI for this repository,
   workflow file `release.yml`, environment `pypi`.
3. Create a GitHub **Environment** named `pypi` (optional approval rules recommended).
4. Set repository variable `PYPI_PUBLISH` to `true`.

The **Publish to PyPI** job uses OIDC (`pypa/gh-action-pypi-publish`); no long-lived
API token is stored in the repository.

**Manual workflow dispatch:** Actions → **Release** → Run workflow.

## Complete Example Workflow

### Scenario: Add Feature & Release

```bash
# 1. Start from main
git checkout main
git pull

# 2. Create feature branch (optional)
git checkout -b feature/color-palettes

# 3. Write code with configuration support
cat > src/gleplot/palettes.py << 'EOF'
"""Color palette manager."""

class PaletteManager:
    """Manage custom color palettes."""
    
    def __init__(self, config):
        self.config = config
        self.palettes = {}
    
    def register_palette(self, name, colors):
        """Register a new color palette."""
        self.palettes[name] = colors
EOF

# 4. Write tests
cat > tests/unit/test_palettes.py << 'EOF'
import pytest
from gleplot.palettes import PaletteManager

def test_register_palette():
    """Test palette registration."""
    manager = PaletteManager(config=None)
    manager.register_palette('viridis', ['blue', 'green', 'yellow'])
    assert 'viridis' in manager.palettes
EOF

# 5. Test locally
git add src/gleplot/palettes.py tests/unit/test_palettes.py
python -m pytest tests/unit/test_palettes.py -v

# 6. Commit with semantic type
git commit -m "feat(colors): implement color palette system

- Add PaletteManager for managing color palettes
- Support custom palette registration
- Include viridis, cool, warm default palettes

See docs/guides/CONFIGURATION_API.md for usage"

# 7. Run full test suite
python -m pytest tests/ -q  # All 114 tests pass

# 8. Preview release (optional)
semantic-release version --noop

# 9. Push to main
git push origin main

# 10. After Tests pass, Release workflow bumps version, tags, and cuts GitHub Release

# 11. Pull updated version
git pull origin main --tags

# 12. Verify version
cat src/gleplot/__init__.py | grep __version__
# Output: __version__ = '0.1.0'
```

### Scenario: Bug Fix & Patch Release

```bash
# 1. Discover bug
# Tests are failing due to incorrect color conversion

# 2. Create fix
cat > src/gleplot/colors.py << 'EOF'
def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple."""
    # Fixed implementation
EOF

# 3. Write test to verify fix
cat > tests/unit/test_color_fix.py << 'EOF'
def test_hex_to_rgb():
    from gleplot.colors import hex_to_rgb
    assert hex_to_rgb('#FF0000') == (255, 0, 0)
EOF

# 4. Commit with fix: prefix
git add src/gleplot/colors.py tests/unit/test_color_fix.py
git commit -m "fix: correct hex to RGB color conversion

Previously returned incorrect values due to bit-shifting error.
Now handles both #RRGGBB and #RGB formats correctly."

# 5. Test
python -m pytest tests/ -q

# 6. Release
git push origin main
# Tests → Release creates patch tag when fix: commits are present
```

## Quick Commands Reference

### Development

```bash
# Setup
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -q           # Quick
python -m pytest tests/ -v           # Verbose
python -m pytest tests/unit/ -v      # Unit only
python -m pytest tests/integration/ -v  # Integration only

# Run examples
python examples/run_and_compile.py
python examples/example_configuration.py
python examples/example_versioning_workflow.py

# Check version
cat src/gleplot/__init__.py | grep __version__
```

### Committing

```bash
# Stage changes
git add <files>

# Commit with semantic type
git commit -m "feat: <description>"    # Minor bump
git commit -m "fix: <description>"     # Patch bump
git commit -m "docs: <description>"    # No bump
git commit -m "feat!: <description>"   # Major bump

# Push
git push origin <branch>
```

### Versioning

```bash
# Preview next release
semantic-release version --noop

# Manual local release (rare)
semantic-release version
git push origin main --follow-tags

# Or: Actions → Release → Run workflow
```

## Tips & Best Practices

**Do:**

- Write descriptive commit messages
- Use scopes: `feat(config):`, `fix(writer):`
- One logical change per commit
- Run tests before pushing
- Run `semantic-release version --noop` when unsure what will release
- Review your commits before pushing

**Don't:**

- Commit random changes without semantic type
- Mix features with fixes in one commit
- Push without running tests
- Use vague commit messages like "Update stuff"
- Forget to update tests for new features

## Troubleshooting

### Release workflow does nothing

```bash
git log --oneline "$(git describe --tags --abbrev=0 2>/dev/null || echo ROOT)..HEAD"
semantic-release version --noop
```

Ensure commits use `feat:`, `fix:`, or `perf:` (or a breaking-change marker) since the
last tag. Documentation-only pushes do not release.

### Tests fail after changes

```bash
# Run tests with detailed output
python -m pytest tests/ -vv --tb=long

# Run specific test
python -m pytest tests/unit/test_specific.py -vv

# Check test coverage
python -m pytest tests/ --cov=src/gleplot --cov-report=term-missing
```

### Version not updating

```bash
# Check current version
cat src/gleplot/__init__.py | grep __version__
cat pyproject.toml | grep version

# Verify commit history
git log --oneline -10

semantic-release version --noop

# Check for BREAKING CHANGE detection
git log -p
```

## Related Documentation

- [Semantic Versioning Guide](VERSIONING.md)
- [Configuration API Reference](CONFIGURATION_API.md)
- [Test Structure Guide](TEST_STRUCTURE.md)
- [Contributing Guidelines](../../CONTRIBUTING.md)
