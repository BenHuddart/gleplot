# Matplotlib Migration Guide

gleplot writes standard GLE through matplotlib's names where they map
cleanly: a matplotlib function keeps matplotlib's parameter names, order and
defaults. Where GLE has no command for what a keyword asks, gleplot does not
emulate it: it accepts the keyword, warns, and this page lists the gap. An
unknown keyword name warns the same way. An argument value gleplot cannot
use, such as an unknown colour or a NaN line width, raises `ValueError` or
`TypeError` when the call is made.

## Quick Mapping

| matplotlib | gleplot |
|---|---|
| `plt.figure()` | `glp.figure()` |
| `plt.close(fig)` / `plt.close('all')` | same; gleplot tracks only the current figure, so `'all'` closes that one, and a figure number or label matches nothing and warns |
| `plt.subplots(nrows, ncols)` | `glp.subplots(nrows, ncols)`: the same numpy array of axes, with `squeeze`, see [Figures and Subplots](FIGURES_AND_SUBPLOTS.md). `subplot_kw` goes to each `add_subplot`; from `gridspec_kw`, the ratios and the `subplots_adjust` spacings are used. Other `gridspec_kw` keys, and figure keywords such as `num` or `layout`, warn |
| `fig.add_subplot(...)` | same, including a `(first, last)` index that spans cells, `polar=True` and `facecolor`; other axes-property keywords warn, see [Figures and Subplots](FIGURES_AND_SUBPLOTS.md) |
| `fig.add_axes(rect)` | same for a rect in figure fractions; the inset has no background unless given `facecolor`, and the other axes-property keywords warn, see [Figures and Subplots](FIGURES_AND_SUBPLOTS.md) |
| `fig.axes` | same, but without the `twinx()`/`twiny()` views, which draw on their parent's graph |
| `ax.plot(...)` | same |
| `ax.scatter(...)` | same, with matplotlib's positional order `scatter(x, y, s, c)` and every other argument keyword-only, including `c=` for per-point colours, see [Scatter colours](#scatter-colours) |
| `ax.errorbar(...)` | same |
| `ax.fill_between(...)` | same |
| `ax.fill_betweenx(...)` / `ax.stackplot(...)` | same, see [Fills](#fills) |
| `ax.hlines(...)` / `ax.vlines(...)` | same, see [Segments](#segments) |
| `ax.pie(...)` / `ax.boxplot(...)` | not provided, see [Not provided](#not-provided) |
| `ax.pcolormesh(...)` | same on a uniform grid, see [Cells](#cells) |
| `ax.contourf(...)` | same on a uniform grid, see [Filled contours](#filled-contours) |
| `fig.colorbar(im, ax=ax)` | same, see [Colorbars](#colorbars) |
| `fig.add_subplot(projection='polar')` | same, lines, scatters and function curves, see [Polar axes](#polar-axes) |
| `ax.set_xlabel(...)` | same; `fontsize`, `color` and `labelpad` are honoured, other text keywords warn; `labelpad` is keyword-only, since the second positional argument is gleplot's `axis` (`'x'`/`'x2'`, `'y'`/`'y2'`; another string raises). A dict there is taken as matplotlib's positional `fontdict` |
| `ax.set_ylabel(...)` | same as `set_xlabel` |
| `ax.set_xlim(...)` / `ax.set_ylim(...)` | same, including `left`/`right`, `bottom`/`top`, a `(low, high)` pair and the `xmin`/`xmax`, `ymin`/`ymax` aliases; an omitted limit keeps its setting. A limit passed as `None` is automatic, chosen from the data when the figure is saved, where matplotlib keeps the current value. `emit=False` and `auto=True` warn, and a NaN, infinite or non-numeric limit raises. The third positional argument is gleplot's `axis` (`'x2'`, `'y2'`) |
| `ax.set_title(...)` | same; `fontsize`, `color` and `pad` are honoured, `fontdict`, `y` and other text keywords warn |
| `plt.xlabel(...)` / `plt.ylabel(...)` / `plt.title(...)` | `glp.xlabel(...)` / `glp.ylabel(...)` / `glp.title(...)`, with matplotlib's positional order and the same keywords as the `ax.set_*` calls; `fig.xlabel`, `fig.ylabel` and `fig.title` take those keywords too. |
| `ax.spines[...].set_color(c)` / `.set_linewidth(w)` | `ax.set_axis_line(axis, color=c, linewidth=w)` |
| `ax.spines[...].set_visible(False)` | `ax.set_axis_line(axis, visible=False)`, with `'x'`, `'y'`, `'x2'`, `'y2'` for bottom, left, top, right |
| `ax.spines['left'].set_position('zero')` and `ax.spines['bottom'].set_position('zero')` | `ax.set_math_mode()` |
| `ax.legend(...)` | same |
| `ax.twinx()` / `ax.twiny()` | same, a view of the right or top scale, see [Secondary axes](#secondary-axes); their `axes_class`, `delta_zorder` and other keywords warn |
| `ax.invert_xaxis()` / `ax.invert_yaxis()` | same; automatic limits are fixed to the data plotted so far, so plot first. On a `twinx()`/`twiny()` view, set the limits first |
| `ax.semilogx(...)` / `semilogy` / `loglog` | same; `base` other than 10, `subs` and `nonpositive` warn |
| `ax.set_xticklabels(labels)` / `set_yticklabels` | same, after `set_xticks(ticks)`; `minor=True` and text properties warn |
| `ax.axis('off')` / `ax.set_axis_off()` | same, but the axis labels stay (with a warning); `'equal'`, `'scaled'`, `'image'`, `'square'` and `emit=False` warn, use `set_aspect` |
| `ax.set_facecolor(color)` | same, as GLE's graph `background`; an axes has none until it is set, where matplotlib's is white. On a polar axes it warns and does nothing: GLE's background fills the rectangular window, not the circle |
| `ax.set_aspect(...)` / `ax.get_aspect()` | same, resizing the box about its centre; `adjustable='datalim'`, an `anchor` other than `'C'` and `share=True` warn, see [Axes and Legends](AXES_AND_LEGENDS.md) |
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

## Default colours

A series given no colour takes the next of matplotlib's `'C0'` to `'C9'`, per axes, where matplotlib would: lines (`plot`, `step`, `errorbar`, `hist`, `stackplot`) and patches (`scatter`, `bar`, `barh`, `fill`, `fill_between`, `fill_betweenx`) have separate cycles, `stem`, `hlines` and `vlines` draw in `'C0'`, and a `twinx()`/`twiny()` view has cycles of its own. A colour that is given takes nothing from the cycle. The rules are in the [`GLEStyleConfig`](https://benhuddart.github.io/gleplot/api_configuration.html#gleplot.GLEStyleConfig) reference. A figure opened with `open_gle` continues each cycle after the series whose colours follow it.

To draw every uncoloured line, histogram and function curve in one colour, and every uncoloured marker in another, set `GLEStyleConfig(default_color=..., default_marker_color=...)`. Bars, fills and `stackplot` layers always take the cycle.

## Legends

`ax.legend()` becomes GLE's graph-block `key` command. The kwargs that map
onto a `key` option are honoured; every other matplotlib legend kwarg raises
a `UserWarning` instead of being silently dropped.

An axes with a labelled series draws a legend even if `ax.legend()` is never
called; matplotlib draws none until it is. Leave `label=` off a series to keep
it out of the legend, or, as in matplotlib, give it a label that starts with an
underscore, such as `'_nolegend_'`. That series keeps its label and writes it
as its `key`, so `open_gle` reads it back, but it is no legend entry: an axes
whose only labels start with an underscore draws no legend (`key off`), and one
with other labels too lists them in a `begin key` block after the graph,
because GLE's own key lists every dataset with a `key`.

`label=` on `bar` and `fill_between` is a real legend entry. GLE's `bar` and
`fill` commands have no `key` qualifier, so the swatch is a following dataset
line: `dN key "label"` for a bar (the bar fill is already the swatch) and
`dN keyfill COLOR key "label"` for a fill. `axvspan` / `axhspan` use the same
fill swatch.

GLE outlines every fill swatch in the key's colour, so the swatch of a bar
with no edge keeps a black border, and one with an edge is not outlined in
that edge's colour. GLE's `boxcolor` sets that outline for the whole key, not
for one entry. A bar with `color='none'` has no swatch at all: GLE draws a
swatch only for a fill it can see. With an `edgecolor` and a `label`, where
matplotlib would show the outline, that warns.

| `legend()` kwarg | gleplot |
|---|---|
| `loc` | wired — all eleven matplotlib strings map onto GLE's nine key anchors (`key pos`). `'best'` is not computed; like matplotlib's own fallback it means top right. GLE short forms (`'tr'`, `'bl'`, …) are accepted too. An unrecognized value warns. |
| `fontsize` | wired — points converted to cm as `key ... hei`, using the same pt→cm conversion as `set hei`. matplotlib's relative names (`'small'`, `'x-large'`, …) resolve against the figure style's fontsize. |
| `frameon` | wired — `False` emits `key ... nobox`. |
| `ncol`/`ncols` | wired — entries in the order they were added, packed like matplotlib (column-major; the first columns are one entry longer). When that order is the order GLE draws the series, the breaks are `key separator` inside the graph. When it is not (a fill or a span is drawn before a bar or a line that was added first), the graph key is `key off` and a `begin key` after the graph lists the entries in addition order. `ncols` wins when both are passed. A count larger than the number of entries collapses to one entry per column, and a re-opened script reports that collapsed count. An integer below 1 raises `ValueError`. |
| `facecolor` | wired — the legend-box fill, emitted as GLE `background`. |
| `compact` | wired — gleplot/GLE flag, not a matplotlib name. `True` emits `compact` (line and marker share one swatch field). |
| `bbox_to_anchor` | wired — `(x, y)` or `(x, y, width, height)` in axes fractions; the `loc` corner of the legend sits on that point (or on that corner of the box). Written as `justify` and `absolute` in a `begin key` after the graph, reading GLE's `xg()`/`yg()` of the graph just drawn, so it holds on log and inverted axes. Like `loc`, it applies to the call that passes it. The page does not grow to fit a legend placed outside the graph: leave room with `figsize` or `subplots_adjust`. `offset`, and the `GLEGraphConfig` legend offset, have no effect while an anchor is set, and warn. |
| `borderpad`, `handlelength`, `handletextpad`, `columnspacing` | wired — font-size units, as in matplotlib, written in cm as GLE `margins`, `llen`, `dist` and `coldist`. GLE's `dist` is also the gap between a marker and a line swatch. |
| `labelcolor` | wired — one colour, written as `textcolor` on every entry of a `begin key` after the graph. `'linecolor'`, `'markerfacecolor'`, `'markeredgecolor'` and a list of colours warn and are ignored. |
| handles/labels (first positional) | warns — legend text always comes from each series' `label=`. |
| `title`, `labelspacing`, `framealpha`, `edgecolor`, `shadow`, `markerscale`, `bbox_transform`, `boxcolor`, … | warn. GLE's key has no title; a text-only entry would sit in the label column of the first column, not above the legend. GLE's row height (`row`) also rescales the margins, line length and gaps, so it is not `labelspacing`. `boxcolor` is not the box fill: in GLE it strokes the fill swatch. |

```python
# an 8.6 cm journal column wants legend text smaller than the axis labels
ax.legend(loc='upper left', fontsize=6.5, frameon=False)

# beside the graph, with shorter line swatches and grey text
ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0), handlelength=1.5,
          labelcolor='gray')
```

## Text

`ax.text(x, y, s)` places a label in data coordinates, or in fractions of the
axes frame with `transform=ax.transAxes`.

| `text()` argument | gleplot |
|---|---|
| `ha` | wired — `left`, `center`, `right` (`set just`). |
| `va` | wired — `top`, `center`, `bottom`: the vertical half of `set just` (`tc`, `bc`, `bl`, …). With the default `center`, GLE's single-word `left`, `center` and `right` are used, which GLE centres vertically. GLE has no baseline; `baseline` warns and is drawn as `center`. |
| `rotation` | wired — degrees counter-clockwise about the alignment point (`begin rotate`). |
| `bbox` | `facecolor` (alias `fill`) draws a filled background (`begin box fill`, 0.05 cm pad, no outline). `edgecolor`, `linewidth`, `pad`, `boxstyle`, and the rest warn. |
| `transform` | `ax.transAxes` places the text in axes fractions: `(0, 0)` is the bottom-left corner of the frame and `(1, 1)` the top-right, on a log or inverted axis too. `ax.transData` is the default. Any other transform, including another axes' `transAxes`, warns and the position is read as data coordinates. |
| other keywords (`fontweight`, `clip_on`, …) | warn and are ignored. |

```python
ax.text(1, 2, "peak", va="bottom", rotation=45, bbox={"facecolor": "white"})
ax.text(0.05, 0.95, "(a)", transform=ax.transAxes, va="top")  # panel label
```

matplotlib's `text.usetex` is `GLEStyleConfig(usetex=True)`, set for the
figure rather than in `rcParams`; see the
[Configuration Guide](CONFIGURATION.md). There is no per-text `usetex=`
keyword.

GLE draws the text of a figure with a semi-transparent colour in its
`texcmr` font, unless the figure sets another `texcm*` font. In `texcmr`, `<`, `>`, `_` and some Unicode characters draw as other glyphs. Saving
warns; the [Configuration Guide](CONFIGURATION.md) lists the markup to write
instead.

### Figure-level text and legend

`fig.suptitle`, `fig.text` and `fig.legend` work on the whole page, as in
matplotlib. They are written after every axes, so they sit on top of them.

| Call | gleplot |
|---|---|
| `fig.suptitle(t)` | centred at `x=0.5`, `y=0.98`, `va='top'`, size `'large'` (1.2 times the figure font size), as matplotlib. `x`, `y`, `ha`, `va`, `fontsize`, `color`, `rotation` and `bbox` are honoured; other keywords warn. A second call replaces the title. Unlike matplotlib, the layout lowers the axes to leave room for the title, unless `subplots_adjust(top=...)` sets that edge. |
| `fig.text(x, y, s)` | `x`, `y` in figure fractions: `(0, 0)` is the bottom-left corner of the page. Takes the `text()` keywords above, and `fontdict`. A `transform` warns: the position is always in figure fractions. |
| `fig.legend()` | one legend listing the labelled series of every axes, axes by axes, each axes' series in the order they were added. While it exists, an axes draws its own legend only if `ax.legend()` was called on it. `loc` is a corner of the page (default `'upper right'`; `'best'` raises `ValueError`, as in matplotlib); `bbox_to_anchor` is in figure fractions. `ncol`/`ncols`, `fontsize`, `frameon`, `facecolor`, `labelcolor`, `borderpad`, `handlelength`, `handletextpad` and `columnspacing` are as for `ax.legend()`. The legend sits half a font size in from the page edges its corner is anchored to (matplotlib's default `borderaxespad`); `borderaxespad`, handles/labels and the other keywords warn. A second call replaces the legend rather than adding another. The layout does not make room for it: leave room with `subplots_adjust`. |

```python
fig, axes = glp.subplots(1, 2)
fig.suptitle("Sample A")
fig.text(0.02, 0.98, "(a)", ha="left", va="top")
fig.legend(loc="lower center", ncol=3)
fig.subplots_adjust(bottom=0.2)
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
| `step` format string | read as `plot` reads it. |
| `linestyle="none"` together with a step style | warns. There is no line for the mode to qualify. `line_from_file` drops the mode the same way and still writes the line reference. |
| `GLEGraphConfig(smooth_curves=True)` | a step, stem, hist, bar or impulse series stays unsmoothed. GLE would spline the points first and then draw the mode through the spline. A script that writes both keywords keeps the smooth it asked for. |
| `stem` `linefmt` / `markerfmt` | color, linestyle and marker are applied. Stems and heads are one dataset, so two different colors warn and the line color wins. |
| `stem` `bottom` | warns unless it is `0`. GLE's origin is 0 when the y range includes 0, otherwise the range edge nearest 0. It is not matplotlib's baseline. |
| `stem` `basefmt` | warns, unless it asks for no baseline. No baseline is drawn. |
| `stem` `orientation="horizontal"` | warns. Impulses are vertical. |
| `stem` return value | the axes. There is no `StemContainer`. |
| `stem(data=...)`, `use_line_collection` | warn and are ignored. |

## Segments

`ax.vlines(x, ymin, ymax)` and `ax.hlines(y, xmin, xmax)` are line datasets: one per distinct colour, line style and width, with a missing value (`*`) between segments. The arguments are listed in the API reference for `Axes.vlines`. GLE breaks a line at `*` and drops a `nan` row, joining its neighbours, so `ax.plot` and `ax.step` write a NaN in a drawn line as `*`: the line breaks there, as in matplotlib. So does a line whose data comes from a `data_provider` at `savefig`. Such a line is not smoothed by `GLEGraphConfig(smooth_curves=True)`, which would fit one curve through the pieces.

| argument | gleplot |
|---|---|
| a dash tuple in `linestyles` | warns and is drawn solid. |
| `alpha` and other `LineCollection` keywords | warn and are ignored. |
| return value | the axes. There is no `LineCollection`. |
| `open_gle` | the segments come back as `plot` lines with NaN gap rows. |

## Line keywords

`plot`, `step`, `semilogx`, `semilogy` and `loglog` take matplotlib's short
names `lw`, `ls`, `c`, `ms` and `mfc` for `linewidth`, `linestyle`,
`color`, `markersize` and `markerfacecolor` (and, except `step`, which sets
the draw style from `where`, `ds` for `drawstyle`), and `None` for one of
them means the default, as in
matplotlib. matplotlib raises for a name passed with its short name; gleplot
keeps the full name, with a warning, unless the full name is left at its
default. A `linewidth` that is NaN, infinite or negative raises
`ValueError` at the call, on these and the other line-drawing calls below,
`line_from_file`, `function` and `hist(histtype='step')`, where
matplotlib does not check it. So does a NaN or infinite position or edge on
`axhline`, `axvline`, `axhspan` or `axvspan`, which matplotlib draws as nothing.
GLE has no zero-width stroke, so `lw=0` on
`plot` (and `step`, `stem`, `semilogx`, `semilogy`, `loglog`), `errorbar`,
`line_from_file`, `axhline`, `axvline`, `hlines` and `vlines` draws no
line, as `linestyle='none'` does; `errorbar` still draws its error bars.
`function` and `hist(histtype='step')` are only their line, so `lw=0`
there warns and draws the default width.

A keyword GLE cannot draw, such as `alpha`, `markeredgecolor` (`mec`),
`markeredgewidth` (`mew`), `dashes`, `transform` or `clip_on`, warns and is
ignored, and so does a misspelt one:
`UserWarning: plot() ignores unsupported keyword(s): alpha.` `scatter` and
`stem` warn the same way, under their own names, for keywords they do not
take, `lw`, `ls` and `ms` included.

The other line-drawing calls follow the same rule:

| call | short names honoured | warns, for example |
|---|---|---|
| `errorbar` | `lw`, `c`, `ms`, `mfc`, and `linestyle` (`ls`), which overrides the line style `fmt` gives unless `fmt='none'` | `ecolor`, `elinewidth`, `capthick`, `barsabove`, `errorevery` |
| `errorbar_from_file` | `c`, `ms`, `mfc` | `lw`, `ls`, `ecolor` |
| `axvline`, `axhline` | `lw`, `ls`, `c` | `alpha`, `zorder`, `transform` |
| `axvspan`, `axhspan` | `facecolor` (`fc`) for `color` | `edgecolor`, `linewidth`, `hatch`, `zorder` |

A `linestyle` is `'-'`, `'--'`, `':'` or `'-.'`, or matplotlib's name for
one: `'solid'`, `'dashed'`, `'dotted'` or `'dashdot'`. `'none'` (or `''`,
`' '`, `'None'`) draws no line. GLE has no custom dash patterns, so a dash
tuple such as `(0, (5, 2))` warns and is drawn solid, and so does a value
that is not a line style. This holds for `plot` and the calls above, for
`line_from_file`, `hist(histtype='step')`, and the single `linestyles` of
`contour` and `tricontour`. A `(offset, None)` tuple is matplotlib's solid
line and is drawn solid without a warning. Passing `None` asks for
matplotlib's default: a solid line from `plot`, `axhline`, `axvline` and
`line_from_file`, and the style `fmt` gives from `errorbar`.

`plot(x, y, fmt)`, `step(x, y, fmt)` and `errorbar(..., fmt=...)` read
matplotlib's format strings in the form GLE draws directly: a colour letter
(or `'C0'` to `'C9'`), a marker character and a line style, such as `'ro'`,
`'k--'` or `'--s'`. A marker with no line style draws no line. A `color`,
`marker` or `linestyle` keyword wins over the format, with a warning, as in
matplotlib. A format outside that subset, such as a colour name `'red'`,
warns and is ignored. `errorbar(fmt='none')` draws only the error bars, with
no markers even when `marker=` is given.

`errorbar`'s `yerr` and `xerr` take matplotlib's shapes: a scalar, `N` values
(one symmetric error per point), or shape `(2, N)` (a lower row and an upper
row, such as a `(lower, upper)` tuple). A two-element `yerr=[0.1, 0.2]` is
one error per point on two points, as in matplotlib, and raises `ValueError`
on any other number of points; pass `yerr=([0.1] * N, [0.2] * N)` for a
lower and an upper error on every point.

## Marker spacing, thinning and data ranges

GLE has no "mark every Nth point". `plot(markevery=...)` warns and is ignored. Use `mdist` instead: it places the markers every `mdist` cm along the drawn curve, whatever the point spacing. That is closest to matplotlib's float form of `markevery`. These keywords are gleplot's names for GLE's dataset qualifiers, and `scatter` passes them on to `plot`:

| keyword | GLE |
|---|---|
| `mdist=0.5` | `mdist 0.5`. Needs a `marker`; without one it warns and is dropped. `GLEMarkerConfig(mdist=...)` is the default for every marked line in the figure. |
| `deresolve=5` | `deresolve 5`: one point in every five is drawn. GLE keeps a line's first and last point. |
| `deresolve=5, deresolve_average=True` | `deresolve 5 average`: each window of five points is drawn as its mean. |
| `xmin`, `xmax`, `ymin`, `ymax` | the series' own data range: it is drawn as if its axes ran over that range, and nothing outside it is drawn. This rescales the series; it is not a clip window, and the tick labels keep the axis' own range. An omitted edge is the limit of the axis the series is drawn against. |

A bad value raises `ValueError` at the call. A range GLE cannot draw warns when the figure is saved: a lone edge at or beyond the far axis limit (GLE fills the missing edge from that limit and stops with "invalid range"), or an edge at or below zero on a log axis. A series with its own `deresolve` gets no preview-only decimation. `errorbar` and `errorbar_from_file` take the data range, and draw their error bars against it too, but not `mdist` or `deresolve`: GLE thins the markers but not the whiskers under `deresolve`. `open_gle` keeps either one on an error-bar dataset that has it.

## Scatter colours

`ax.scatter(x, y, c=values, cmap='viridis', vmin=0, vmax=300)` colours each point, as in matplotlib. A GLE dataset has one colour, so the script gets a `glp_cdata_<marker>_<cmap>` sub that draws each point in its own colour. Each point's value comes from GLE's `mdata` and is mapped onto the colormap by a `let`. The values go into the series' data file as given. Where gleplot differs:

| `scatter()` argument | gleplot |
|---|---|
| `c` with one number per point | wired, with `cmap`, `vmin` and `vmax`. A value outside `vmin`..`vmax` takes the end colour, and a point whose value is not finite is left out of the plot and the axis limits. The legend marker is drawn in the colormap's last colour, not the first point's: GLE draws a legend marker as if its value were `vmax`. |
| `c` as one colour | the same as `color`. Passing both `c` and `color` raises `ValueError`. |
| `c` with one colour per point | one series per distinct colour, in the order each colour first appears. Only the first series carries `label`. Points of one colour are drawn together, which only matters where points overlap. |
| `c` with one number per point and `s` with one size per point | warns and draws the colours, every point at the middle size: a GLE dataset carries one per-point value. Pass one size, or one colour. |
| `cmap`, `vmin`, `vmax` without numbers to map | warn and are ignored, as in matplotlib. |
| `norm` | warns and is ignored: colours are always mapped linearly from `vmin` to `vmax`. |

`fig.colorbar(ax=ax)`, or `fig.colorbar()` when only one axes has something to show, draws a bar for the axes' colour-mapped scatter, from its `vmin` to its `vmax`. matplotlib's `fig.colorbar(sc)` is not available: `scatter` returns the axes, not a mappable. See [Colorbars](#colorbars).

## Cells

`ax.pcolormesh(X, Y, C)` draws one flat colour per cell, with the cell edges where matplotlib puts them. It is a heatmap, so it is the axes' one colormap, as `imshow` is. How gleplot writes it is in [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md).

| `pcolormesh()` argument | gleplot |
|---|---|
| `C`, `X`, `Y`, `cmap`, `vmin`, `vmax` | wired. `X` and `Y` must be uniformly spaced; another grid raises `ValueError`, and `tripcolor` takes scattered or irregular data. Values must be finite: `NaN` or a masked value raises `ValueError` rather than leaving the cell blank. |
| `shading` | `'flat'`, `'nearest'` and `'auto'` as in matplotlib; `'gouraud'` warns and is drawn as `'nearest'`. |
| `alpha`, `norm`, `colorizer`, `data`, `antialiased=True` | warn and are ignored: a GLE colormap is opaque and maps colours linearly from `vmin` to `vmax`. |
| `edgecolors` | `'none'` and `'face'` are what is drawn; any other value warns, as do `linewidth`, `zorder` and the other keywords. |
| `pixels` | gleplot's own: the bitmap resolution, as for `imshow`. Each cell edge is drawn to within one pixel. |
| axis limits beyond the mesh | the edge cells show half a cell wider there, and saving warns; see [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md). |

## Filled contours

`ax.contourf(X, Y, Z, levels)` fills the bands between levels by drawing a heatmap through a band palette; how, and when it falls back to a smooth heatmap, is in [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md). It returns the heatmap rather than a `QuadContourSet`; `cf['levels']` holds the levels.

| `contourf()` argument | gleplot |
|---|---|
| `Z`, `X`, `Y`, `levels` (keyword or positional), `cmap`, `vmin`, `vmax` | wired. `levels` as a count picks the levels matplotlib's `MaxNLocator` would. `X` and `Y` must be uniformly spaced and increasing; another grid raises `ValueError`, and `tripcolor` takes scattered data. `NaN` or a masked value raises rather than leaving a hole. |
| `extend` | `'min'`, `'max'` and `'both'` as in matplotlib. With `'neither'`, values beyond the levels are white rather than blank. |
| levels closer together than 6 significant digits | raise `ValueError`: gleplot writes numbers with 6. |
| `colors`, `alpha`, `norm`, `hatches`, `data` | warn and are ignored: the bands are coloured from the colormap. |
| `origin`, `extent`, `locator`, `antialiased`, `zorder` and other keywords | warn and are ignored. |
| `pixels` | gleplot's own: the bitmap resolution, as for `imshow`. |

## Heatmaps and contour lines

`imshow` and `tripcolor` take the arguments listed in their API entries. A NaN or masked cell in `imshow`'s `Z` raises `ValueError` rather than leaving the cell blank, as for `pcolormesh`: choose its value with `np.ma.filled(Z, value)`. `imshow`'s `extent` gives the first and last grid nodes, where `contour` puts them, not the box the image fills: matplotlib's pixels reach half a pixel past the outer centres, and gleplot's colormap stops at those nodes. To match a matplotlib figure, pass the outer pixel centres as `extent`.
Every other keyword, such as `alpha`, `norm` or `aspect`, warns and is
ignored: a GLE colormap is opaque and one per axes (see "One Heatmap Per
Axes" in [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md)).
`contour` and `tricontour` take matplotlib's `linewidth` (`lw`) and
`linestyle` (`ls`) for `linewidths` and `linestyles`, one value each: GLE
draws every level as one dataset, so a per-level list of differing values,
or of `colors`, warns and its first entry is used. `None` for `colors`, `linewidths` or
`linestyles` means the default. Their other keywords
warn and are ignored, among them `extent` and `origin`: pass the grid's
coordinates, `contour(x, y, Z)`, to place it. A misspelt keyword warns the
same way.

matplotlib labels contours with a separate `ax.clabel(cs)` call; gleplot takes
`clabel=True` (and `clabel_fmt`) on `contour` and `tricontour`. The labels are
drawn by `contour_labels` from GLE's `contour.gle`, which writes them in blue,
0.25 cm high, in a white box, whatever the line colour; matplotlib draws them
in the line's colour.

The colormaps are GLE's own: `viridis`, `magma`, `inferno`, `plasma`,
`cividis`, `coolwarm`, `gray`, `rainbow` (`jet`) and the ColorBrewer maps, and
their `_r` forms but `rainbow_r`. GLE draws the sequential and diverging
ColorBrewer maps in 9 or 11 steps where matplotlib blends them. `rainbow_r` and
`jet_r` warn and draw `rainbow`, and per-point scatter colours and `contourf`
bands draw `rainbow` as `viridis`; "Palette Gallery" in
[Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md) lists each one.

## Line caps and joins

matplotlib caps and joins each line on its own; GLE sets them once for the
whole figure. Set them with `GLEStyleConfig(line_cap=..., line_join=...)`,
described in the [Configuration Guide](CONFIGURATION.md). `plot` accepts
`solid_capstyle`, `dash_capstyle`, `solid_joinstyle` and `dash_joinstyle` with
matplotlib's values. One that asks for what the figure already draws is
honoured; one that differs warns and is not applied. As in matplotlib, the
`solid_*` keywords concern a solid line and the `dash_*` ones a dashed line.
`'projecting'` is GLE's `square` and `'miter'` is its `mitre`. With nothing
set, GLE draws butt caps and mitre joins, not matplotlib's projecting solid
caps and round joins.

## Bars

`ax.bar(x, height)` emits `bar dN fill rgb255(31,119,180) color rgb255(31,119,180) lwidth 0`: the first colour of the axes' patch cycle (see [Default colours](#default-colours)), and no edge (see below). One GLE dataset has one face and one edge. A colour sequence therefore becomes one `bar` command per bar, and each of those carries an explicit width, because a one-point dataset has no gap for GLE to measure. A single colour, including the same colour repeated, stays one command.

`edgecolor`, `linewidth` and `linestyle` are the stroke: `color`, `lwidth` and `lstyle`. As in matplotlib, a bar has no edge unless `edgecolor` is given: `linewidth` and `linestyle` style that edge and draw none of their own. GLE strokes every bar, and `lwidth 0` alone is a black hairline, so a bar with no edge is stroked with that hairline in the colour under the edge (`color C lwidth 0`): the fill, or the face of a hatched bar. That is a bar given no `edgecolor`, and one given `edgecolor='none'`, `linestyle='none'` or `linewidth=0`. A hatched bar with `color='none'` has no face to match, and its outline is drawn in the hatch ink. `color='none'` is GLE's `CLEAR` fill. With no edge it is drawn as a black outline, since GLE strokes every bar, and that warns. An RGBA colour with zero alpha, such as `(0, 0, 0, 0)`, is `'none'` here, as a face and as an edge. It is `'none'` too for `hist`, `markerfacecolor`, `set_facecolor` and the `fill` and `color` of a figure drawing such as `Figure.circle`. `bottom` stacks the bar from that baseline to `bottom + height`, written `bar dTo from dFrom`. A zero baseline is not written. `ax.barh(y, width)` emits `horiz`. Its thickness is `height` and defaults to GLE's own derivation, not matplotlib's `0.8`. `align='edge'` warns and is drawn centered.

`hatch` is GLE's `pattern`. Every GLE pattern is diagonal, so only these hatches have one: `'/'` is `SHADE`, `'\\'` is `RSHADE` and `'x'` (or `'X'`) is `GRID`. Repeated (`'//'`, `'xx'`, ...) they are the `2` variants, at half the spacing; a longer run is no denser. `'|'`, `'-'`, `'+'`, `'o'`, `'O'`, `'.'`, `'*'` and any mix such as `'/\\'` warn, and those bars are drawn solid. A sequence gives one hatch per bar, like a colour sequence, and splits the call the same way. GLE's `fill` is the hatch ink and `background` the colour under it, so `ax.bar(x, h, color='yellow', hatch='//')` emits `fill BLACK pattern SHADE2 background YELLOW`. As in matplotlib, the ink is `edgecolor`, or black when `edgecolor` is not given or is `'none'`, and `color='none'` is a `CLEAR` background. The legend swatch is hatched too. In a legend gleplot writes as a `begin key` block, the swatch hatches on white: there, `background` would colour the whole key. GLE's hatch lines are thinner than matplotlib's, and their spacing is fixed in centimetres.

`yerr` and `xerr` draw whiskers at the tip of each bar. A scalar or a length-n sequence is symmetric. Shape `(2, n)` is asymmetric (first row minus, second row plus); `(2, 1)` broadcasts. The whisker is a separate markerless error-bar series, because GLE's `horiz` swaps axes only while drawing the bar and an `err`/`herr` dataset is not swapped. A vertical bar's tip is `(x, bottom + height)`. A horizontal bar's tip is `(left + width, y)`. `yerr` stays vertical and `xerr` stays horizontal, so `barh(..., xerr=)` is a `herr` along the length.

`ecolor` defaults to black. One colour is one series; a sequence of different colours is one series per bar. `capsize` is the cap width in points (`errwidth` / `herrwidth`). Leave it out and GLE draws its own cap, one third of the font height. `capsize=0` is that same default: GLE reads a zero width as "not given". There is no way to omit the cap. `capsize_cm` is the width in centimetres and overrides `capsize`. `error_kw` may set `ecolor`, `capsize`, `capsize_cm` and `zorder` (the last wins, then 0.01 is added so the whisker sits above the bar). Other `error_kw` keys, including `elinewidth`, warn and are ignored: a markerless error dataset does not carry `lwidth`, so the stem uses the line width already in force. The bar's label is the only legend entry.

An autoscaled x axis now includes `xerr`, the way the y axis already included `yerr`. A horizontal whisker is not clipped by the `xaxis` gleplot writes. This applies to `errorbar` as well as to bars.

Two matplotlib calls with shifted x are two commands. GLE's side-by-side group `bar d1,d2 fill c1,c2`, read from a script whose data file gleplot wrote, round-trips as one command (on a data file of your own the whole command stays raw GLE, see [Opening GLE Files](OPENING_GLE_FILES.md)), `dist` included, and so do `pattern` and `background` when they give each dataset at most one pattern, a `fill`, and a background only under a pattern. `3d`, `style`, `side`, `top` and `notop` have no series field; the whole command stays raw GLE.

| call | GLE |
|---|---|
| `ax.bar(x, h, color='green', edgecolor='k')` | `bar dN fill GREEN color BLACK` |
| `ax.bar(x, h, color=['red', 'blue'])` | one `bar` per bar, explicit `width` |
| `ax.bar(x, h2, bottom=h1)` | `bar dTo from dFrom` |
| `ax.bar(x, h, yerr=e, capsize=3)` | `bar dN`, then `dM color BLACK err dE errwidth …` at the tip |
| `ax.barh(y, w, xerr=e)` | `bar dN horiz`, then `herr` at `(left + w, y)` |
| `ax.barh(y, w)` | `bar dN horiz` |

`bar` and `barh` take matplotlib's positional order, `bar(x, height, width, bottom)` and `barh(y, width, height, left)`, and everything else is a keyword. A colour or a string in the third or fourth place raises `TypeError`; pass it as `color=` or `label=`. `width` (and `barh`'s `height`) is one number for every bar; a sequence raises `TypeError`.

## Not provided

GLE has no pie chart or box plot command, and gleplot does not build one out
of subroutines, so `pie` and `boxplot` are not provided: calling them raises
`AttributeError`, as for any other matplotlib name gleplot lacks.

GLE has no broken axis either, so gleplot has none. A logarithmic axis shows
two scales in one panel, and two subplots show two ranges.

gleplot 5 drew all three with its own subroutines. How its files and
snapshots open now is in "Files written by gleplot 5" in
[Migrating from gleplot 5 to 6](MIGRATING_TO_6.md).

## Colorbars

`fig.colorbar(im, ax=ax)` takes the heatmap `imshow`, `pcolormesh`, `tripcolor` or `contourf` returned (a `contourf`'s bar shows its bands, but has no `extend` end caps; thinned ticks start at the first level rather than nearest zero; and with uneven levels each band's room is in proportion to its range, ticked in equal steps, where matplotlib gives every band the same room and ticks the levels), so each axes of a grid can carry its own bar. On an axes with no heatmap, `fig.colorbar(ax=ax)` shows its colour-mapped scatter (`scatter(..., c=values)`); `scatter` returns the axes, so the scatter cannot be passed as `mappable`. The rest of the call differs from matplotlib. See "Colorbars" in [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md).

| `colorbar()` argument | gleplot |
|---|---|
| `mappable`, `ax`, `orientation`, `label` | wired. `ax` must be the axes that holds `mappable`; a list of axes is rejected. |
| `cax` | warns and is ignored. The bar is drawn beside its heatmap's or scatter's axes. |
| `use_gridspec` | accepted. The grid always makes room for the bar. |
| `format` | a GLE `format$` string such as `'fix 2'`, not a `'%.2f'` format. Default: fixed-point with as many decimals as the tick values need. |
| `location`, `fraction`, `shrink`, `aspect`, `pad`, `ticks`, `extend` | not accepted. Use `orientation`, `width`, `sep` and `nticks`. |
| a contour set as `mappable` | not supported: contour lines draw in one colour, so there is no scale to show. |

## Polar axes

GLE has no polar axis. `fig.add_subplot(projection='polar')` hides the graph's axes and draws a grid of rings and spokes with a `glp_polar_grid` call in layer 200, below the curves. The angle and radius labels are written by a `glp_polar_labels` call after the graph block. Both subroutines are defined once at the top of the script. Each curve's data file keeps theta and r, and a `let dK = dJ*cos(x),dJ*sin(x)` turns them into the x and y GLE draws, so markers, line styles and legend entries work as on any axes. The x and y ranges are chosen so both axes have the same scale and the angle labels fit inside the frame; the rings stay round in a subplot that is not square.

```python
ax = fig.add_subplot(projection="polar")
ax.plot(theta, r, marker="o", label="r")
ax.set_ylim(0, 2)
```

| matplotlib | gleplot |
|---|---|
| `ax.plot(theta, r)`, `ax.scatter(theta, r)` | same. `yaxis`, `xaxis`, `offset`, `drawstyle`/`ds`/`line_mode` and the `xmin`/`xmax`/`ymin`/`ymax` data range raise `ValueError`. |
| `ax.set_ylim(0, rmax)`, `ax.set_ylim(top=...)` | same. A lower limit other than 0 raises `ValueError`. Left unset, the outer ring is the largest radius in the data rounded up to a ring, or 1 when the axes has only function curves. |
| `ax.set_rmax`, `set_rticks`, `set_thetagrids`, `set_theta_zero_location`, `set_theta_direction`, `set_rlabel_position` | not available. Rings are evenly spaced, at most five; spokes and angle labels are every 45°, counter-clockwise from the right; ring labels lie along 22.5°. |
| `ax.grid(True)` | does nothing: the polar grid is always drawn. `ax.grid(False)`, `ax.grid()` and grid styling warn and are ignored. `GLEGraphConfig(show_grid=True)` does not apply. |
| `ax.bar`, `ax.fill`, `ax.errorbar`, `ax.text`, `ax.set_xlim`, `ax.set_xticks`, `ax.tick_params`, `ax.derived` and the other plotting and cartesian axis methods | raise `NotImplementedError` on a polar axes. |
| `plt.subplots(subplot_kw={'projection': 'polar'})` | same; every axes of the grid is polar. |

The figure-wide `GLEGraphConfig(smooth_curves=True)` does not apply to a polar axes: GLE would smooth the drawn x and y, which need not be in order. A figure's `sharex`/`sharey` leaves a polar axes' limits alone.

## Histograms

`ax.hist(samples, bins=20, range=(0, 1), histtype="step")` keeps the samples in the data file. GLE bins them with `let dK = hist dJ from 0 to 1 bins 20` and draws the counts. The heights are counts. The window is the data min and max when `range` is omitted, widened by half a unit when every finite sample is the same value, and it is always written into the `let` so GLE does not re-bin over the axis. A sample on the right edge falls in the last bin; samples outside the window are not counted. Non-finite and masked samples are dropped, with a warning that names them.

| `histtype` | GLE |
|---|---|
| `"step"` | `dK line hist`, with smoothing pinned off. The line is drawn in `edgecolor` when one is given, else in `color`, as in matplotlib. |
| `"stepfilled"` | `bar dK fill C color C width W`, one bin wide, from zero. `fill x1,dK` would chord the centres and fill to the axis minimum. The stroke matches the fill so the shared edge of two bins is not a second ink, unless `edgecolor` is given. GLE strokes every bar, so `edgecolor='none'` also strokes in the fill. `color='none'` is a `CLEAR` fill; with no `edgecolor` its outline is black, with a warning. As in matplotlib, `alpha=` reaches an explicit `edgecolor` and the alpha of an RGBA `color` does not. |
| `"bar"`, `"barstacked"` | warn, and draw the step outline in `color`; an `edgecolor` warns and is ignored. Per-bar faces, edges, groups and stacks are `Axes.bar`. |

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
| `ax.fill_betweenx(y, x1, x2)` | `fill dN`, the polygon `(x1, y)` forward and `(x2, y)` back, because GLE's two-curve fill is vertical. `where` selects y runs, clipped with `ymin` / `ymax`. A figure read back with `open_gle` has a `fill` polygon in its place. |
| `ax.stackplot(x, y1, y2, ...)` | one `fill dA,dB` per layer, between running sums. Returns the list of fill series. |

```python
ax.fill_between(x, y, where=(x > 0))
ax.fill_between(x, y, baseline="x1")
ax.fill(x, y, alpha=0.4)
ax.fill_betweenx(y, x, alpha=0.4)
ax.stackplot(x, y, y, labels=["a", "b"], baseline="sym")
```

| argument | gleplot |
|---|---|
| `where` | a boolean array the same length as `x`. A run is filled only where neighboring samples are both True, so one isolated True draws nothing. Each run is a clip window on the full curves, and the axis still covers the whole dataset: GLE autoscales from the points, not from the ink. `x` has to be finite and strictly monotonic (no repeated x); otherwise the mask is ignored, with a warning. |
| `interpolate` | `True` moves a clip edge to where the two curves cross beside that run (matplotlib's intersection, not a midpoint of the mask). An axis fill has no second curve, so this warns and the edge stays on the sample. |
| `xmin`, `xmax`, `ymin`, `ymax` | the same clip, in data coordinates. These are not `axvspan` fractions. On `baseline="x1"`, `ymin` is also the line the fill closes on: GLE uses that value as the baseline and clips below it. Do not pass `where` together with `xmin` or `xmax`. |
| `step` | warns and is ignored. `fill` has no step mode. |
| `fill_betweenx` `where`, `interpolate` | as on `fill_between`, with y in place of x: `y` has to be finite and strictly monotonic, and the clip is `ymin` / `ymax`. Do not pass `where` together with `ymin` or `ymax`. |
| `stackplot` `colors` | cycled over the layers. Omitted, each layer takes the next colour of the axes' line cycle, as in matplotlib (see [Default colours](#default-colours)). A `facecolor` (or `color`) keyword replaces `colors`. |
| `stackplot` `baseline` | `'zero'`, `'sym'`, `'wiggle'` and `'weighted_wiggle'`, computed as matplotlib does. Other keywords (`alpha`, `where`, ...) go to every layer's `fill_between`. |
| `fill` extra polygons | the first polygon is drawn. The rest warn and are ignored. |
| `edgecolor`, `linewidth` on `fill` | warn and are ignored. GLE fills the interior and does not stroke it. |
| `hatch` | warns and is ignored, on `stackplot` too. A graph `fill` has no `pattern` keyword, and a pattern name given as its colour draws black lines on white, which would hide the face colour. |
| `alpha` | unchanged: below 1 the colour is `rgba255(...)`. |

## Saving

`savefig` writes the `.gle` script and, for a `.pdf`, `.png`, `.eps`, `.svg`
or `.jpg` name, compiles it with GLE.

| `savefig()` keyword | gleplot |
|---|---|
| `transparent` | wired — a PNG gets an alpha channel instead of a white background (GLE `-transparent`). PDF, EPS and SVG have no background to begin with. A JPEG has no alpha channel, so `True` warns there; a grayscale PNG keeps its alpha channel only with `cairo=True`, and warns without it. |
| `grayscale` | gleplot keyword, not a matplotlib one: the colours GLE draws become their grey level (GLE `-nocolor`). A heatmap's image is greyed only in PNG and JPEG; in PDF, EPS and SVG it stays in colour and `True` warns. |
| `bbox_inches`, `pad_inches`, `facecolor`, `edgecolor` | warn. The page is always the figure's `figsize`, and its background is not settable. |
| `metadata`, `orientation`, `papertype`, `backend`, `bbox_extra_artists`, `pil_kwargs` and any other keyword | warn and are ignored, whatever the value: `savefig() ignores unsupported keyword(s): metadata.` `savefig_gle` warns the same way for any keyword but `folder`. |

`transparent` and `grayscale` act when GLE compiles, so they warn when only
the `.gle` script is saved.

```python
fig.savefig("plot.png", transparent=True)
fig.savefig("plot.pdf", grayscale=True)
```

## Secondary axes

The right-hand scale is `yaxis="y2"` on a series or the `ax.twinx()` view, and `ax.twiny()` opens the top scale. Both are described in [Axes and Legends](AXES_AND_LEGENDS.md).

## Key Behavioral Differences

1. Primary output model is GLE script generation.
2. Saving to `.gle` always works without external compiler.
3. Saving to `.pdf`, `.png`, `.eps`, `.svg` or `.jpg` requires GLE and its include library (`gleinc`).
4. Sidecar `.dat` files are generated for in-memory series unless file-based series methods are used.
5. `ax.grid(visible, which=, axis=, color=, linestyle=, linewidth=)` maps to
   GLE's `xaxis grid` (+ `xsubticks on` for `which='both'`). A minor-only
   grid is not expressible and is normalized to both, with a warning.
6. `fontname=` on `set_xlabel`, `set_ylabel` and `set_title` takes a GLE
   font name (`'texcmr'`, `'psh'`), not a matplotlib family such as
   `'serif'`. GLE centres every title, so `loc` other than `'center'`
   warns, as do `fontweight`, `fontdict` and the other text keywords.
   Unlike matplotlib, `set_title` keeps the size and pad of the
   previous call unless they are passed again.
7. GLE has no separate top and right spines: the x line's style is copied
   onto the top line and the y line's onto the right one. Set `'x2'` or
   `'y2'` with `set_axis_line` to style those on their own. Hiding the top
   or right line with `visible=False` also removes the tick marks GLE
   mirrors there, and any `twiny`/`twinx` scale drawn on that edge (which
   warns).
8. Display strings follow matplotlib's contract: plain text renders literally
   (`'lambda_tail'` is not a subscript) and math is opt-in via `$...$`. Unlike
   matplotlib, a backslash outside `$...$` still opens GLE's own text markup
   (`r'\chi{}'`), as do braced scripts (`'T_{N}'`).
9. A second or translucent `imshow` or `pcolormesh` is not possible; see
   [Contours and Heatmaps](CONTOUR_AND_HEATMAPS.md) for why and what to use
   instead.
10. `ax.tick_params` honours `which`, `reset`, `direction`, `length`,
    `width` and `color`. Its other keywords (`pad`, `labelsize`,
    `labelcolor`, `bottom`, `labelbottom`, `grid_*`, ...) warn and are
    ignored. GLE has no separate top and right ticks: `axis='x'` styles the
    top ticks too. Minor ticks with no colour of their own take the major
    ticks' colour. On an axis with a grid, GLE's grid lines are the ticks,
    so the tick marks are not written and saving warns. See
    [Axes and Legends](AXES_AND_LEGENDS.md).
11. `imshow` colours an array; it does not show a picture read with `imread`.
    Place the image file itself with `ax.image(fname, extent=...)`; see
    [Plot Types](PLOT_TYPES.md).
12. An RGBA colour's alpha is honoured by `hist` only. Elsewhere the colour
    is drawn opaque and a warning says so: pass an RGB colour and use the
    `alpha=` keyword where the function has one (`fill_between`, `fill`,
    `axhspan`, `axvspan`). As in matplotlib, `alpha=` overrides the colour's
    own alpha, and then nothing warns. Where `'none'` is accepted, a zero
    alpha is `'none'`, unless `alpha=` replaces it.
13. A guide (`axhline`, `axvline`, `axhspan`, `axvspan`) on an axis gleplot
    cannot range, because the axes has no data and no limit for it or its
    data collapses to one value, is drawn after the graph against the range
    GLE picks. It is then drawn above the data, the grid and the ticks
    rather than under them, and a line outside the frame is not clipped.
    Give the axes a limit with `set_xlim`/`set_ylim` to keep the guide
    under the data. See
    [Reference Lines and Shaded Spans](REFERENCE_LINES_AND_SPANS.md).
14. A masked value (`numpy.ma`) is read as NaN wherever matplotlib leaves a
    masked point out: the data of `plot`, `step`, `stem`, `scatter` (`x`,
    `y`, `c` and `s`), the heights and `yerr`/`xerr` of `bar` and `barh`,
    `errorbar`, `fill_between`, `fill_betweenx`, `hist`, `hlines` and
    `vlines`. It then behaves as a NaN does there: a `scatter` point with a
    NaN size and a `bar` whisker with a NaN error are left out, and `hist`
    warns that it dropped the masked samples. As in matplotlib, `fill`,
    `stackplot` and the `bar` positions and `bottom` use the values under
    the mask.
15. A line on a log axis leaves a negative point out and joins its
    neighbours, where matplotlib draws the line off the axis there; a zero
    goes down to the axis edge, as in matplotlib. Saving warns when a
    `plot` or `step` line has a negative value on a log axis. Set those
    values to NaN to break
    the line there, see [Axes and Legends](AXES_AND_LEGENDS.md).

## Migration Strategy

1. Port plotting code with minimal edits (`plt` -> `glp`).
2. Validate scripts first by saving as `.gle`.
3. Add `data_prefix` for deterministic sidecar names in batch pipelines.
4. Replace custom file parsers with `errorbar_from_file()`/`line_from_file()` where possible.
5. Add project-specific style defaults via `GlobalConfig`.
