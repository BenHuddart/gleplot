# Versioning and releases

gleplot follows [Semantic Versioning 2.0](https://semver.org/). Releases are
cut by [Python Semantic Release](https://python-semantic-release.readthedocs.io/)
from [conventional commit](https://www.conventionalcommits.org/) messages on
`main`, while the maintainer has the Release workflow enabled.

## Stability

6.0 is gleplot's first stable release. From 6.0 on, a public name or a
default changes only in a major release, and so does the GLE a script emits
when that output was correct. A minor adds capability, and a patch changes
emitted GLE only to correct output that was wrong.

## Gathering a major

To gather breaking changes into one major, the maintainer pauses releases by
disabling the Release workflow. While it is paused, commits still land on
`main` with their usual types, breaking (`!`) changes included, and nothing is
published. Re-enabling the workflow does not run it: the maintainer then runs
it by hand (**Actions → Release → Run workflow**, `auto`), and that run cuts
one release from every commit since the last tag, a single major if any of
them is breaking.

## Commit messages

```
<type>(<optional scope>): <subject>

<optional body>

<optional footer>
```

| Type | Version bump |
|------|--------------|
| `feat` | minor |
| `fix`, `perf` | patch |
| `feat!`, `fix!`, or a `BREAKING CHANGE:` footer | major |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore` | none |

Examples:

```bash
git commit -m "feat: add support for histogram plots"
git commit -m "fix(writer): handle edge case in scale auto"
git commit -m "docs: update installation instructions"
```

A breaking change:

```
feat!: remove deprecated plot_old() function

BREAKING CHANGE: plot_old() has been removed. Use plot() instead.
```

The bump rules live in `pyproject.toml` under
`[tool.semantic_release.commit_parser_options]`.

## How a release happens

1. A push to `main` runs the **Tests** workflow. Pull requests never cut a
   release.
2. When Tests succeed, that commit is still the tip of `main`, and the
   maintainer has not paused releases, the **Release** workflow
   ([`.github/workflows/release.yml`](https://github.com/benhuddart/gleplot/blob/main/.github/workflows/release.yml))
   looks at the commits since the last tag.
3. If they warrant a bump, python-semantic-release updates the version,
   prepends release notes to [`docs/CHANGELOG.md`](https://github.com/benhuddart/gleplot/blob/main/docs/CHANGELOG.md), builds
   the sdist and wheel, pushes the release commit and `vX.Y.Z` tag, and
   creates a GitHub Release with the artifacts attached.
4. If the repository variable `PYPI_PUBLISH` is `true`, a separate job uploads
   to PyPI through Trusted Publishing; see
   [Publishing to PyPI](#publishing-to-pypi).

The version is stored in two places, which the release keeps in sync:
`project.version` in `pyproject.toml` and `__version__` in
`src/gleplot/__init__.py`. Do not edit either by hand.

## Previewing and forcing a release

Preview what the next release would be, without writing anything:

```bash
pip install -e ".[dev]"
semantic-release version --noop
```

To release by hand, go to **Actions → Release → Run workflow** and choose
`auto` or force `major`, `minor` or `patch`.

Maintainers can also release locally, which is rarely needed:

```bash
semantic-release version
git push origin main --follow-tags
```

## Publishing to PyPI

Each release attaches the sdist and wheel to its GitHub Release, and the
**Publish to PyPI** job uploads the same files to
[PyPI](https://pypi.org/project/gleplot/). It runs in the GitHub
**Environment** `pypi`, which waits for a maintainer to approve the upload:
open the Release run under **Actions** and choose **Review deployments**.

The job authenticates through OIDC as a PyPI **Trusted Publisher**
(`pypa/gh-action-pypi-publish`, workflow file `release.yml`, environment
`pypi`), so no long-lived API token is stored in the repository. It runs only
while the repository variable `PYPI_PUBLISH` is `true`; set it to anything
else to keep releases on GitHub only.

To check a build locally:

```bash
pip install build twine
python -m build
twine check dist/*
```

## If the Release workflow does nothing

- Releases are paused: the maintainer has disabled the workflow to gather a
  major (see [Gathering a major](#gathering-a-major)).
- No commit since the last tag has a bumping type. `docs:`, `test:`, `ci:`
  and the like never release on their own.
- A newer commit reached `main` before Tests finished; that commit's run cuts
  the release instead.
- Tests failed.
