# CHANGELOG

<!-- version list -->

## v3.3.0 (2026-11-14)

### Features

- Emit step, stem, and histogram outlines as GLE line modes
  ([`45f91f8`](https://github.com/BenHuddart/gleplot/commit/45f91f801a0962bea3e017f7486bbd926b4ed3da))


## v3.2.0 (2026-11-14)

### Features

- Draw bar and fill labels in the legend
  ([`022ec15`](https://github.com/BenHuddart/gleplot/commit/022ec15729b14184470fdf21291c4bb44ab8d61e))

### Testing

- Expect a legend swatch on a labelled span
  ([`827c996`](https://github.com/BenHuddart/gleplot/commit/827c996c0595d72ba1d64f66cc10c99ae4ac3118))


## v3.1.0 (2026-11-14)

### Features

- Emit text vertical alignment, rotation, and backgrounds
  ([`c95857a`](https://github.com/BenHuddart/gleplot/commit/c95857a3b269539fe5e24912923365cc6563d914))

### Testing

- Refresh text annotation emission digests
  ([`cbb045c`](https://github.com/BenHuddart/gleplot/commit/cbb045ca0a0d531debbcd92777e145b1361b85f9))


## v3.0.0 (2026-11-14)

### Continuous Integration

- Simplify release to PSR v10 and gate PyPI
  ([`8359a69`](https://github.com/BenHuddart/gleplot/commit/8359a6977f885c43f9e5a6f6c3d12645d73663b0))

### Features

- Remove calibration v2
  ([`07c3d4e`](https://github.com/BenHuddart/gleplot/commit/07c3d4eba337c72b14d7f298a938793369b65fbb))

- Remove the desktop GUI
  ([`32eebc5`](https://github.com/BenHuddart/gleplot/commit/32eebc57687e5bc0ec44929d1f0ee5990827acea))


<!-- Hand-written notes for work that does not yet have a generated release
     section. python-semantic-release inserts new releases above this comment.
     Delete this section once a generated release covers the same changes. -->

## Unreleased

### Features

- `ax.legend()` honours `fontsize` (GLE `key ... hei`, points converted with
  the same pt→cm rule as `set hei`, including matplotlib's relative names) and
  `frameon` (`key ... nobox`); all eleven matplotlib `loc` strings now reach
  GLE's nine key anchors instead of five of them collapsing onto top right
- Every other matplotlib `legend()` keyword — and an unrecognized `loc`, and
  an explicit handles/labels sequence — warns instead of being silently
  dropped
- `ax.contour(X, Y, Z)` accepts matplotlib's 2-D `np.meshgrid` coordinate
  arrays; irregular grids, transposed (`indexing='ij'`) grids and shape
  mismatches each raise their own message

### Behaviour changes

- **Plain display strings now render literally.** GLE's text engine reads `_`
  and `^` as sub/superscripts and swallows braces, so `'lambda_tail'` used to
  render as "lambda" with a subscripted "tail" and `'{a, b}'` lost its braces.
  gleplot now follows matplotlib's contract — literal by default, math opt-in
  via `$...$` — and escapes `_`, `^`, `{` and `}` in every non-math segment of
  every display string (axis labels, titles, legend keys, annotations, tick
  labels).

  Still treated as GLE markup, so existing figures that use it are unaffected:
  a **backslash** (`r'\chi{} (emu/mol)'`, `'{\bf bold}'`) and a **braced**
  script (`'T_{N}'`, `'mol^{-1}'`). Only a *bare* `_`/`^` changed meaning. If
  you relied on `'T_N'` subscripting, write `'T_{N}'` or `r'$T_N$'`.

### Fixes

- `gleplot.calibration` hardens `glestudio-cal`/`glestudio-box`/`glestudio-tw`
  markers against spoofing: an optional per-invocation `nonce` on
  `instrument_script`/`inject_text_metrics`/`build_text_metric_script`
  (`new_calibration_nonce()` mints one) embeds `marker:<nonce>` in every
  printed record, and `parse_calibration_records(..., expected_nonce=...)`
  rejects any record whose marker lacks or mismatches it as a new `"spoofed"`
  `CalibrationWarning`, instead of letting it race the genuine record for the
  first-parsed slot. Fixes a hole where a `print "glestudio-cal ..."`
  smuggled into a document as passthrough text (axes ids travel in
  GLEstudio's `project.json` plaintext) could poison the data↔cm map before
  the real record — printed after the actual graph block — ever arrived.
  Opt-in: omitting `nonce`/`expected_nonce` reproduces prior behaviour
  exactly.

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
