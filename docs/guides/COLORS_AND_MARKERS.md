# Colors and Markers Reference

This guide lists the color and marker names supported by gleplot's conversion utilities.

## Color Mapping

gleplot accepts matplotlib-style color inputs and converts them to a GLE color token:

- a **recognized GLE color name** (in any case) is emitted as that name -- `color RED`;
- **anything else** is emitted as an **exact** GLE color expression -- `color rgb255(140,140,140)`.

No requested color is ever replaced by an approximation. `#8c8c8c` renders as
`#8c8c8c`, and two series given two different colors always get two different
colors in the script.

> **Before 1.8.2** a hex string or RGB tuple was snapped onto whichever of about
> eight named colors shared its dominant channel. That silently substituted a
> different color: `#8c8c8c` and `#999999` both rendered MAGENTA, `#bbbbbb`
> rendered WHITE (invisible on a white page), and `#9467bd` (matplotlib's tab
> purple) rendered MAGENTA -- so distinct series could collide onto one color
> with no warning. If you have a script or figure that relied on that behavior,
> name the color you want explicitly.

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

- Hex format: `#RRGGBB` (for example `#1f77b4`) or the `#RGB` shorthand (`#bbb`)
- RGB tuple/list in [0, 1]: `(0.1, 0.2, 0.8)` (components outside [0, 1] are clamped)
- matplotlib's default property cycle, by cycle reference or `tab:` name:
  `C0`..`C9`, `tab:blue`, `tab:orange`, ..., `tab:cyan`. All ten are distinct
  colors, so a ten-series figure using the default cycle stays readable.
- An already-formed GLE color expression, e.g. `rgb255(140,140,140)` or
  `rgb(0.55,0.4,0.74)`, which is passed through (whitespace normalized). This
  is what makes colors survive an `open_gle()` round trip unchanged.

### GLE version

`rgb255(r,g,b)` and `rgb(r,g,b)` are part of GLE's own color syntax and are
accepted anywhere a color name is -- `d1 line color ...`, `d1 marker ... color
...`, `bar dN fill ...`, `fill dA,dB color ...`, `set color ...`. gleplot
already requires **GLE 4.3+** for compilation (see the README); the emitted
expressions are verified against GLE 4.3.10. Nothing here needs a newer GLE
than gleplot already asked for.

## Marker Mapping

gleplot accepts matplotlib marker symbols and maps them to GLE marker types.
**Every code in matplotlib's standard string marker set is mapped** (as of
1.9.0), so no valid matplotlib marker silently turns into a circle.

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

You can also use GLE names directly:

- Filled: `FCIRCLE`, `FSQUARE`, `FTRIANGLE`, `FTRIANGLED`, `FDIAMOND`, `FSTARR`
- Outline: `CIRCLE`, `SQUARE`, `TRIANGLE`, `TRIANGLED`, `DIAMOND`, `STARR`
- Symbols: `DOT`, `PLUS`, `PCROSS`, `CROSS`, `CLUB`, `HEART`, `SPADE`, `STAR`, `DAG`, `DDAG`, `SNAKE`

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
  than an area, so honouring it needs no conversion. (Before 1.9.0 `markersize`
  was swallowed by `**kwargs` and silently ignored, drawing the default size.)
- Per-point sizes (`s=[10, 20, 30]`) are **not** supported and raise
  `ValueError`: GLE's `msize` is a per-dataset attribute, so one series draws
  one marker size. Plot one series per size. (Before 1.9.0 this emitted an
  array into the script -- `msize [0.094 0.212 0.284]` -- which is not valid
  GLE.)
- If a color or marker cannot be resolved, gleplot falls back to defaults (`BLACK` for color, `FCIRCLE` for marker).
- Error bars take the series `color`, and so do their caps -- including bars-only
  series (`fmt='none'`, no marker and no line) and `capsize=0`. GLE draws error
  bars in the dataset's colour and an unstyled dataset renders black, so gleplot
  always emits a `color` qualifier on an errorbar dataset. That qualifier carries
  the exact colour, `rgb255(...)` included.
- The GUI colour picker stores exactly the colour you picked (as `rgb255(...)`)
  and reopens on that same colour, rather than snapping it to the nearest
  palette entry.
- `gleplot.colors.gle_color_to_rgb255()` inverts a stored colour token -- a name
  or an `rgb255(...)`/`rgb(...)` expression -- back to an `(r, g, b)` triple.
- To snap a colour to the nearest *named* GLE colour on purpose, call
  `gleplot.parser.tables.nearest_gle_color(r, g, b)` and pass the name it
  returns.
