# Guides

This directory contains detailed guides and documentation for various aspects of gleplot.

## API and Usage Documentation

### [VIEW_FUNCTION.md](VIEW_FUNCTION.md)
Complete guide for the `view()` function for inline display in Jupyter notebooks.

**Contents:**
- Usage examples
- Parameters and options
- Jupyter integration
- Comparison with savefig()
- Tips and best practices

### [TEXT_ANNOTATIONS.md](TEXT_ANNOTATIONS.md)
Guide for data-coordinate text labels, alignment controls, and callout boxes.

**Contents:**
- Basic `text()` usage
- Alignment (`ha`/`va`) options
- Boxed annotations
- Convenience API patterns

### [FILE_BASED_SERIES.md](FILE_BASED_SERIES.md)
Guide for plotting directly from existing data files.

**Contents:**
- `errorbar_from_file()` patterns
- `line_from_file()` overlays
- 1-based column indexing
- Data format and workflow notes

### [COLORS_AND_MARKERS.md](COLORS_AND_MARKERS.md)
Reference for accepted color and marker mappings.

**Contents:**
- Matplotlib-to-GLE color mapping
- Supported named colors
- Marker symbol mapping
- Native GLE marker names

### [MATPLOTLIB_MIGRATION.md](MATPLOTLIB_MIGRATION.md)
Quick-start migration guide from matplotlib plotting code.

**Contents:**
- API mapping table
- Porting examples
- Behavioral differences
- Migration strategy

### [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
Common issues and practical fixes for save/compile/layout workflows.

**Contents:**
- Missing GLE executable
- Compilation failures
- Sidecar naming issues
- Shared-axis and layout behavior

## Testing Documentation

### [TESTING_QUICK_REFERENCE.md](TESTING_QUICK_REFERENCE.md)
Quick reference guide with common testing commands and examples. Start here for fast answers.

**Contents:**
- Quick test commands
- Timing information
- Quick troubleshooting
- Essential references

### [TEST_STRUCTURE.md](TEST_STRUCTURE.md)
Complete documentation of the test suite architecture and organization.

**Contents:**
- Test organization (unit, integration, graphics)
- Directory structure
- Test categories and purposes
- File organization

### [GRAPHICS_TESTING_SUMMARY.md](GRAPHICS_TESTING_SUMMARY.md)
Overview of the graphics testing implementation and capabilities.

**Contents:**
- Graphics testing features
- Test count and coverage
- File list and purposes
- CI/CD integration

### [GRAPHICS_TESTING.md](GRAPHICS_TESTING.md)
Complete user guide for graphics testing with examples and API documentation.

**Contents:**
- Installation and setup
- Running graphics tests
- Test examples
- Advanced usage
- Troubleshooting
- Custom script usage

### [GRAPHICS_TESTING_COMPLETE.md](GRAPHICS_TESTING_COMPLETE.md)
Implementation details and completion summary of the graphics testing feature.

**Contents:**
- Implementation phases
- Files created and modified
- Feature checklist
- Future enhancements

---

## Related Documentation

- **Project Root**: [README.md](../../README.md) - Main project documentation
- **Versioning**: [docs/VERSIONING.md](../VERSIONING.md) - Version management
- **Changelog**: [docs/CHANGELOG.md](../CHANGELOG.md) - Project history
