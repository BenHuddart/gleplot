# Contour Plots and Heatmaps

gleplot can render 2-D scalar fields as heatmaps (matplotlib's `imshow`/`tripcolor`) and contour lines (`contour`/`tricontour`), with an optional colorbar. Under the hood these compile to GLE `colormap` / `begin contour` / `begin fitz` constructs, with self-contained colour-palette subroutines written directly into the `.gle` script — no `gle-library` include is required to compile the output.

## Supported Methods

- `Axes.imshow(Z, extent=None, origin='lower', cmap=None, vmin=None, vmax=None, interpolation='bicubic', pixels=None, invert=False, label=None)` — heatmap of a **gridded** 2-D array.
- `Axes.contour(*args, levels=None, colors='black', linewidths=1.0, linestyles='-', clabel=False, clabel_fmt='fix 1', label=None)` — contour lines of **gridded** data. Call as `contour(Z)` or `contour(x, y, Z)`.
- `Axes.tripcolor(x, y, z, gridsize=(50, 50), extent=None, **imshow_kwargs)` — heatmap of **scattered** `(x, y, z)` samples, gridded by GLE at compile time.
- `Axes.tricontour(x, y, z, gridsize=(50, 50), extent=None, ncontour=3, **contour_kwargs)` — contour lines of **scattered** `(x, y, z)` samples.
- `Figure.colorbar(label=None, format='fix 1', nticks=None, width=0.5, sep=0.3)` — attaches a vertical colorbar to the figure's single heatmap-bearing axes.

Each has a module-level convenience wrapper too: `glp.imshow(...)`, `glp.contour(...)`, `glp.tripcolor(...)`, `glp.tricontour(...)`, `glp.colorbar(...)` (they operate on `gca()`/`gcf()`, matching `glp.plot()` and friends).

There is no `pcolormesh` alias and no 3-D surface support — gleplot only targets 2-D colormap/contour output.

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

`contour`'s `levels` argument accepts:

- `None` (default) — GLE's own default of 10 automatic levels.
- An `int` `n` — resolved **at call time** into `n` explicit level values evenly spaced strictly between the data's min and max, and emitted as an explicit `values v1 v2 ...` list (not GLE's `values from a to b step s` form). This keeps the stored model self-contained and round-trip-safe, but means the levels are fixed to the data range at the moment you call `contour`/`tricontour`, not re-derived later.
- An explicit sequence, e.g. `levels=[0.2, 0.5, 0.8]` — stored verbatim.

Add `clabel=True` to draw inline value labels at each contour crossing (formatted with `clabel_fmt`, a GLE `format$` string such as `'fix 1'` or `'fix 2'`):

```python
ax.contour(x, y, Z, levels=[0.2, 0.5, 0.8], colors='black', clabel=True, clabel_fmt='fix 2')
```

## `origin` — Read This Before You Get Flipped Data

`imshow`'s default is **`origin='lower'`**, which puts row 0 of `Z` at `ymin` — this **deviates from matplotlib**, whose `imshow` default is `origin='upper'` (row 0 at the top). gleplot chose `'lower'` because it matches the scientific/phase-diagram convention this feature was built for, and because GLE's own `.z` grid file format is y-increasing (row 0 = `ymin`) — `'lower'` is the identity mapping with no row-flipping needed.

If your `Z` array was built the way most image libraries build one (row 0 = top of the image), pass `origin='upper'` explicitly; gleplot flips the rows when writing the `.z` sidecar so the displayed orientation matches.

```python
ax.imshow(image_array, origin='upper')   # row 0 is the top row, like a typical image
ax.imshow(field_grid, origin='lower')    # row 0 is ymin, like np.meshgrid's row-0-is-y[0] layout (the default)
```

`tripcolor`/`tricontour` don't take an `origin` argument — they always store `origin='lower'`, since GLE's `fitz` gridding is inherently y-increasing.

## `vmin` / `vmax` (colour normalization)

`vmin`/`vmax` map to GLE's `zmin`/`zmax` colormap clauses. Leave them `None` to let GLE auto-scale to the data's own range (the `.z` file's or the scattered points' min/max, whichever applies).

```python
ax.imshow(Z, cmap='magma', vmin=-1, vmax=1)
```

**For scattered data (`tripcolor`), prefer setting `vmin`/`vmax` explicitly** rather than leaving them `None`. GLE's `fitz` step performs Akima network interpolation from your scattered samples, which can overshoot beyond your data's actual value range in sparsely-sampled regions — and if `vmax` is left `None`, GLE auto-scales the colormap from the **gridded** `.z` file's own range, so a single wild overshoot node can compress your entire real data range into a sliver at one end of the colour scale. Pinning `vmin`/`vmax` to the range you care about keeps the colour mapping stable and readable.

gleplot's generated palette subroutines **clamp** the normalized value into `[0, 1]`, so a grid node that overshoots above `vmax` (or dips below `vmin`) saturates at the palette's brightest (or darkest) end colour — the same "over"/"under" → end-colour behaviour matplotlib's default colormaps use — rather than producing stray speckles. A tight `vmax` set just above your physical peak is therefore safe. See `examples/advanced/phase_diagram.py` for a worked example.

## Palette Gallery

| `cmap` name | Notes |
|---|---|
| `viridis` | Default (`GLEGraphConfig.default_cmap`). Perceptually uniform. |
| `magma` | Perceptually uniform, dark-to-light. |
| `inferno` | Perceptually uniform, dark-to-light. |
| `plasma` | Perceptually uniform, dark-to-light. |
| `cividis` | Perceptually uniform, colourblind-safe. |
| `coolwarm` | Diverging blue -> white -> red. |
| `gray` | GLE's built-in grayscale; emits no palette clause. |
| `rainbow` (alias `jet`) | GLE's built-in rainbow; emits `colormap ... color` instead of a `palette` clause. |

Unknown names raise `ValueError` listing the supported set. `viridis`/`magma`/`inferno`/`plasma`/`cividis` are transcribed from `gle-library`'s `include/palettes.gle` RGB stop tables; `coolwarm` from `include/color.gle`'s `palette_blue_white_red`. All are emitted as self-contained `sub gleplot_<name> z ... end sub` subroutines directly in the `.gle` script (deduplicated — only palettes actually used are written), so the output compiles without the `gle-library` on the include path.

## One Heatmap Per Axes

GLE supports at most one `colormap` per graph. Calling `imshow`/`tripcolor` a second time on the same `Axes` raises `ValueError`:

```python
ax.imshow(Z1)
ax.imshow(Z2)  # ValueError: GLE supports at most one heatmap (colormap) per axes
```

Contour lines have no such limit — you can layer multiple `contour`/`tricontour` calls (e.g. one heatmap plus several contour overlays at different levels) on the same axes.

## Data Requirements

GLE's colormap/contour grid has no missing-value support and requires ascending axis ranges, so gleplot validates these at call time and raises a clear `ValueError` rather than emitting a `.gle` that breaks at compile:

- **Finite values only.** A `NaN` or infinity anywhere in `Z` (or in scattered `x`/`y`/`z`) is rejected — GLE's `.z` reader has no transparent/masked pixel (unlike matplotlib's `imshow`, which renders `NaN` transparent). Mask or fill missing cells before plotting.
- **Ascending `extent`.** `extent` must have `xmin < xmax` and `ymin < ymax`; a reversed or degenerate extent is rejected (gleplot cannot express an axis flipped purely via `extent`).
- **In-range contour levels.** Explicit `contour` levels that all fall outside the grid's data range are rejected (no lines would be drawn, and GLE aborts on the resulting empty polyline file). A partially in-range level set is fine — the out-of-range ones are simply not drawn. (For `tricontour` the grid is interpolated at compile time, so its exact range isn't known in advance and this check isn't applied.)

A colorbar over a **constant** field (`zmax == zmin`) is handled gracefully — the generated colorbar subroutine expands the degenerate range to a nominal unit span so the bar still renders instead of dividing by zero.

## What Files gleplot Writes

- `imshow`/gridded `contour` write a `.z` sidecar directly: a text header `! nx <nx> ny <ny> xmin <x0> xmax <x1> ymin <y0> ymax <y1>` followed by `ny` rows of `nx` values.
- `tripcolor`/`tricontour` write a points sidecar (`<prefix>_points<N>.dat`): raw whitespace-separated `x y z` triples, one per line, no header.
- These sidecars are **not** columnar data in the usual gleplot sense — they're excluded from the `! gleplot: import-data = ...` metadata comment (which only lists file-backed series you could re-import as columns).

At **GLE compile time** (not written by gleplot), GLE itself generates further files next to your `.gle` script:

- `begin fitz` grids a points sidecar into `<points-base>.z`.
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

### matplotlib mathtext (`$...$`)

Anything between unescaped `$` delimiters is treated as math and translated to GLE markup; text outside the delimiters passes through verbatim:

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

### GLE markup (direct)

Direct GLE markup still works — a string with no `$` is passed through byte-for-byte:

- Greek letters and symbols use backslash escapes: `\chi`, `\alpha`, `\Omega`, `\mu`, `\pi`, …
- Subscripts/superscripts use braces: `T_{N}`, `mol^{-1}`, `10^{-3}`.
- Use Python **raw strings** so the backslash reaches GLE intact: `r'\chi'`, not `'\chi'` (which Python would treat as an invalid escape).

```python
fig.colorbar(label=r'\chi{} (emu mol^{-1})')   # renders: χ (emu mol⁻¹)
ax.set_ylabel(r'T_{N} (K)')                    # renders: T_N (K)
```

**The swallowed-space gotcha:** GLE (like TeX) eats the single space immediately after a macro name, so `r'\chi (emu ...)'` renders as `χ(emu ...)` with **no gap**. When a space must follow a macro, terminate it with an empty group `{}` — `r'\chi{} (emu ...)'` — or let a following brace group do it, as in `r'\chi_{mol} (emu ...)'`. Both preserve the space. When translating `$...$` mathtext, gleplot inserts this `{}` for you at math→text boundaries, so `r'$\chi$ (emu/mol)'` becomes `\chi{} (emu/mol)` automatically.

## See Also

- `examples/basic/heatmap_imshow.py` — simple gridded `imshow` + `contour` + colorbar.
- `examples/advanced/phase_diagram.py` — the full susceptibility phase-diagram example.
- `docs/guides/COLORS_AND_MARKERS.md` — matplotlib-style color/marker name mapping (contour `colors=` uses the same mapping).
- `docs/guides/FILE_BASED_SERIES.md` — for plotting from pre-existing columnar data files (not applicable to the raw `.z`/points sidecars described here).
