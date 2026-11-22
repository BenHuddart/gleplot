# Colors and Markers Reference

This guide lists the color and marker names supported by gleplot's conversion utilities.

## Color Mapping

gleplot accepts matplotlib-style color inputs and converts them to a GLE color token:

- a **recognized GLE color name** (in any case) is emitted as that name -- `color RED`;
- **anything else** is emitted as an **exact** GLE color expression -- `color rgb255(140,140,140)`.

No requested color is ever replaced by an approximation. `#8c8c8c` renders as
`#8c8c8c`, and two series given two different colors always get two different
colors in the script.

A series given no color takes the next color of its axes' cycle, `C0` to
`C9`, as in matplotlib; see "Default colours" in the
[Matplotlib Migration Guide](MATPLOTLIB_MIGRATION.md).

### Matplotlib single-letter colors

- `b` -> `BLUE`
- `g` -> `GREEN`
- `r` -> `RED`
- `c` -> `CYAN`
- `m` -> `MAGENTA`
- `y` -> `YELLOW`
- `k` -> `BLACK`
- `w` -> `WHITE`

### Named colors supported directly

Common matplotlib spellings:

- `blue`, `green`, `red`, `cyan`, `magenta`, `yellow`, `black`, `white`
- `orange`, `purple`, `brown`, `pink`
- `gray`/`grey`, `lightgray`/`lightgrey`, `darkgray`/`darkgrey`
- `lightblue`, `lightgreen`, `lightcyan`
- `darkblue`, `darkgreen`, `darkred`

Plus **every color name GLE itself knows** (the 151 SVG names and the
`GRAY1`..`GRAY90` ramp), in any case -- `salmon`, `SteelBlue`, `gray30`, ... .
These are emitted verbatim as names. The authoritative list is
`gleplot.parser.tables.COLORS`.

### Accepted non-name color inputs

All of these emit as an exact `rgb255(r,g,b)` expression:

- Hex format: `#RRGGBB` (for example `#1f77b4`) or the `#RGB` shorthand
  (`#bbb`). An alpha, `#RRGGBBAA` or `#RGBA`, is not applied, and below
  opaque warns, as for an RGB tuple.
- RGB tuple, list or 1-D numpy array in [0, 1]: `(0.1, 0.2, 0.8)` (components
  outside [0, 1] are clamped). A fourth, alpha component is applied only by
  `hist`; elsewhere an alpha below 1 warns, see the
  [Matplotlib Migration Guide](MATPLOTLIB_MIGRATION.md).
- A grey level as a number string in [0, 1]: `'0.3'`, as matplotlib accepts.
  A number string outside [0, 1] raises `ValueError`.
- matplotlib's default property cycle, by cycle reference or `tab:` name:
  `C0`..`C9`, `tab:blue`, `tab:orange`, ..., `tab:cyan`. All ten are distinct
  colors, so a ten-series figure using the default cycle stays readable.
  `C10` and beyond wrap round the ten, as in matplotlib.
- An already-formed GLE color expression, e.g. `rgb255(140,140,140)` or
  `rgb(0.55,0.4,0.74)`, which is passed through (whitespace normalized). This
  is what makes colors survive an `open_gle()` round trip unchanged.

Two matplotlib colours have no counterpart here and warn, drawing in
`BLACK`: `'none'`, where the element has no way to be left undrawn, and the
`xkcd:` names, which gleplot has no table for (pass the hex value instead).

Anything else raises when the call is made: an unknown name, a malformed hex
string or a sequence of fewer than three numbers raises `ValueError`, and a
value of another type, such as a float or bytes, raises `TypeError`. A
sequence of more than four values warns and uses the first three.
`open_gle()` keeps a colour it cannot read, such as a variable the script
defines, as it is.

### GLE version

`rgb255(r,g,b)` and `rgb(r,g,b)` are part of GLE's own color syntax and are
accepted anywhere a color name is -- `d1 line color ...`, `d1 marker ... color
...`, `bar dN fill ...`, `fill dA,dB color ...`, `set color ...`. gleplot
already requires **GLE 4.3+** for compilation (see the README); the emitted
expressions are verified against GLE 4.3.10. Nothing here needs a newer GLE
than gleplot already asked for.

## Marker Mapping

gleplot accepts matplotlib marker symbols and maps them to GLE marker types.
**Every code in matplotlib's standard string marker set is mapped**, so no
valid matplotlib marker silently turns into a circle.

Marker codes are case-significant, exactly as in matplotlib. Where matplotlib
distinguishes a pair by case, gleplot keeps them visually distinct by giving
the uppercase code the filled GLE glyph and the lowercase one the outline
glyph.

### Common matplotlib markers

- `o` -> `FCIRCLE`
- `s` -> `FSQUARE`
- `^` -> `FTRIANGLE`
- `v` -> `FTRIANGLED`
- `D` -> `FDIAMOND`
- `d` -> `DIAMOND` (thin diamond -- outline partner of `D`)
- `*` -> `FSTARR`
- `+` / `P` -> `PLUS`
- `x` / `X` -> `PCROSS`
- `.` / `,` -> `DOT`

### Additional accepted symbols

- `<`, `>` -> `TRIANGLE`
- `1` -> `TRIANGLED`; `2`, `3`, `4` -> `TRIANGLE` (matplotlib's `tri_*`
  markers are the spokes of a triangle; GLE has no such glyph, and no
  directed triangle, so left/right collapse onto `TRIANGLE` as `<`/`>` do)
- `8` -> `FCIRCLE` (a filled octagon at marker sizes is a filled circle)
- `p` -> `STARR`
- `H` -> `HEART`
- `h` -> `DIAMOND`
- `|`, `_` -> `PLUS`

### Not mapped

matplotlib's **integer** markers -- `0`-`3` (`tickleft`, `tickright`,
`tickup`, `tickdown`) and `4`-`11` (the carets) -- have no GLE counterpart:
they are line segments and wedges drawn beside a point, not symbols centred
on it. They fall back to the default marker (`FCIRCLE`) rather than being
approximated. Note that they are a separate namespace from the string codes:
the integer `1` is `tickright`, the string `'1'` is `tri_down`.

### Native GLE marker names

You can also use GLE names directly (any case — `wcircle` and `WCIRCLE` both
work). They are validated against GLE's own marker table, so a name GLE would
reject at compile time is caught in Python first:

- Filled: `FCIRCLE`, `FSQUARE`, `FTRIANGLE`, `FTRIANGLED`, `FDIAMOND`, `FSTARR`
- Outline (transparent): `CIRCLE`, `SQUARE`, `TRIANGLE`, `TRIANGLED`, `DIAMOND`, `STARR`
- Outline (white fill): `WCIRCLE`, `WSQUARE`, `WTRIANGLE`, `WTRIANGLED`, `WDIAMOND`, `WSTARR`
- Symbols: `DOT`, `PLUS`, `PCROSS`, `CROSS`, `CLUB`, `HEART`, `SPADE`, `STAR`, `DAG`, `DDAG`, `SNAKE`

## Open (unfilled) markers

Filled-vs-open markers are a standard way to distinguish two datasets in one
panel (e.g. zero-field vs longitudinal-field muon data). Both matplotlib
spellings are accepted by `plot`, `scatter`, `errorbar` and
`errorbar_from_file`:

```python
ax.errorbar(t, a1, yerr=e1, marker='o', linestyle='none', label='2 K')                   # filled
ax.errorbar(t, a2, yerr=e2, marker='o', linestyle='none', fillstyle='none', label='20 K')  # open
ax.errorbar(t, a3, yerr=e3, marker='o', linestyle='none', mfc='none')                     # same thing
ax.scatter(x, y, marker='s', markerfacecolor='white')                               # white-filled
```

There are three fill modes, matching the three GLE marker families:

| Request | GLE family | Appearance |
|---|---|---|
| default | `FCIRCLE`, `FSQUARE`, … | solid |
| `fillstyle='none'` or `markerfacecolor='none'` (or `mfc='none'`) | `CIRCLE`, `SQUARE`, … | outline, **transparent** — a line or error bar underneath shows through |
| `markerfacecolor='white'` (or `'w'`, `'#ffffff'`) | `WCIRCLE`, `WSQUARE`, … | outline, **opaque white** interior that masks what is underneath |

`fillstyle` wins when both are given (as in matplotlib). Shapes with no filled
counterpart (`PLUS`, `PCROSS`, `DOT`, `CROSS`, …) are strokes rather than
areas and are returned unchanged by any fill mode.

Two constraints worth knowing:

- matplotlib's *partial* fill styles (`'top'`, `'bottom'`, `'left'`, `'right'`)
  have no GLE equivalent; they warn and fall back to a solid marker.
- A GLE marker is drawn in **one** colour, so a `markerfacecolor` that is
  neither `'none'` nor white cannot be represented (edge and face colours
  cannot differ). Such a value warns and is ignored.

The `fill=` argument of `gleplot.markers.get_gle_marker` and
`gleplot.markers.apply_marker_fill` expose the same mapping directly, and
`gleplot.markers.MATPLOTLIB_TO_GLE_OUTLINE_MARKERS` /
`MATPLOTLIB_TO_GLE_WHITE_MARKERS` are the full derived tables.

## Line Style Mapping

Matplotlib `linestyle` strings map onto GLE `lstyle` integers. Solid lines emit
no `lstyle` token at all, since GLE's own default is style 1.

| matplotlib | GLE `lstyle` | Renders as |
| ---------- | ------------ | ---------- |
| `'-'`      | 1 (implicit) | solid |
| `'--'`     | 3            | dashed |
| `':'`      | 2            | dotted |
| `'-.'`     | 6            | dash-dot |

The integers are GLE's built-in style table, not a gleplot convention. Compiling
a ruler of `set lstyle 1..9` strokes through GLE 4.3.10 gives:

    1 solid   2 dotted   3 dashed   4 dotted (sparse)   5 dashed (long)
    6 dash-dot   7 dash-dot (sparse)   8 dash-dot (dense)   9 dashed (long)

Only the four styles in the table are reachable from a matplotlib `linestyle`
string; the rest are available by overriding
`GLEStyleConfig.line_style_dashed` / `line_style_dotted` / `line_style_dashdot`
(see [CONFIGURATION.md](CONFIGURATION.md)). The parser derives its inverse table
from those same fields, so reading a `.gle` file back in always agrees with what
the writer emits.

## Practical Notes

- Marker size in `plot` and `errorbar` uses `markersize` (matplotlib's `Line2D`
  convention -- a diameter in points) and is scaled internally for GLE.
- Marker size in `scatter` takes **either** convention:
  - `s` -- matplotlib's `scatter` size, an *area* in points<sup>2</sup>
    (gleplot's default is `s=20`). Converted with the square-root relation
    matplotlib defines between area and diameter, `markersize = sqrt(s)`,
    times gleplot's 1.2 visibility factor. Quadrupling `s` doubles the marker.
  - `markersize` -- a *diameter* in points, used as given. A `scatter` and a
    `plot` asking for the same `markersize` draw the same marker.

  Passing **both is ambiguous, and `markersize` wins**: it is a size rather
  than an area, so honouring it needs no conversion.
- Per-point sizes make a bubble chart: pass one value per point for `s` or
  `markersize`, e.g. `ax.scatter(x, y, s=population / 1e6)`. GLE scales a
  marker per point (`mdata`) only when a subroutine draws it, so the script
  gets a `glp_mdata_<marker>` sub that draws the built-in marker, and the
  sizes go into the series' data file as an extra column. The legend marker's
  area is halfway between the largest and smallest point's, as in
  matplotlib's legend. Sizes must not be negative or infinite, and cannot be
  combined with `mdist` or `deresolve`; a NaN or masked size leaves that
  point out, as in matplotlib.
- Per-point colours work the same way: `ax.scatter(x, y, c=temperature,
  cmap='viridis', vmin=0, vmax=300)` gets a `glp_cdata_<marker>_<cmap>`
  sub, the values go into the data file, and a `let` maps them onto the
  colormap. `c` may also be one colour, or one colour per point, which draws
  one series per colour. With per-point sizes as well, the colours are drawn
  at one size, with a warning. `fig.colorbar(ax=ax)` shows the colour scale; see "Colorbars" in
  [Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md). See "Scatter colours" in the
  [Matplotlib Migration Guide](MATPLOTLIB_MIGRATION.md) for how they differ
  from matplotlib.
- Error bars take the series `color`, and so do their caps -- including bars-only
  series (`fmt='none'`, no marker and no line) and `capsize=0`. GLE draws error
  bars in the dataset's colour and an unstyled dataset renders black, so gleplot
  always emits a `color` qualifier on an errorbar dataset. That qualifier carries
  the exact colour, `rgb255(...)` included.
- `gleplot.colors.gle_color_to_rgb255()` inverts a stored colour token -- a name
  or an `rgb255(...)`/`rgb(...)` expression -- back to an `(r, g, b)` triple.
- To snap a colour to the nearest *named* GLE colour on purpose, call
  `gleplot.parser.tables.nearest_gle_color(r, g, b)` and pass the name it
  returns.
- An **unrecognized marker** (neither a matplotlib code nor a GLE marker name)
  falls back to `FCIRCLE` *and emits a `UserWarning`*.
- A few long-standing mappings point at outline shapes because GLE has no
  filled counterpart at all: `<`/`>` → `TRIANGLE` (GLE has no sideways
  triangle), `p` → `STARR`, `h` → `DIAMOND`. These are kept verbatim so
  existing scripts render identically.
