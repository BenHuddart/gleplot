## Local Development Workflow

This project maintains a clean repository by not tracking test or example outputs.

### Running Tests Locally

Tests run against your local code and can generate output files for inspection:

```bash
# Run the main test suite (outputs go to tests/)
pytest tests/ -v

# Run test validation graphics (for visual inspection)
python generate_test_graphics.py
# Outputs: test_graphics_output/*.gle, test_graphics_output/*.dat, etc.
```

**Important:** These output files are ignored by git and can be safely removed.

### Running Examples Locally

Examples showcase gleplot features and generate output files in `examples/outputs/`:

```bash
# Generate example GLE files only
python examples/run_all.py
# Outputs: example_*.gle files in current directory

# Generate examples with PDF/PNG compilation (requires GLE to be installed)
cd examples
python run_and_compile.py
# Outputs: examples/outputs/*.gle, *.pdf, *.png, *.eps files
```

**Important:** Example outputs in `examples/outputs/` are also ignored by git.

### Cleaning Up Local Outputs

Remove all uncommitted outputs (test and example files):

```bash
# Remove untracked files and directories
git clean -fdx

# Or selectively:
rm -rf test_graphics_output/ test_custom_prefix_output/
rm -rf examples/outputs/
```

### CI/CD Pipeline (GitHub Actions)

The documentation build on release:
1. Runs test validation graphics
2. Runs all examples  
3. Compiles outputs to PDF and PNG
4. Generates gallery images and embeds them in published docs

You don't need to commit or track these outputs—GitHub Actions handles it!

### Summary

- **Local testing**: Outputs are ephemeral, use `git clean` to remove
- **Local examples**: Same as above, outputs in `examples/outputs/`
- **Documentation builds**: GitHub Actions runs everything and publishes clean docs
- **Repository**: Always clean, no generated files ever committed
