# Contour Plots and Heatmaps

gleplot can render 2-D scalar fields as heatmaps (matplotlib's `imshow`/`pcolormesh`/`tripcolor`) filled contours (`contourf`) and contour lines (`contour`/`tricontour`), with an optional colorbar. Under the hood these compile to GLE `colormap` / `begin contour` / `begin fitz` constructs, coloured by the palettes of GLE's include library (see "Palette Gallery" below).

## Supported Methods

- `Axes.imshow(Z, extent=None, origin='lower', cmap=None, vmin=None, vmax=None, interpolation='bicubic', pixels=None, invert=False, label=None)` — heatmap of a **gridded** 2-D array.
- `Axes.pcolormesh(*args, cmap=None, vmin=None, vmax=None, shading=None, pixels=None, label=None)` — one flat colour per cell of a **uniform** grid (see [Cells with pcolormesh](#cells-with-pcolormesh)).
- `Axes.contourf(*args, levels=None, cmap=None, vmin=None, vmax=None, extend='neither', pixels=None, label=None)` — bands between contour levels of **gridded** data (see [Filled contours with contourf](#filled-contours-with-contourf)).
- `Axes.contour(*args, levels=None, colors='black', linewidths=1.0, linestyles='-', clabel=False, clabel_fmt='fix 1', label=None)` — contour lines of **gridded** data. Call as `contour(Z)` or `contour(x, y, Z)`.
- `Axes.tripcolor(x, y, z, gridsize=(50, 50), extent=None, **imshow_kwargs)` — heatmap of **scattered** `(x, y, z)` samples, gridded by GLE at compile time.
- `Axes.function2d(expression, extent, cmap=None, vmin=0.0, vmax=1.0, pixels=None, invert=False, label=None)` — heatmap of an **expression** in `x` and `y` that GLE evaluates itself (see [Heatmap from an expression](#heatmap-from-an-expression)).
- `Axes.tricontour(x, y, z, gridsize=(50, 50), extent=None, ncontour=3, **contour_kwargs)` — contour lines of **scattered** `(x, y, z)` samples.
- `Figure.colorbar(mappable=None, cax=None, ax=None, use_gridspec=True, *, orientation=None, label=None, format=None, nticks=None, width=0.5, sep=None)` — attaches a colorbar to a heatmap or a colour-mapped scatter, beside its axes (vertical) or below it (horizontal). See [Colorbars](#colorbars).

Each except `function2d` has a module-level convenience wrapper too: `glp.imshow(...)`, `glp.pcolormesh(...)`, `glp.contour(...)`, `glp.contourf(...)`, `glp.tripcolor(...)`, `glp.tricontour(...)`, `glp.colorbar(...)` (they operate on `gca()`/`gcf()`, matching `glp.plot()` and friends).

There is no 3-D surface support — gleplot only targets 2-D colormap/contour output.

## Minimal Example: Gridded Heatmap + Contour

```python
import numpy as np
import gleplot as glp

x = np.linspace(-3, 3, 120)
y = np.linspace(-2.5, 2.5, 100)
X, Y = np.meshgrid(x, y)
Z = np.exp(-(X**2 + Y**2) / 2.0)

fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)

ax.imshow(Z, extent=(x[0], x[-1], y[0], y[-1]), cmap='viridis')
ax.contour(x, y, Z, levels=6, colors='white', linewidths=0.7)

ax.set_xlabel('x')
ax.set_ylabel('y')
fig.colorbar(label='amplitude')

fig.savefig('gaussian.pdf')
```

`extent` gives the first and last grid nodes, where `contour` places them, so the heatmap and the contour lines of one grid line up. GLE's `colormap` puts the last node one node spacing short of its `.z` header's `xmax`, so the header is written one spacing past the last node (see [What Files gleplot Writes](#what-files-gleplot-writes)). Axis limits beyond the last node show that extra spacing in the colours of the edge nodes, and saving warns.

`contour`'s `levels` argument accepts:

- `None` (default) — GLE's own default of 10 automatic levels.
- An `int` `n` — resolved **at call time** into `n` explicit level values evenly spaced strictly between the data's min and max, and emitted as an explicit `values v1 v2 ...` list (not GLE's `values from a to b step s` form). This keeps the stored model self-contained and round-trip-safe, but means the levels are fixed to the data range at the moment you call `contour`/`tricontour`, not re-derived later.
- An explicit sequence, e.g. `levels=[0.2, 0.5, 0.8]` — stored verbatim.

Add `clabel=True` to draw inline value labels at each contour crossing (formatted with `clabel_fmt`, a GLE `format$` string such as `'fix 1'` or `'fix 2'`). They are written by `contour_labels` from GLE's include library (`contour.gle`), in blue in a white box:

```python
ax.contour(x, y, Z, levels=[0.2, 0.5, 0.8], colors='black', clabel=True, clabel_fmt='fix 2')
```

## Cells with pcolormesh

`pcolormesh` colours each cell of a grid by its value, with each edge where matplotlib puts it:

```python
import numpy as np
import gleplot as glp

x = np.linspace(0, 4, 9)        # 9 cell edges -> 8 columns
y = np.linspace(0, 3, 7)        # 7 cell edges -> 6 rows
C = np.add.outer(np.arange(6), np.arange(8)).astype(float)

fig = glp.figure()
ax = fig.add_subplot(111)
mesh = ax.pcolormesh(x, y, C, cmap='magma')
fig.colorbar(mesh)
fig.savefig('cells.pdf')
```

`X` and `Y` are the cell edges (one longer than `C` along each axis) or the cell centres (the same shape as `C`); `shading` chooses as in matplotlib, and the 2-D arrays from `np.meshgrid` work as well as 1-D ones. The spacing must be uniform: a grid that is not raises `ValueError`, and `tripcolor` draws scattered or irregularly gridded data instead. `shading='gouraud'` warns and is drawn as `'nearest'`.

GLE's `colormap ... interpolate nearest` gives a pixel the value of the nearest grid node, and stops the bitmap at the `.z` file's `xmin`/`xmax`. So the sidecar repeats the first row and column and puts its header half a cell outside the mesh; the graph frame, which the mesh's extent sets, clips the half cell left over at each end. A `! gleplot: cells xmin ... ymax ...` line under the header, which GLE skips, holds the mesh's own edges, so `open_gle` reads back the mesh and not the padding. If other data, `set_xlim` or `set_ylim` take the axes beyond the mesh, that half cell shows beside it in the colour of the edge cells, and saving warns. On a log axis, a mesh whose padded bitmap would start at or below zero is not drawn by GLE, and saving warns too. Each cell edge is drawn to within one of the colormap's `pixels`.

## Filled contours with contourf

GLE has no filled-contour command. `contourf` draws a heatmap whose palette colours each value by the band it falls in:

```python
import numpy as np
import gleplot as glp

x = np.linspace(-3, 3, 121)
y = np.linspace(-2, 2, 81)
X, Y = np.meshgrid(x, y)
Z = np.exp(-(X**2 + Y**2) / 2) * np.cos(2 * X)

fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
cf = ax.contourf(X, Y, Z, levels=8, cmap='coolwarm')
ax.contour(x, y, Z, levels=cf['levels'], colors='black', linewidths=0.5)
fig.savefig('bands.pdf')
```

`levels` works as in matplotlib: a count picks round-number levels spanning the data (`None` is 7), and a sequence is used as given. Each band takes the colour the colormap gives its middle value on the `vmin`..`vmax` scale, which defaults to the first and last level. `extend='min'`, `'max'` or `'both'` fills the values beyond the levels on that side with the colormap's end colour; with `'neither'` they are white, where matplotlib leaves them blank. The call returns the heatmap, and `cf['levels']` holds the levels it used, so `contour` can draw lines on the band edges as above.

GLE's colormap smooths the grid with a cubic B-spline before the palette sees it, so a band edge is drawn near its level, not exactly on it. `contourf` works out, when it is called, where GLE will draw every edge. If some edge would land more than one bitmap pixel from its level, which happens on a coarse grid, it warns and draws a smooth heatmap instead, coloured by value between the outer levels. A finer `Z`, or fewer `pixels`, brings the bands back. The check assumes the axis limits are the grid's extent.

The `.z` sidecar is written with its header one node spacing past the last node, because GLE's `colormap` places the last node one spacing short of the header's `xmax`. A `! gleplot: nodes ...` line under the header holds the grid's own edges. The band palette is a `glp_contourf<k>` sub written just before the graph, and its first line records the levels, `extend`, colormap and `vmin`/`vmax`, which is what `open_gle` reads back. Axis limits beyond the last node show that extra spacing, so saving warns. With a colorbar, the band sub is also the bar's palette: the colormap scales the grid onto the bar's range and the sub's first statement maps it back.

## Heatmap from an Expression

When the field is an analytic function, `function2d` lets GLE compute it: the figure gets one `colormap` line and no data file.

```python
import gleplot as glp

fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
ax.function2d('sin(x)*cos(y)', extent=(0, 6.28, 0, 6.28), vmin=-1, vmax=1)
fig.colorbar(label='z')
fig.savefig('waves.pdf')
```

This writes `colormap sin(x)*cos(y) 200 200 zmin -1 zmax 1 palette cmap_viridis` inside the graph. The expression is GLE syntax (`^` for powers, `exp`, `atan2(y,x)`, …) and must not contain spaces.

It differs from `imshow` in two ways:

- **Set `vmin`/`vmax` to your function's range.** GLE does not look for the smallest and largest value of an expression, so the colour scale runs from `vmin` to `vmax`, 0 to 1 by default. Values outside it are drawn in the end colours.
- **The map fills the whole graph.** `extent` sets the axis range, as an `imshow` extent does, but if other data or `set_xlim` widens the axes, GLE computes the expression over the wider range too.

Contours of an expression are not supported; sample the function into an array and use `contour`.

## `origin` — Read This Before You Get Flipped Data

`imshow`'s default is **`origin='lower'`**, which puts row 0 of `Z` at `ymin` — this **deviates from matplotlib**, whose `imshow` default is `origin='upper'` (row 0 at the top). gleplot chose `'lower'` because it matches the scientific/phase-diagram convention this feature was built for, and because GLE's own `.z` grid file format is y-increasing (row 0 = `ymin`) — `'lower'` is the identity mapping with no row-flipping needed.

If your `Z` array was built the way most image libraries build one (row 0 = top of the image), pass `origin='upper'` explicitly; gleplot flips the rows when writing the `.z` sidecar so the displayed orientation matches.

```python
ax.imshow(image_array, origin='upper')   # row 0 is the top row, like a typical image
ax.imshow(field_grid, origin='lower')    # row 0 is ymin, like np.meshgrid's row-0-is-y[0] layout (the default)
```

`tripcolor`/`tricontour` don't take an `origin` argument — they always store `origin='lower'`, since GLE's `fitz` gridding is inherently y-increasing.

## `vmin` / `vmax` (colour normalization)

`vmin`/`vmax` map to GLE's `zmin`/`zmax` colormap clauses. Leave them `None` to let GLE auto-scale to the data's own range (the `.z` file's or the scattered points' min/max, whichever applies). `function2d` has no data to scale to; see [Heatmap from an expression](#heatmap-from-an-expression).

```python
ax.imshow(Z, cmap='magma', vmin=-1, vmax=1)
```

**For scattered data (`tripcolor`), prefer setting `vmin`/`vmax` explicitly** rather than leaving them `None`. GLE's `fitz` step performs Akima network interpolation from your scattered samples, which can overshoot beyond your data's actual value range in sparsely-sampled regions — and if `vmax` is left `None`, GLE auto-scales the colormap from the **gridded** `.z` file's own range, so a single wild overshoot node can compress your entire real data range into a sliver at one end of the colour scale. Pinning `vmin`/`vmax` to the range you care about keeps the colour mapping stable and readable.

The palette subs **clamp** the normalized value into `[0, 1]`, so a grid node that overshoots above `vmax` (or dips below `vmin`) saturates at the palette's brightest (or darkest) end colour — the same "over"/"under" → end-colour behaviour matplotlib's default colormaps use — rather than producing stray speckles. A tight `vmax` set just above your physical peak is therefore safe. See `examples/advanced/phase_diagram.py` for a worked example.

## Palette Gallery

GLE draws every colormap. These names are drawn as they are:

| `cmap` name | Drawn by |
|---|---|
| `viridis` | `viridis` in GLE's `palettes.gle`. The default (`GLEGraphConfig.default_cmap`). |
| `magma`, `inferno`, `plasma`, `cividis` | The routines of the same names in `palettes.gle`. |
| `coolwarm` | `palette_blue_white_red` in GLE's `color.gle`: blue -> white -> red. |
| `gray` | GLE's built-in grayscale; emits no palette clause. |
| `rainbow` (alias `jet`) | GLE's built-in rainbow; emits `colormap ... color` instead of a `palette` clause. |

Each of these except `rainbow` also has a reversed form with `_r` appended, as in matplotlib: `cmap='coolwarm_r'` runs red to blue from `vmin` to `vmax`. The script includes the file a routine is in and calls it through a short sub, `cmap_<name>`, that clamps the value and, for a reversed map, reads it from 1 down to 0. A colorbar calls the same sub, so it shows a reversed map reversed too. `invert=True` flips the image the same way, and a colorbar for an inverted image draws the reversed palette to match; an inverted `rainbow` image's bar is not reversed, and `colorbar()` warns.

Per-point scatter colours and `contourf` bands call a palette sub for each value, which GLE's built-in rainbow is not: there, `rainbow` and `jet` are drawn as `viridis`, with a warning.

matplotlib's ColorBrewer names are accepted too, but GLE has no routine that draws them, so the call warns and draws the closest map above:

| `cmap` name | Drawn as |
|---|---|
| `Blues`, `BuGn`, `BuPu`, `GnBu`, `Greens`, `Oranges`, `OrRd`, `PuBu`, `PuBuGn`, `PuRd`, `Purples`, `RdPu`, `Reds`, `YlGn`, `YlGnBu`, `YlOrBr`, `YlOrRd` | `viridis_r`, light to dark as they are. |
| `Greys` | `gray_r`. |
| `BrBG`, `PiYG`, `PuOr`, `RdBu`, `RdGy`, `RdYlBu`, `RdYlGn`, `Spectral` | `coolwarm_r`, warm end first as they are. |
| `PRGn` | `coolwarm`. |
| `Accent`, `Dark2`, `Paired`, `Pastel1`, `Pastel2`, `Set1`, `Set2`, `Set3` | `rainbow`. |

Their `_r` forms take the reversed map (`RdBu_r` is `coolwarm`), and `rainbow_r` and `jet_r` are drawn as `rainbow`. Names are matched case-insensitively. Unknown names raise `ValueError` listing the supported set.

## One Heatmap Per Axes

GLE draws one `colormap` per graph: a second `colormap` statement replaces the first rather than drawing over it, and wrapping each in a `begin layer` block does not change that. A colormap is also always opaque — GLE has no transparency for it — so matplotlib's pattern of blending two images with `alpha` cannot be drawn. Calling `imshow`/`pcolormesh`/`contourf`/`tripcolor` a second time on the same `Axes` therefore raises `ValueError`:

```python
ax.imshow(Z1)
ax.imshow(Z2)  # ValueError: GLE supports at most one heatmap (colormap) per axes
```

Contour lines have no such limit — you can layer multiple `contour`/`tricontour` calls (e.g. one heatmap plus several contour overlays at different levels) on the same axes. To show a second field over a heatmap, draw it as contours.

## Colorbars

`fig.colorbar()` with no heatmap named attaches to the figure's only heatmap. In a grid of heatmaps, pass the heatmap `imshow` (or `pcolormesh`, `tripcolor`) returned, and each axes gets its own bar on its own scale:

```python
import numpy as np
import gleplot as glp

y, x = np.mgrid[0:20, 0:30]
fig, (a, b) = glp.subplots(1, 2, figsize=(10, 4))
ha = a.imshow(np.sin(x / 5.0) * np.cos(y / 4.0), cmap='viridis')
hb = b.imshow(100.0 * x * y, cmap='magma')
fig.colorbar(ha, ax=a, label='amplitude')
fig.colorbar(hb, ax=b, orientation='horizontal', label='counts')
fig.savefig('two_bars.pdf')
```

A vertical bar sits `sep` cm to the right of its axes. A horizontal bar spans its axes' width, below the x tick labels and title; its `sep` is measured from the frame's bottom edge, and the default clears them at the figure's font size when `colorbar()` is called. `width` is the bar's thickness either way. The bar is drawn by `color_range_vertical` or `color_range_horizontal` from GLE's include library (`color.gle`, see [GLE's include library](https://benhuddart.github.io/gleplot/getting_started.html#gle-s-include-library)), and its `label` is written beside it as plain text: rotated, to the right of a vertical bar's tick numbers, or centred under a horizontal one's. The tick labels default to fixed-point with as many decimals as the first value and the tick step need (`format=` overrides it). The subplot grid makes room for every bar: a vertical bar widens the gap to the right of its column, a horizontal bar the gap below its row, and a bar on the last column or row widens the page margin instead.

`ax` must be the axes holding the heatmap: the bar is drawn beside its own heatmap's axes. `cax` is not supported. Passing it warns, and the bar is drawn beside the heatmap's axes.

A scatter coloured by value (`scatter(x, y, c=values, cmap=...)`) gets a bar the same way. `scatter` returns the axes, not a mappable, so pick the scatter by its axes; on an axes with no heatmap, the bar shows the colour-mapped scatter drawn last, from its `vmin` to its `vmax`:

```python
import gleplot as glp

fig, ax = glp.subplots()
ax.scatter([1, 2, 3, 4], [1, 4, 9, 16], c=[0, 100, 200, 300], cmap='viridis')
fig.colorbar(ax=ax, label='T (K)')
fig.savefig('scatter_bar.pdf')
```

The bar of a `contourf` shows its bands, from the first level to the last. With evenly spaced levels it is ticked at the levels: every `ceil(len(levels) / 10)`-th level from the first, with `nticks` in place of the 10. GLE's colorbar ticks in equal steps along a linear scale, so with uneven levels each band takes room in proportion to its range and the ticks are `nticks` (default 5) equal steps; `colorbar()` warns. It draws no triangular end caps for `extend`, and warns when `extend` is set.

## Contour Smoothing

GLE's `begin contour` block accepts a `smooth <integer>` line, but GLE reads the number and never uses it: the traced lines are the same with or without it. gleplot therefore offers no smoothing option on `contour`/`tricontour`. For smoother contour lines, use a finer grid (more points in `Z`, or a larger `gridsize` for `tricontour`).

## Data Requirements

GLE's colormap/contour grid has no missing-value support and requires ascending axis ranges, so gleplot validates these at call time and raises a clear `ValueError` rather than emitting a `.gle` that breaks at compile:

- **Finite values only.** A `NaN` or infinity anywhere in `Z` (or in scattered `x`/`y`/`z`) is rejected — GLE's `.z` reader has no transparent/masked pixel (unlike matplotlib's `imshow`, which renders `NaN` and masked cells transparent). A masked cell in `imshow`'s `Z` is rejected too. Fill missing cells before plotting, e.g. with `np.ma.filled(Z, value)`.
- **Ascending `extent`.** `extent` must have `xmin < xmax` and `ymin < ymax`; a reversed or degenerate extent is rejected (gleplot cannot express an axis flipped purely via `extent`).
- **In-range contour levels.** Explicit `contour` levels that all fall outside the grid's data range are rejected (no lines would be drawn, and GLE aborts on the resulting empty polyline file). A partially in-range level set is fine — the out-of-range ones are simply not drawn. (For `tricontour` the grid is interpolated at compile time, so its exact range isn't known in advance and this check isn't applied.)

A colorbar over a **constant** field (`zmax == zmin`) is drawn over one unit from that value, since GLE's colour range divides by its span.

## What Files gleplot Writes

- `imshow`/`pcolormesh`/`contourf`/gridded `contour` write a `.z` sidecar directly: a text header `! nx <nx> ny <ny> xmin <x0> xmax <x1> ymin <y0> ymax <y1>` followed by `ny` rows of `nx` values. A gridded `contour` writes the grid's extent in the header. An `imshow` or `contourf` writes its header one node spacing past the last node, with a `! gleplot: nodes xmin ... ymax ...` line under it, which GLE skips, holding the extent; a grid one node wide or tall has no spacing and is written like a `contour`'s. A `.z` file without that line, as earlier versions of gleplot wrote for `imshow`, still loads, over its header's range. A `pcolormesh` sidecar has one more row and column; see [Cells with pcolormesh](#cells-with-pcolormesh) and [Filled contours with contourf](#filled-contours-with-contourf).
- `tripcolor`/`tricontour` write a points sidecar (`<prefix>_points<N>.dat`): raw whitespace-separated `x y z` triples, one per line, no header.
- `function2d` writes no file.
- These sidecars are **not** columnar data in the usual gleplot sense — they're excluded from the `! gleplot: import-data = ...` metadata comment (which only lists file-backed series you could re-import as columns).

At **GLE compile time** (not written by gleplot), GLE itself generates further files next to your `.gle` script:

- `begin fitz` grids a points sidecar into `<points-base>.z`, with `gridsize` nodes from the extent's first edge to its last. For a `tricontour` the header's range is the extent. For a `tripcolor` it reaches just short of one node spacing past the last node, as an `imshow` header does, so the heatmap lines up with a `tricontour` of the same points; a `! gleplot: nodes ...` line in the `begin fitz` block holds the extent. Axis limits beyond the extent show that extra spacing, and saving warns.
- `begin contour` on a `.z` file produces `<z-base>-cdata.dat` (the drawn polylines), and, when `clabel=True`, `<z-base>-clabels.dat` (label positions/values) and `<z-base>-cvalues.dat`.

These generated files only exist after compilation; `savefig()` (or the GLE binary itself) tolerates their absence beforehand, and you never need to create or manage them yourself.

## Worked Example: Antiferromagnet Phase Diagram

The canonical use case this feature was built for: plotting a magnetic-field/temperature phase diagram from noisy, scattered susceptibility measurements — the kind you'd actually get from an experiment (sweeping temperature at each of several fixed applied fields), not from a clean grid.

The synthetic data models a susceptibility `chi(T, H)` that peaks along a Néel transition boundary:

```
T_N(H) = T_N0 * sqrt(1 - (H / Hc)^2)
```

with the peak broadening as `H` approaches the critical field `Hc` (critical broadening).

```python
import numpy as np
import gleplot as glp

rng = np.random.default_rng(11)
T_N0, Hc = 30.0, 9.5
chi0, amplitude = 0.05, 1.0

n_points = 3200
H = rng.uniform(0.0, 0.92 * Hc, n_points)
T = rng.uniform(1.5, 1.15 * T_N0, n_points)

T_N = T_N0 * np.sqrt(1.0 - (H / Hc) ** 2)
width = 2.0 + 1.4 * (H / Hc)
chi = chi0 + amplitude * np.exp(-((T - T_N) ** 2) / (2.0 * width**2))
chi += rng.normal(0.0, 0.015 * amplitude, n_points)

fig = glp.figure(figsize=(9, 6.5))
ax = fig.add_subplot(111)

ax.tripcolor(T, H, chi, gridsize=(90, 70), cmap='magma', vmin=0.0, vmax=chi0 + 2.0 * amplitude)
ax.tricontour(
    T, H, chi, gridsize=(90, 70),
    levels=[chi0 + 0.55 * amplitude],
    colors='black', linewidths=1.3,
    clabel=True, clabel_fmt='fix 2',
)

ax.set_xlabel('Temperature (K)')
ax.set_ylabel('Magnetic field (T)')
fig.colorbar(label=r'\chi{} (emu mol^{-1})', format='fix 2')

fig.savefig('phase_diagram.pdf')
fig.savefig('phase_diagram.png')
```

(See [Greek letters and math in labels](#greek-letters-and-math-in-labels) below for the `\chi{}` label syntax.)

The full runnable version — `examples/advanced/phase_diagram.py` — adds a second panel of susceptibility line-cuts at representative fields, showing the peak shift and broadening as `H → Hc`. Run it (and the simpler `examples/basic/heatmap_imshow.py`) via:

```bash
cd examples
python advanced/phase_diagram.py
python basic/heatmap_imshow.py
```

## Greek Letters and Math in Labels

You can write labels in **either** matplotlib-style `$...$` mathtext **or** GLE's own TeX-like markup — both reach the same result. Every display string entering the model (axis titles, series `label=`, `title`/`text`, `colorbar(label=)`, …) is translated at store time by `gleplot.mathtext_to_gle`, so matplotlib users get Greek/math rendering without learning GLE markup.

To typeset labels with LaTeX itself instead, see `usetex` in the
[Configuration Guide](CONFIGURATION.md); the translation below is then skipped.

### matplotlib mathtext (`$...$`)

Anything between unescaped `$` delimiters is treated as math and translated to GLE markup; text outside the delimiters is escaped so it renders **literally** (see "Plain text is literal" below):

```python
ax.set_ylabel(r'$\chi_{mol}$ (emu mol$^{-1}$)')   # renders: χ_mol (emu mol⁻¹)
ax.set_title(r'Susceptibility $\chi$ vs $T$')      # renders: Susceptibility χ vs T
ax.plot(x, y, label=r'$\alpha$ decay')             # legend key: α decay
```

Translation rules:

- Greek letters / symbols GLE supports natively pass through: `\chi`, `\alpha`, `\Omega`, `\times`, `\pm`, `\cdot`, `\infty`, `\degree`, …
- Single-token sub/superscripts are braced automatically: `$x^2$` → `x^{2}`, `$x_i$` → `x_{i}`; already-braced forms (`$^{-1}$`) pass through.
- `\mathrm{…}`/`\text{…}` → `{\rm …}`, `\mathit{…}` → `{\it …}`, `\mathbf{…}` → `{\bf …}`, `\mathtt{…}` → `{\tt …}`. Families GLE has no inline font for (`\mathsf`, `\mathcal`, `\mathbb`) degrade to their contents.
- `\frac{a}{b}` degrades to `a/b` (GLE has no inline `\frac`).
- Spacing macros `\,` `\:` `\;` `\!` pass through; unknown macros pass through unchanged (GLE understands more than gleplot enumerates).
- `\$` is a literal dollar sign anywhere (not a delimiter). A string with an **odd/unmatched** `$` count is left completely unchanged (matplotlib would error; gleplot degrades gracefully rather than guess).

### Plain text is literal

GLE's text engine is TeX-ish everywhere, not only inside math: a bare `_` or `^` starts a sub/superscript and braces group silently. gleplot follows matplotlib's contract instead — **a plain string renders literally, and math is opt-in via `$...$`** — by escaping those characters outside math:

```python
ax.plot(x, y, label='lambda_tail')        # renders: lambda_tail  (not lambda_t ail)
ax.set_title('excluded: window_bias')     # renders: excluded: window_bias
ax.text(1, 1, 'set {a, b} at x^2')        # renders: set {a, b} at x^2
```

Two things are deliberately *not* escaped, because they are gleplot's opt-in to GLE's own markup (see below): a **backslash**, and a **braced** script `_{…}` / `^{…}`.

### GLE markup (direct)

Direct GLE markup still works — a backslash outside `$...$` opens GLE's text commands:

- Greek letters and symbols use backslash escapes: `\chi`, `\alpha`, `\Omega`, `\mu`, `\pi`, …
- Subscripts/superscripts use **braces**: `T_{N}`, `mol^{-1}`, `10^{-3}`. The braces are what marks them as markup; a bare `T_N` renders literally as `T_N`.
- Font groups work: `{\bf bold}`, `{\it italic}`, `{\rm roman}`.
- A literal character GLE would otherwise eat can always be written `\char{n}` — `\char{95}` underscore, `\char{94}` caret, `\char{123}`/`\char{125}` braces. (`\_` is the underscore too; `\^` and `\{` are *accents*, not literals.)
- Use Python **raw strings** so the backslash reaches GLE intact: `r'\chi'`, not `'\chi'` (which Python would treat as an invalid escape).

```python
fig.colorbar(label=r'\chi{} (emu mol^{-1})')   # renders: χ (emu mol⁻¹)
ax.set_ylabel(r'T_{N} (K)')                    # renders: T_N (K)
```

**The swallowed-space gotcha:** GLE (like TeX) eats the single space immediately after a macro name, so `r'\chi (emu ...)'` renders as `χ(emu ...)` with **no gap**. When a space must follow a macro, terminate it with an empty group `{}` — `r'\chi{} (emu ...)'` — or let a following brace group do it, as in `r'\chi_{mol} (emu ...)'`. Both preserve the space. When translating `$...$` mathtext, gleplot inserts this `{}` for you at math→text boundaries, so `r'$\chi$ (emu/mol)'` becomes `\chi{} (emu/mol)` automatically.

## See Also

- `examples/basic/heatmap_imshow.py` — simple gridded `imshow` + `contour` + colorbar.
- `examples/advanced/phase_diagram.py` — the full susceptibility phase-diagram example.
- [Colors and Markers](COLORS_AND_MARKERS.md) — matplotlib-style color/marker name mapping (contour `colors=` uses the same mapping).
- [File-Based Series](FILE_BASED_SERIES.md) — for plotting from pre-existing columnar data files (not applicable to the raw `.z`/points sidecars described here).
