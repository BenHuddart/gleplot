# Matplotlib Migration Guide

gleplot intentionally mirrors the matplotlib style for core plotting tasks.

## Quick Mapping

| matplotlib | gleplot |
|---|---|
| `plt.figure()` | `glp.figure()` |
| `fig.add_subplot(...)` | same |
| `ax.plot(...)` | same |
| `ax.scatter(...)` | same |
| `ax.errorbar(...)` | same |
| `ax.fill_between(...)` | same |
| `ax.set_xlabel(...)` | same |
| `ax.set_ylabel(...)` | same |
| `ax.set_title(...)` | same |
| `ax.legend(...)` | same |
| `plt.savefig(...)` | `fig.savefig(...)` or `glp.savefig(...)` |

## Minimal Porting Example

Matplotlib:

```python
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(x, y, color='blue', label='sin(x)')
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.legend()
fig.savefig('plot.pdf')
```

gleplot:

```python
import gleplot as glp
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

fig, ax = glp.subplots(figsize=(8, 5))
ax.plot(x, y, color='blue', label='sin(x)')
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.legend()
fig.savefig('plot.pdf')
```

## Legends

`ax.legend()` becomes GLE's graph-block `key` command. The kwargs that map
onto a `key` option are honoured; every other matplotlib legend kwarg raises
a `UserWarning` instead of being silently dropped.

`label=` on `bar` and `fill_between` is a real legend entry. GLE's `bar` and
`fill` commands have no `key` qualifier, so the swatch is a following dataset
line: `dN key "label"` for a bar (the bar fill is already the swatch) and
`dN keyfill COLOR key "label"` for a fill. `axvspan` / `axhspan` use the same
fill swatch.

| `legend()` kwarg | gleplot |
|---|---|
| `loc` | wired — all eleven matplotlib strings map onto GLE's nine key anchors (`key pos`). `'best'` is not computed; like matplotlib's own fallback it means top right. GLE short forms (`'tr'`, `'bl'`, …) are accepted too. An unrecognized value warns. |
| `fontsize` | wired — points converted to cm as `key ... hei`, using the same pt→cm conversion as `set hei`. matplotlib's relative names (`'small'`, `'x-large'`, …) resolve against the figure style's fontsize. |
| `frameon` | wired — `False` emits `key ... nobox`. |
| `ncol`/`ncols` | wired — entries in the order they were added, packed like matplotlib (column-major; the first columns are one entry longer). When that order is the order GLE draws the series, the breaks are `key separator` inside the graph. When it is not (a fill or a span is drawn before a bar or a line that was added first), the graph key is `key off` and a `begin key` after the graph lists the entries in addition order. `ncols` wins when both are passed. A count larger than the number of entries collapses to one entry per column, and a re-opened script reports that collapsed count. An integer below 1 raises `ValueError`. |
| `facecolor` | wired — the legend-box fill, emitted as GLE `background`. |
| `compact` | wired — gleplot/GLE flag, not a matplotlib name. `True` emits `compact` (line and marker share one swatch field). |
| handles/labels (first positional) | warns — legend text always comes from each series' `label=`. |
| `title`, `framealpha`, `edgecolor`, `shadow`, `bbox_to_anchor`, `markerscale`, `borderpad`, `labelspacing`, `boxcolor`, … | warn. `boxcolor` is not the box fill: in GLE it strokes the fill swatch. Absolute `justify` positioning is not modelled. |

```python
# an 8.6 cm journal column wants legend text smaller than the axis labels
ax.legend(loc='upper left', fontsize=6.5, frameon=False)
```

## Text

`ax.text(x, y, s)` places a label in data coordinates.

| `text()` argument | gleplot |
|---|---|
| `ha` | wired — `left`, `center`, `right` (`set just`). |
| `va` | wired — `top`, `center`, `bottom`. GLE has no baseline; `baseline` warns and is drawn as `center`. |
| `rotation` | wired — degrees counter-clockwise about the alignment point (`begin rotate`). |
| `bbox` | `facecolor` (alias `fill`) draws a filled background (`begin box fill`, 0.05 cm pad, no outline). `edgecolor`, `linewidth`, `pad`, `boxstyle`, and the rest warn. |
| other keywords (`transform`, `fontweight`, `clip_on`, …) | warn and are ignored. |

```python
ax.text(1, 2, "peak", va="bottom", rotation=45, bbox={"facecolor": "white"})
```

### Annotations

`ax.annotate(text, xy, xytext=..., arrowprops=...)` is a text at `xytext` with an arrow to `xy`, both in data coordinates. The text takes the `text()` keywords above. The arrow is GLE `join` from the text's named box to a saved point at `xy`, so it starts at the box edge (0.05 cm pad) rather than over the text. An `xy` inside the text's own box draws the arrow back across the text, where matplotlib draws nothing: keep `xytext` clear of the point.

| `annotate()` argument | gleplot |
|---|---|
| `xytext` | wired. Omitted: the text sits on `xy` and no arrow is drawn. |
| `xycoords`, `textcoords` | only `'data'`. Anything else (`'offset points'`, `'axes fraction'`, …) warns and the numbers are read as data. |
| `arrowprops['arrowstyle']` | `'-'`, `'->'`, `'<-'`, `'<->'` (GLE `simple` heads), `'-\|>'`, `'<\|-'`, `'<\|-\|>'` (GLE `filled` heads). No `arrowstyle` (the legacy `shrink`/`width` form) is `'-\|>'`. `'fancy'`, `'simple'`, `'wedge'` and unknown names warn and draw `'-\|>'`. Head-size parameters (`'->,head_width=0.4'`) warn. |
| `arrowprops` colour | `color`, else `edgecolor`/`ec`, else `facecolor`/`fc`: GLE draws one arrow colour. Default black. |
| `arrowprops['linewidth']` / `lw` | wired, in points (`set lwidth`). |
| `connectionstyle` | straight `arc3` only. Curved connections warn and are drawn straight. |
| `shrinkA`, `shrinkB`, `shrink`, `width`, `headwidth`, `headlength`, `linestyle`, `alpha`, `mutation_scale`, … | warn and are ignored. |
| `annotation_clip` | warns; the annotation is always drawn. |

```python
ax.annotate("peak", xy=(2, 3), xytext=(2.4, 3.5), arrowprops={"arrowstyle": "->"})
```

## Step and stem plots

GLE draws these as a mode on the same `dN line` command. The points stay in the data file; only the join changes.

| call | GLE |
|---|---|
| `ax.step(x, y)` / `where="pre"` / `drawstyle="steps"` or `"steps-pre"` | `line fsteps` (vertical, then horizontal) |
| `ax.step(x, y, where="post")` / `drawstyle="steps-post"` | `line steps` (horizontal, then vertical) |
| `ax.step(x, y, where="mid")` / `drawstyle="steps-mid"` | `line hist` (each point is a bin center) |
| `ax.stem(x, y)` | `line impulses`, with a filled-circle head |
| `ax.plot(..., line_mode="bar")` | `line bar` (histogram outline plus separators). This is not `ax.bar`. |

`line hist` is an outline through points that are already bin centres. Binning samples into counts is `Axes.hist`, below.

```python
ax.step(x, y, where="pre")
ax.plot(x, y, drawstyle="steps-mid")
ax.stem(x, y)
```

| argument | gleplot |
|---|---|
| `where` | `'pre'`, `'post'`, `'mid'`. Anything else raises `ValueError`. |
| `drawstyle` / `ds` | the five matplotlib names above. `'default'` is an ordinary line. An unknown value raises `ValueError`. |
| `step` format string | warns and is ignored. Pass `color`, `linestyle` and `marker` as keywords. |
| `linestyle="none"` together with a step style | warns. There is no line for the mode to qualify. `line_from_file` drops the mode the same way and still writes the line reference. |
| `GLEGraphConfig(smooth_curves=True)` | a step, stem, hist, bar or impulse series stays unsmoothed. GLE would spline the points first and then draw the mode through the spline. A script that writes both keywords keeps the smooth it asked for. |
| `stem` `linefmt` / `markerfmt` | color, linestyle and marker are applied. Stems and heads are one dataset, so two different colors warn and the line color wins. |
| `stem` `bottom` | warns unless it is `0`. GLE's origin is 0 when the y range includes 0, otherwise the range edge nearest 0. It is not matplotlib's baseline. |
| `stem` `basefmt` | warns, unless it asks for no baseline. No baseline is drawn. |
| `stem` `orientation="horizontal"` | warns. Impulses are vertical. |
| `stem` return value | the axes. There is no `StemContainer`. |
| `stem(data=...)`, `use_line_collection` | warn and are ignored. |

## Bars

`ax.bar(x, height)` emits `bar dN fill RED`. One GLE dataset has one face and one edge. A colour sequence therefore becomes one `bar` command per bar, and each of those carries an explicit width, because a one-point dataset has no gap for GLE to measure. A single colour, including the same colour repeated, stays one command.

`edgecolor`, `linewidth` and `linestyle` are the stroke: `color`, `lwidth` and `lstyle`. `edgecolor='none'` emits `lwidth 0` (GLE has no missing edge). `bottom` stacks the bar from that baseline to `bottom + height`, written `bar dTo from dFrom`. A zero baseline is not written. `ax.barh(y, width)` emits `horiz`. Its thickness is `height` and defaults to GLE's own derivation, not matplotlib's `0.8`. `align='edge'` warns and is drawn centered. `hatch` warns and is ignored.

`yerr` and `xerr` draw whiskers at the tip of each bar. A scalar or a length-n sequence is symmetric. Shape `(2, n)` is asymmetric (first row minus, second row plus); `(2, 1)` broadcasts. The whisker is a separate markerless error-bar series, because GLE's `horiz` swaps axes only while drawing the bar and an `err`/`herr` dataset is not swapped. A vertical bar's tip is `(x, bottom + height)`. A horizontal bar's tip is `(left + width, y)`. `yerr` stays vertical and `xerr` stays horizontal, so `barh(..., xerr=)` is a `herr` along the length.

`ecolor` defaults to black. One colour is one series; a sequence of different colours is one series per bar. `capsize` is the cap width in points (`errwidth` / `herrwidth`). Leave it out and GLE draws its own cap, one third of the font height. `capsize=0` is that same default: GLE reads a zero width as "not given". There is no way to omit the cap. `capsize_cm` is the width in centimetres and overrides `capsize`. `error_kw` may set `ecolor`, `capsize`, `capsize_cm` and `zorder` (the last wins, then 0.01 is added so the whisker sits above the bar). Other `error_kw` keys, including `elinewidth`, warn and are ignored: a markerless error dataset does not carry `lwidth`, so the stem uses the line width already in force. The bar's label is the only legend entry.

An autoscaled x axis now includes `xerr`, the way the y axis already included `yerr`. A horizontal whisker is not clipped by the `xaxis` gleplot writes. This applies to `errorbar` as well as to bars.

Two matplotlib calls with shifted x are two commands. A hand-written `bar d1,d2 fill c1,c2` is GLE's side-by-side group and round-trips as one command, `dist` included. `3d`, `pattern`, `style`, `side`, `top`, `notop` and `background` have no series field; the whole command stays raw GLE.

| call | GLE |
|---|---|
| `ax.bar(x, h, color='green', edgecolor='k')` | `bar dN fill GREEN color BLACK` |
| `ax.bar(x, h, color=['red', 'blue'])` | one `bar` per bar, explicit `width` |
| `ax.bar(x, h2, bottom=h1)` | `bar dTo from dFrom` |
| `ax.bar(x, h, yerr=e, capsize=3)` | `bar dN`, then `dM color BLACK err dE errwidth …` at the tip |
| `ax.barh(y, w, xerr=e)` | `bar dN horiz`, then `herr` at `(left + w, y)` |
| `ax.barh(y, w)` | `bar dN horiz` |

`width` stays a keyword. The third positional argument is `color`, as it has always been.

## Histograms

`ax.hist(samples, bins=20, range=(0, 1), histtype="step")` keeps the samples in the data file. GLE bins them with `let dK = hist dJ from 0 to 1 bins 20` and draws the counts. The heights are counts. The window is the data min and max when `range` is omitted, widened by half a unit when every finite sample is the same value, and it is always written into the `let` so GLE does not re-bin over the axis. A sample on the right edge falls in the last bin; samples outside the window are not counted. Non-finite samples are dropped, with a warning.

| `histtype` | GLE |
|---|---|
| `"step"` | `dK line hist`, with smoothing pinned off |
| `"stepfilled"` | `bar dK fill C color C width W`, one bin wide, from zero. `fill x1,dK` would chord the centres and fill to the axis minimum. The stroke matches the fill so the shared edge of two bins is not a second ink. |
| `"bar"`, `"barstacked"` | warn, and draw the step outline. Per-bar faces, edges, groups and stacks are `Axes.bar`. |

| argument | gleplot |
|---|---|
| `bins` | an integer, or equal-width edges. Unequal edges warn and are equalized over the first and last edge. `'auto'` and the other string rules warn and use 10 bins. |
| `density`, `weights`, `cumulative`, `bottom`, `stacked`, `rwidth` | warn and are ignored. The drawing stays counts from zero. |
| `align` | warns unless it is `'mid'`. GLE stores bin centres. |
| `orientation="horizontal"` | warns. The histogram is vertical. |
| `log=True` | sets the y axis to log. |
| `yaxis="y2"` | a step histogram can use it. A filled one warns and stays on the primary axis: `bar` has no `y2axis`. |
| `xaxis="x2"` | a step histogram can use the top scale. A filled one warns and stays on the primary x axis: `bar` has no `x2axis`. |
| return value | the axes. |

## Fills

`fill_between` still emits `fill dA,dB` for two curves. Three other GLE fill forms are available.

| call | GLE |
|---|---|
| `ax.fill_between(x, y1, y2)` | `fill dA,dB`. A scalar `y2` (the default `0`) is a constant second curve, so a curve that crosses it fills on both sides. |
| `ax.fill_between(x, y, baseline="x1")` | `fill x1,dN`. The region closes on the bottom of the y axis (GLE's x-axis), which is the axis minimum, not the line y=0. |
| `ax.fill_between(x, y, baseline="x2")` | `fill dN,x2`, closing on the top of the y axis. |
| `ax.fill_between(..., where=mask)` | one `fill` per contiguous run of True samples, clipped with `xmin` / `xmax`. |
| `ax.fill(x, y)` | `fill dN`. GLE closes the polygon. |

```python
ax.fill_between(x, y, where=(x > 0))
ax.fill_between(x, y, baseline="x1")
ax.fill(x, y, alpha=0.4)
```

| argument | gleplot |
|---|---|
| `where` | a boolean array the same length as `x`. A run is filled only where neighboring samples are both True, so one isolated True draws nothing. Each run is a clip window on the full curves, and the axis still covers the whole dataset: GLE autoscales from the points, not from the ink. `x` has to be finite and strictly monotonic (no repeated x); otherwise the mask is ignored, with a warning. |
| `interpolate` | `True` moves a clip edge to where the two curves cross beside that run (matplotlib's intersection, not a midpoint of the mask). An axis fill has no second curve, so this warns and the edge stays on the sample. |
| `xmin`, `xmax`, `ymin`, `ymax` | the same clip, in data coordinates. These are not `axvspan` fractions. On `baseline="x1"`, `ymin` is also the line the fill closes on: GLE uses that value as the baseline and clips below it. Do not pass `where` together with `xmin` or `xmax`. |
| `step` | warns and is ignored. `fill` has no step mode. |
| `fill_betweenx` | not available. These fill forms are vertical. |
| `fill` extra polygons | the first polygon is drawn. The rest warn and are ignored. |
| `edgecolor`, `linewidth` on `fill` | warn and are ignored. GLE fills the interior and does not stroke it. |
| `alpha` | unchanged: below 1 the colour is `rgba255(...)`. |

## Secondary axes

The right-hand scale is `yaxis="y2"` on a series, and `ax.twiny()` opens the top scale. Both are described in [Axes and Legends](AXES_AND_LEGENDS.md).

## Key Behavioral Differences

1. Primary output model is GLE script generation.
2. Saving to `.gle` always works without external compiler.
3. Saving to `.pdf`, `.png`, `.eps` requires a working GLE installation.
4. Sidecar `.dat` files are generated for in-memory series unless file-based series methods are used.
5. `ax.grid(visible, which=, axis=, color=, linestyle=, linewidth=)` maps to
   GLE's `xaxis grid` (+ `xsubticks on` for `which='both'`). A minor-only
   grid is not expressible and is normalized to both, with a warning.
6. Display strings follow matplotlib's contract: plain text renders literally
   (`'lambda_tail'` is not a subscript) and math is opt-in via `$...$`. Unlike
   matplotlib, a backslash outside `$...$` still opens GLE's own text markup
   (`r'\chi{}'`), as do braced scripts (`'T_{N}'`).

## Migration Strategy

1. Port plotting code with minimal edits (`plt` -> `glp`).
2. Validate scripts first by saving as `.gle`.
3. Add `data_prefix` for deterministic sidecar names in batch pipelines.
4. Replace custom file parsers with `errorbar_from_file()`/`line_from_file()` where possible.
5. Add project-specific style defaults via `GlobalConfig`.
