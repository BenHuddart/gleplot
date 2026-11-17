# Contributing

Thanks for helping improve gleplot. This page covers what you need before opening a pull request. For commit types and how releases are cut, see [docs/guides/VERSIONING.md](docs/guides/VERSIONING.md).

## Setup

```bash
git clone https://github.com/benhuddart/gleplot.git
cd gleplot
pip install -e ".[dev]"
```

## Tests

```bash
pytest tests/ -v
```

Tests that shell out to the `gle` binary are marked `@pytest.mark.gle` and are skipped when GLE is not installed. See [docs/guides/TESTING.md](docs/guides/TESTING.md) for the test layers and the fixed-point check.

## Code style

CI checks black, isort, flake8 and mypy, and all four must pass. gleplot supports Python 3.9+; the formatters and mypy need 3.10+.

```bash
black src tests examples docs
isort src tests examples docs
flake8 src tests examples docs
mypy src
```

## Docs and examples

CI runs every example and builds the Sphinx site with warnings treated as errors, so a malformed docstring or a broken example fails the pull request. To check locally (GLE required for the gallery images):

```bash
pip install -e ".[dev,docs]"
python examples/run_and_compile.py
mkdir -p docs/source/_static/gallery
cp examples/outputs/example_*.png docs/source/_static/gallery/
sphinx-build -W --keep-going -b html docs/source docs/build/html
```

`examples/run_and_compile.py` holds the one list of examples. Add a new example there: the run fails on an `example_*` function under `examples/basic/` or `examples/advanced/` that is not listed. Without GLE, `python examples/run_and_compile.py --no-compile` runs the examples without compiling them. The runner writes into `examples/outputs/`, which is ignored, and an example writes to the current directory rather than next to its own source. No generated figure or data file is committed, so running the examples leaves `git status` clean.

## Commits

Use [conventional commits](https://www.conventionalcommits.org/). The type decides the release; [docs/guides/VERSIONING.md](docs/guides/VERSIONING.md) lists what each one does.

## Pull requests

1. Run the test suite and formatters above.
2. Add or extend tests for behavior you change.
3. Update user-facing docs when the API or workflows change.
4. Open a PR with a clear summary and test plan.

## Questions and bugs

Open a [GitHub issue](https://github.com/benhuddart/gleplot/issues) with steps to reproduce, expected vs actual behavior, and your Python/OS versions when reporting bugs.