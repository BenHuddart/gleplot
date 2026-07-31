# CHANGELOG

## v1.9.0 (2026-07-31)

### Features

- `Figure.add_broken_xaxes` — split/broken x-axis figures, rendered as
  independent GLE subplot segments with a shared y-axis and configurable
  divider style (double-slash, single rule, or none)
- `axhline`/`axvline`/`axhspan`/`axvspan` as first-class `Axes` methods,
  matplotlib-compatible reference lines and shaded spans
- `Axes.set_xticks`/`set_yticks` accept `dticks`/`dsubticks` for explicit
  major/minor tick spacing
- `height_ratios`/`width_ratios` on `Figure`/`glp.figure`/`glp.subplots` for
  matplotlib-`gridspec`-style uneven subplot grids
- Open (outline) and white-filled marker variants, selected via `fillstyle`
  or `markerfacecolor`/`mfc` on `plot`, `scatter`, and `errorbar`
- `scatter` accepts `markersize` (matplotlib `Line2D` diameter convention)
  alongside its existing `s` (area) convention; passing both prefers
  `markersize`
- Every matplotlib string marker code is now mapped to a GLE glyph

### Fixes

- Colours are emitted as exact `rgb255(...)` values instead of being snapped
  onto the nearest of ~8 named GLE colours
- Line series are drawn as the data itself rather than a spline through it
  unless smoothing is explicitly requested (`GLEGraphConfig.smooth_curves`
  now defaults to `False`)
- Line styles use the GLE line-style numbers that actually render as their
  names say (dashed, dotted, and dash-dot no longer render as each other)
- Error bars and their caps consistently take the series colour, including
  bars-only error series
- `Figure(data_prefix=...)` is validated instead of silently producing GLE
  scripts that fail to parse

## v1.0.1 (2026-03-03)

### Improvements

- Gallery updated to use example outputs instead of test suite outputs
- All gallery code snippets now match the actual example source files
- New examples added: conditional `fill_between` (with `where=`), combined X+Y error bars,
  side-by-side subplots (1×2), stacked subplots (2×1), 2×2 mixed-type subplot grid, 1×3 comparison
- Documentation homepage now includes prominent links to the GitHub repository
- GitHub Pages deployment workflow fixed (`fetch-tags: true`)

## v0.0.1 (2026-03-01)

### Features

- Initial release of gleplot
- Matplotlib-compatible API for creating GLE plots
- Support for line plots, scatter plots, bar charts, and fill_between
- Full axis customization (labels, limits, scales, grid)
- Color and marker mappings compatible with matplotlib
- Direct compilation to PDF, PNG, and EPS via GLE
- Export to GLE scripts for manual editing
- Comprehensive test suite with 34 tests
- Sphinx documentation with GitHub Actions publishing
- Examples gallery demonstrating various plot types
