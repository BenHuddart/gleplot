# Matplotlib Migration Guide

gleplot intentionally mirrors the matplotlib style for core plotting tasks.

## Quick Mapping

| matplotlib | gleplot |
|---|---|
| `plt.figure()` | `glp.figure()` |
| `fig.add_subplot(...)` | same, including a `(first, last)` index that spans cells, see [Figures and Subplots](FIGURES_AND_SUBPLOTS.md) |
| `fig.add_axes(rect)` | same for a rect in figure fractions; the inset has no background, and axes-property keywords warn, see [Figures and Subplots](FIGURES_AND_SUBPLOTS.md) |
| `ax.plot(...)` | same |
| `ax.scatter(...)` | same, including `c=` for per-point colours, see [Scatter colours](#scatter-colours) |
| `ax.errorbar(...)` | same |
| `ax.fill_between(...)` | same |
| `ax.fill_betweenx(...)` / `ax.stackplot(...)` | same, see [Fills](#fills) |
| `ax.hlines(...)` / `ax.vlines(...)` | same, see [Segments](#segments) |
| `ax.pie(...)` | same, see [Pie charts](#pie-charts) |
| `ax.boxplot(...)` | same, vertical only, see [Box plots](#box-plots) |
| `ax.pcolormesh(...)` | same on a uniform grid, see [Cells](#cells) |
| `fig.colorbar(im, ax=ax)` | same, see [Colorbars](#colorbars) |
| `fig.add_subplot(projection='polar')` | same, lines, scatters and function curves, see [Polar axes](#polar-axes) |
| `ax.set_xlabel(...)` | same; `fontsize`, `color` and `labelpad` are honoured, other text keywords warn; `labelpad` is keyword-only, since the second positional argument is gleplot's `axis` |
| `ax.set_ylabel(...)` | same as `set_xlabel` |
| `ax.set_title(...)` | same; `fontsize`, `color` and `pad` are honoured, `fontdict`, `y` and other text keywords warn |
| `ax.spines[...].set_color(c)` / `.set_linewidth(w)` | `ax.set_axis_line(axis, color=c, linewidth=w)` |
| `ax.spines[...].set_visible(False)` | `ax.set_axis_line(axis, visible=False)`, with `'x'`, `'y'`, `'x2'`, `'y2'` for bottom, left, top, right |
| `ax.spines['left'].set_position('zero')` and `ax.spines['bottom'].set_position('zero')` | `ax.set_math_mode()` |
| `ax.legend(...)` | same |
| `ax.twinx()` / `ax.twiny()` | same, a view of the right or top scale, see [Secondary axes](#secondary-axes); `twinx`'s `axes_class`, `delta_zorder` and other keywords warn |
| `ax.invert_xaxis()` / `ax.invert_yaxis()` | same; automatic limits are fixed to the data plotted so far, so plot first. On a `twinx()`/`twiny()` view, set the limits first |
| `ax.semilogx(...)` / `semilogy` / `loglog` | same; `base` other than 10, `subs` and `nonpositive` warn |
| `ax.set_xticklabels(labels)` / `set_yticklabels` | same, after `set_xticks(ticks)`; `minor=True` and text properties warn |
| `ax.axis('off')` / `ax.set_axis_off()` | same, but the axis labels stay (with a warning); `'equal'`, `'scaled'`, `'image'`, `'square'` and `emit=False` warn, use `set_aspect` |
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
| `step` format string | warns and is ignored. Pass `color`, `linestyle` and `marker` as keywords. |
| `linestyle="none"` together with a step style | warns. There is no line for the mode to qualify. `line_from_file` drops the mode the same way and still writes the line reference. |
| `GLEGraphConfig(smooth_curves=True)` | a step, stem, hist, bar or impulse series stays unsmoothed. GLE would spline the points first and then draw the mode through the spline. A script that writes both keywords keeps the smooth it asked for. |
| `stem` `linefmt` / `markerfmt` | color, linestyle and marker are applied. Stems and heads are one dataset, so two different colors warn and the line color wins. |
| `stem` `bottom` | warns unless it is `0`. GLE's origin is 0 when the y range includes 0, otherwise the range edge nearest 0. It is not matplotlib's baseline. |
| `stem` `basefmt` | warns, unless it asks for no baseline. No baseline is drawn. |
| `stem` `orientation="horizontal"` | warns. Impulses are vertical. |
| `stem` return value | the axes. There is no `StemContainer`. |
| `stem(data=...)`, `use_line_collection` | warn and are ignored. |

## Segments

`ax.vlines(x, ymin, ymax)` and `ax.hlines(y, xmin, xmax)` are line datasets: one per distinct colour, line style and width, with a missing value (`*`) between segments. The arguments are listed in the API reference for `Axes.vlines`. GLE breaks a line at `*`. It drops a `nan` row and joins its neighbours, so a NaN in `ax.plot` is not a gap.

| argument | gleplot |
|---|---|
| a dash tuple in `linestyles` | warns and is drawn solid. |
| `alpha` and other `LineCollection` keywords | warn and are ignored. |
| return value | the axes. There is no `LineCollection`. |
| `open_gle` | the segments come back as `plot` lines with NaN gap rows. |

## Marker spacing, thinning and clipping

GLE has no "mark every Nth point". `plot(markevery=...)` warns and is ignored. Use `mdist` instead: it places the markers every `mdist` cm along the drawn curve, whatever the point spacing. That is closest to matplotlib's float form of `markevery`. These keywords are gleplot's names for GLE's dataset qualifiers, and `scatter` passes them on to `plot`:

| keyword | GLE |
|---|---|
| `mdist=0.5` | `mdist 0.5`. Needs a `marker`; without one it warns and is dropped. `GLEMarkerConfig(mdist=...)` is the default for every marked line in the figure. |
| `deresolve=5` | `deresolve 5`: one point in every five is drawn. GLE keeps a line's first and last point. |
| `deresolve=5, deresolve_average=True` | `deresolve 5 average`: each window of five points is drawn as its mean. |
| `xmin`, `xmax`, `ymin`, `ymax` | the series' own clip window in data coordinates. Nothing is drawn outside it. |

A bad value raises `ValueError` at the call. A series with its own `deresolve` gets no preview-only decimation. `errorbar` does not take them: GLE thins the markers but not the whiskers under `deresolve`.

## Scatter colours

`ax.scatter(x, y, c=values, cmap='viridis', vmin=0, vmax=300)` colours each point, as in matplotlib. A GLE dataset has one colour, so the script gets a `gleplot_cdata_<marker>_<cmap>` sub that draws each point in its own colour. Each point's value comes from GLE's `mdata` and is mapped onto the colormap by a `let`. The values go into the series' data file as given. Where gleplot differs:

| `scatter()` argument | gleplot |
|---|---|
| `c` with one number per point | wired, with `cmap`, `vmin` and `vmax`. A value outside `vmin`..`vmax` takes the end colour, and a point whose value is not finite is left out of the plot and the axis limits. The legend marker is drawn in the colormap's last colour, not the first point's: GLE draws a legend marker as if its value were `vmax`. |
| `c` as one colour | the same as `color`. Passing both `c` and `color` raises `ValueError`. |
| `c` with one colour per point | one series per distinct colour, in the order each colour first appears. Only the first series carries `label`. Points of one colour are drawn together, which only matters where points overlap. |
| `c` with one number per point and `s` with one size per point | raises `ValueError`: a GLE dataset carries one per-point value. Pass one size, or one colour. |
| `cmap`, `vmin`, `vmax` without numbers to map | warn and are ignored, as in matplotlib. |
| `norm` | warns and is ignored: colours are always mapped linearly from `vmin` to `vmax`. |

`fig.colorbar()` does not yet take a scatter: it shows a heatmap's colour scale only.

## Cells

`ax.pcolormesh(X, Y, C)` draws one flat colour per cell, with the cell edges where matplotlib puts them. It is a heatmap, so it is the axes' one colormap, as `imshow` is. How gleplot writes it is in [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md).

| `pcolormesh()` argument | gleplot |
|---|---|
| `C`, `X`, `Y`, `cmap`, `vmin`, `vmax` | wired. `X` and `Y` must be uniformly spaced; another grid raises `ValueError`, and `tripcolor` takes scattered or irregular data. Values must be finite: `NaN` raises `ValueError` rather than leaving the cell blank. |
| `shading` | `'flat'`, `'nearest'` and `'auto'` as in matplotlib; `'gouraud'` warns and is drawn as `'nearest'`. |
| `alpha`, `norm`, `colorizer`, `data`, `antialiased=True` | warn and are ignored: a GLE colormap is opaque and maps colours linearly from `vmin` to `vmax`. |
| `edgecolors` | `'none'` and `'face'` are what is drawn; any other value warns, as do `linewidth`, `zorder` and the other keywords. |
| `pixels` | gleplot's own: the bitmap resolution, as for `imshow`. Each cell edge is drawn to within one pixel. |

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

`ax.bar(x, height)` emits `bar dN fill RED`. One GLE dataset has one face and one edge. A colour sequence therefore becomes one `bar` command per bar, and each of those carries an explicit width, because a one-point dataset has no gap for GLE to measure. A single colour, including the same colour repeated, stays one command.

`edgecolor`, `linewidth` and `linestyle` are the stroke: `color`, `lwidth` and `lstyle`. `edgecolor='none'` emits `lwidth 0` (GLE has no missing edge). `bottom` stacks the bar from that baseline to `bottom + height`, written `bar dTo from dFrom`. A zero baseline is not written. `ax.barh(y, width)` emits `horiz`. Its thickness is `height` and defaults to GLE's own derivation, not matplotlib's `0.8`. `align='edge'` warns and is drawn centered.

`hatch` is GLE's `pattern`. Every GLE pattern is diagonal, so only these hatches have one: `'/'` is `SHADE`, `'\\'` is `RSHADE` and `'x'` (or `'X'`) is `GRID`. Repeated (`'//'`, `'xx'`, ...) they are the `2` variants, at half the spacing; a longer run is no denser. `'|'`, `'-'`, `'+'`, `'o'`, `'O'`, `'.'`, `'*'` and any mix such as `'/\\'` warn, and those bars are drawn solid. A sequence gives one hatch per bar, like a colour sequence, and splits the call the same way. GLE's `fill` is the hatch ink and `background` the colour under it, so `ax.bar(x, h, color='yellow', hatch='//')` emits `fill BLACK pattern SHADE2 background YELLOW`. As in matplotlib, the ink is `edgecolor`, or black when there is no edge or it is `'none'`, and `color='none'` is a `CLEAR` background. The legend swatch is hatched too. In a legend gleplot writes as a `begin key` block, the swatch hatches on white: there, `background` would colour the whole key. GLE's hatch lines are thinner than matplotlib's, and their spacing is fixed in centimetres.

`yerr` and `xerr` draw whiskers at the tip of each bar. A scalar or a length-n sequence is symmetric. Shape `(2, n)` is asymmetric (first row minus, second row plus); `(2, 1)` broadcasts. The whisker is a separate markerless error-bar series, because GLE's `horiz` swaps axes only while drawing the bar and an `err`/`herr` dataset is not swapped. A vertical bar's tip is `(x, bottom + height)`. A horizontal bar's tip is `(left + width, y)`. `yerr` stays vertical and `xerr` stays horizontal, so `barh(..., xerr=)` is a `herr` along the length.

`ecolor` defaults to black. One colour is one series; a sequence of different colours is one series per bar. `capsize` is the cap width in points (`errwidth` / `herrwidth`). Leave it out and GLE draws its own cap, one third of the font height. `capsize=0` is that same default: GLE reads a zero width as "not given". There is no way to omit the cap. `capsize_cm` is the width in centimetres and overrides `capsize`. `error_kw` may set `ecolor`, `capsize`, `capsize_cm` and `zorder` (the last wins, then 0.01 is added so the whisker sits above the bar). Other `error_kw` keys, including `elinewidth`, warn and are ignored: a markerless error dataset does not carry `lwidth`, so the stem uses the line width already in force. The bar's label is the only legend entry.

An autoscaled x axis now includes `xerr`, the way the y axis already included `yerr`. A horizontal whisker is not clipped by the `xaxis` gleplot writes. This applies to `errorbar` as well as to bars.

Two matplotlib calls with shifted x are two commands. A hand-written `bar d1,d2 fill c1,c2` is GLE's side-by-side group and round-trips as one command, `dist` included, and so do `pattern` and `background` when they give each dataset at most one pattern, a `fill`, and a background only under a pattern. `3d`, `style`, `side`, `top` and `notop` have no series field; the whole command stays raw GLE.

| call | GLE |
|---|---|
| `ax.bar(x, h, color='green', edgecolor='k')` | `bar dN fill GREEN color BLACK` |
| `ax.bar(x, h, color=['red', 'blue'])` | one `bar` per bar, explicit `width` |
| `ax.bar(x, h2, bottom=h1)` | `bar dTo from dFrom` |
| `ax.bar(x, h, yerr=e, capsize=3)` | `bar dN`, then `dM color BLACK err dE errwidth …` at the tip |
| `ax.barh(y, w, xerr=e)` | `bar dN horiz`, then `herr` at `(left + w, y)` |
| `ax.barh(y, w)` | `bar dN horiz` |

`width` stays a keyword. The third positional argument is `color`, as it has always been.

## Pie charts

GLE has no pie command. `ax.pie(x)` stores one `Wedge` per value and writes each as a `gleplot_wedge` call after the graph block. The subroutine is defined once at the top of the script, so the output does not depend on GLE's include path. Each wedge is filled with no outline. Its label sits `labeldistance` radii out, and its `autopct` text sits `pctdistance` radii out, as in matplotlib. The radius is measured on the axis with fewer centimetres per unit, so the pie stays round in a subplot that is not square. Both limits are set to `center` ± 1.25. The axis lines, ticks and tick labels are hidden, and the title stays.

```python
ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=90)
```

| `pie()` argument | gleplot |
|---|---|
| `labels`, `colors`, `autopct`, `pctdistance`, `labeldistance`, `startangle`, `radius`, `counterclock`, `center`, `normalize` | wired. Without `colors`, the wedges cycle `'C0'` to `'C9'`. |
| `textprops` | `fontsize` (alias `size`) sets the text height, in points or as a size name such as `'large'`. Other keys warn. The text is black. |
| `explode` | warns when an offset is not zero; the wedges are drawn in place. |
| `wedgeprops` | warns. A donut hole (`width`) and wedge outlines are not drawn. |
| `shadow`, `hatch`, `rotatelabels` | warn and are ignored. |
| `frame=True` | keeps the axes, but the limits are still `center` ± 1.25 rather than autoscaled. Warns. |
| return value | `(wedges, texts)`, or `(wedges, texts, autotexts)` with `autopct`. The texts are the strings drawn, one per wedge, not `Text` objects. |

Labels are drawn beside the wedges; they are not legend entries. The wedges are drawn above anything else plotted on the same axes. A wedge's text height, like an `ax.text` height, stays in force for the text drawn after it on that axes.

## Box plots

GLE has no box plot command. `ax.boxplot(x)` computes each box's quartiles, whiskers and fliers in Python, as matplotlib does, stores one `Box` per sample set and writes each as a `gleplot_box` call after the graph block, followed by a `gleplot_box_flier` call per flier and a `gleplot_box_mean` call with `showmeans=True`. The subroutines are defined once at the top of the script. The style is matplotlib's default: black 1 pt lines, an orange median, black open circle fliers and a green triangle mean.

```python
ax.boxplot(samples, widths=0.4, tick_labels=["a", "b", "c"])
```

| `boxplot()` argument | gleplot |
|---|---|
| `whis`, `positions`, `widths`, `capwidths`, `usermedians`, `showmeans`, `showcaps`, `showfliers`, `autorange`, `tick_labels`, `manage_ticks` | wired, with matplotlib's defaults. `widths` and `capwidths` are in data units. |
| `orientation='horizontal'`, `vert=False` | raise `ValueError`: only vertical box plots are drawn. |
| `sym` | `''` hides the fliers. Any other value warns; fliers are black open circles. |
| `notch`, `bootstrap`, `conf_intervals` | warn; boxes are not notched. |
| `patch_artist` | warns; boxes are not filled. |
| `meanline` | warns; the mean is a marker. |
| `showbox=False` | warns; the box is drawn. |
| `boxprops`, `flierprops`, `medianprops`, `meanprops`, `capprops`, `whiskerprops` | warn; the style is matplotlib's default. |
| `zorder`, `label`, `data` | warn and are ignored. Boxes have no legend entry. |
| return value | a dict with matplotlib's keys (`'boxes'`, `'medians'`, `'whiskers'`, `'caps'`, `'fliers'`, `'means'`), each holding the list of `Box` entries. One entry holds every part of its box; there are no `Line2D` objects. |

Samples must be finite: `NaN` or infinity raises `ValueError`. The boxes are drawn above anything else plotted on the same axes, clipped to the frame (a whisker or cap lying on the frame is drawn whole); a flier or mean outside the axis ranges is not drawn. The x range covers each box and half a unit either side of its position, whatever `manage_ticks` is, and the y range covers the whiskers, the median and the drawn fliers and means, with no margin.

## Colorbars

`fig.colorbar(im, ax=ax)` takes the heatmap `imshow`, `pcolormesh` or `tripcolor` returned, so each axes of a grid can carry its own bar. The rest of the call differs from matplotlib. See "Colorbars" in [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md).

| `colorbar()` argument | gleplot |
|---|---|
| `mappable`, `ax`, `orientation`, `label` | wired. `ax` must be the axes that holds `mappable`; a list of axes is rejected. |
| `cax` | warns and is ignored. The bar is drawn beside its heatmap's axes. |
| `use_gridspec` | accepted. The grid always makes room for the bar. |
| `format` | a GLE `format$` string such as `'fix 2'`, not a `'%.2f'` format. |
| `location`, `fraction`, `shrink`, `aspect`, `pad`, `ticks`, `extend` | not accepted. Use `orientation`, `width`, `sep` and `nticks`. |
| a contour set as `mappable` | not supported: contour lines draw in one colour, so there is no scale to show. |

## Polar axes

GLE has no polar axis. `fig.add_subplot(projection='polar')` hides the graph's axes and draws a grid of rings and spokes with a `gleplot_polar_grid` call in layer 200, below the curves. The angle and radius labels are written by a `gleplot_polar_labels` call after the graph block. Both subroutines are defined once at the top of the script. Each curve's data file keeps theta and r, and a `let dK = dJ*cos(x),dJ*sin(x)` turns them into the x and y GLE draws, so markers, line styles and legend entries work as on any axes. The x and y ranges are chosen so both axes have the same scale and the angle labels fit inside the frame; the rings stay round in a subplot that is not square.

```python
ax = fig.add_subplot(projection="polar")
ax.plot(theta, r, marker="o", label="r")
ax.set_ylim(0, 2)
```

| matplotlib | gleplot |
|---|---|
| `ax.plot(theta, r)`, `ax.scatter(theta, r)` | same. `yaxis`, `xaxis`, `offset`, `drawstyle`/`ds`/`line_mode` and the `xmin`/`xmax`/`ymin`/`ymax` clip window raise `ValueError`. |
| `ax.set_ylim(0, rmax)`, `ax.set_ylim(top=...)` | `ax.set_ylim(0, rmax)` or `ax.set_ylim(None, rmax)`. A lower limit other than 0 raises `ValueError`. Left unset, the outer ring is the largest radius in the data rounded up to a ring, or 1 when the axes has only function curves. |
| `ax.set_rmax`, `set_rticks`, `set_thetagrids`, `set_theta_zero_location`, `set_theta_direction`, `set_rlabel_position` | not available. Rings are evenly spaced, at most five; spokes and angle labels are every 45°, counter-clockwise from the right; ring labels lie along 22.5°. |
| `ax.grid(True)` | does nothing: the polar grid is always drawn. `ax.grid(False)`, `ax.grid()` and grid styling warn and are ignored. `GLEGraphConfig(show_grid=True)` does not apply. |
| `ax.bar`, `ax.fill`, `ax.errorbar`, `ax.text`, `ax.set_xlim`, `ax.set_xticks`, `ax.tick_params`, `ax.derived` and the other plotting and cartesian axis methods | raise `NotImplementedError` on a polar axes. |
| `plt.subplots(subplot_kw={'projection': 'polar'})` | not available; use `fig.add_subplot(..., projection='polar')`. |

The figure-wide `GLEGraphConfig(smooth_curves=True)` does not apply to a polar axes: GLE would smooth the drawn x and y, which need not be in order. A figure's `sharex`/`sharey` leaves a polar axes' limits alone.

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
| `stackplot` `colors` | cycled over the layers. The default is `'C0'` to `'C9'`, starting again at `'C0'` on every call; matplotlib continues the axes' colour cycle. A `facecolor` (or `color`) keyword replaces `colors`. |
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
3. Saving to `.pdf`, `.png`, `.eps` requires a working GLE installation.
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

## Migration Strategy

1. Port plotting code with minimal edits (`plt` -> `glp`).
2. Validate scripts first by saving as `.gle`.
3. Add `data_prefix` for deterministic sidecar names in batch pipelines.
4. Replace custom file parsers with `errorbar_from_file()`/`line_from_file()` where possible.
5. Add project-specific style defaults via `GlobalConfig`.
