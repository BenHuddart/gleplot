# Contributing

Thanks for helping improve gleplot. This page covers what you need before opening a pull request. For versioning, releases, and day-to-day workflow, see [docs/guides/DEVELOPMENT_WORKFLOW.md](docs/guides/DEVELOPMENT_WORKFLOW.md).

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

Tests that shell out to the `gle` binary are skipped when GLE is not installed.

## Code style

Match the project tooling:

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/
```

## Commits

Use [conventional commits](https://www.conventionalcommits.org/) (`feat`, `fix`, `perf`, …). Releases use `python-semantic-release` (`feat` → minor, `fix`/`perf` → patch).

## Pull requests

1. Run the test suite and formatters above.
2. Add or extend tests for behavior you change.
3. Update user-facing docs when the API or workflows change.
4. Open a PR with a clear summary and test plan.

## Questions and bugs

Open a [GitHub issue](https://github.com/benhuddart/gleplot/issues) with steps to reproduce, expected vs actual behavior, and your Python/OS versions when reporting bugs.