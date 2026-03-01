# Documentation Index

Complete guide to all documentation files in the gleplot project.

## Core Documentation

### [README.md](../README.md)
Main project file with overview, quick start, and links to all documentation.

**Contains:**
- Project overview and features
- Quick start guide
- Installation instructions
- Key capabilities
- Documentation links
- Contributing guidelines
- License information

## Configuration System Documentation

### [CONFIGURATION.md](guides/CONFIGURATION.md)
Tutorial guide for using gleplot's configuration system.

**Contains:**
- Introduction to configuration
- Global configuration examples
- Per-figure configuration
- Per-element styling
- Real-world usage scenarios
- Integration with GLE features

### [CONFIGURATION_API.md](guides/CONFIGURATION_API.md)
Complete API reference for all configuration options.

**Contains:**
- GLEStyleConfig API (400+ lines)
- GLEGraphConfig API
- GLEMarkerConfig API
- GlobalConfig API
- All properties explained
- Default values documented
- Usage examples

## Semantic Versioning Documentation

### [VERSIONING.md](guides/VERSIONING.md)
Comprehensive semantic versioning guide.

**Contains:**
- Version format and meaning
- Conventional commits specification
- How to trigger version bumps
- Manual version bumping workflow
- GitHub Actions automation
- Version locations and sync
- Best practices
- References to semver.org and conventionalcommits.org

### [VERSIONING_QUICK_REF.md](guides/VERSIONING_QUICK_REF.md)
Quick reference for common versioning patterns.

**Contains:**
- Commit message examples
- Bump type cheat sheet
- Common commands
- Scenario-based examples
- Tips for new users

### [SEMANTIC_VERSIONING_IMPLEMENTATION.md](SEMANTIC_VERSIONING_IMPLEMENTATION.md)
Technical summary of the versioning system implementation.

**Contains:**
- System overview
- Components implemented
- Conventional commits support details
- Files updated automatically
- Git integration
- Usage scenarios
- Current status
- Next steps for users

## Development and Workflow Documentation

### [DEVELOPMENT_WORKFLOW.md](guides/DEVELOPMENT_WORKFLOW.md)
Complete development cycle guide integrating all practices.

**Contains:**
- Planning and setup
- Writing code with semantic intent
- Testing practices
- Configuration integration
- Version management workflow
- Publishing procedures
- Complete example workflows
- Troubleshooting tips
- Quick commands reference

### [TESTING_QUICK_REFERENCE.md](guides/TESTING_QUICK_REFERENCE.md)
Quick reference for running tests.

**Contains:**
- Common test commands
- Example usage
- Pytest basics
- Coverage reporting
- Graphics testing

### [TEST_STRUCTURE.md](guides/TEST_STRUCTURE.md)
Guide to test organization and architecture.

**Contains:**
- Test organization
- Unit tests structure
- Integration tests structure
- Graphics test structure
- Running specific tests
- Writing new tests

### [GRAPHICS_TESTING.md](guides/GRAPHICS_TESTING.md)
Complete guide for graphics testing capabilities.

**Contains:**
- Graphics compilation testing
- Output validation
- GLE script analysis
- Visual verification

### [GRAPHICS_TESTING_COMPLETE.md](guides/GRAPHICS_TESTING_COMPLETE.md)
Detailed implementation of graphics testing system.

### [GRAPHICS_TESTING_SUMMARY.md](guides/GRAPHICS_TESTING_SUMMARY.md)
Overview of graphics testing capabilities.

## Examples

### example_configuration.py
Demonstrations of configuration system usage with 5 scenarios.

### example_versioning_workflow.py
7 detailed versioning workflows with examples:
- Bug fix release (patch)
- Feature release (minor)
- Breaking change (major)
- Mixed releases
- Documentation-only releases
- GitHub Actions automation
- Manual version control

### run_and_compile.py
Script to run and compile all basic examples.

## File Structure

```
gleplot/
├── README.md                          # Main documentation entry point
├── docs/
│   ├── SEMANTIC_VERSIONING_IMPLEMENTATION.md
│   └── guides/
│       ├── CONFIGURATION.md
│       ├── CONFIGURATION_API.md
│       ├── VERSIONING.md
│       ├── VERSIONING_QUICK_REF.md
│       ├── DEVELOPMENT_WORKFLOW.md
│       ├── TESTING_QUICK_REFERENCE.md
│       ├── TEST_STRUCTURE.md
│       ├── GRAPHICS_TESTING.md
│       ├── GRAPHICS_TESTING_COMPLETE.md
│       └── GRAPHICS_TESTING_SUMMARY.md
├── examples/
│   ├── example_configuration.py
│   ├── example_versioning_workflow.py
│   ├── run_and_compile.py
│   └── gleplot_examples.py
└── scripts/
    └── bump_version.py               # Semantic versioning automation
```

## How to Navigate

### If you want to...

**Get started quickly**
→ Read [README.md](../README.md) then [DEVELOPMENT_WORKFLOW.md](guides/DEVELOPMENT_WORKFLOW.md)

**Configure gleplot**
→ Read [CONFIGURATION.md](guides/CONFIGURATION.md) then [CONFIGURATION_API.md](guides/CONFIGURATION_API.md)

**Release a new version**
→ Read [VERSIONING.md](guides/VERSIONING.md) or [VERSIONING_QUICK_REF.md](guides/VERSIONING_QUICK_REF.md)

**Set up development environment**
→ Read [DEVELOPMENT_WORKFLOW.md](guides/DEVELOPMENT_WORKFLOW.md)

**Run tests**
→ Read [TESTING_QUICK_REFERENCE.md](guides/TESTING_QUICK_REFERENCE.md)

**Understand test structure**
→ Read [TEST_STRUCTURE.md](guides/TEST_STRUCTURE.md)

**Test graphics compilation**
→ Read [GRAPHICS_TESTING.md](guides/GRAPHICS_TESTING.md)

**Understand implementation**
→ Read [SEMANTIC_VERSIONING_IMPLEMENTATION.md](SEMANTIC_VERSIONING_IMPLEMENTATION.md)

## Documentation Standards

All documentation follows these principles:

- **Clear**: Easy to understand for both beginners and experts
- **Complete**: Comprehensive coverage of features
- **Practical**: Real examples and use cases
- **Organized**: Logical sections and navigation
- **Linked**: Cross-references between related docs
- **Maintained**: Updated with code changes

## Contributing Documentation

When adding features:

1. Update relevant guide (e.g., CONFIGURATION_API.md)
2. Add example to examples/ directory
3. Update this index if creating new docs
4. Keep documentation synchronized with code

## Version Information

- **gleplot Version**: See [src/gleplot/__init__.py](../src/gleplot/__init__.py)
- **Documentation Last Updated**: See recent git commits
- **Versioning System**: See [SEMANTIC_VERSIONING_IMPLEMENTATION.md](SEMANTIC_VERSIONING_IMPLEMENTATION.md)

---

For questions or issues with documentation, please open an issue on GitHub.
