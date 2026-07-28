# Colors and Markers Reference

This guide lists the color and marker names supported by gleplot's conversion utilities.

## Color Mapping

gleplot accepts matplotlib-style color inputs and converts them to GLE names.

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

- `blue`, `green`, `red`, `cyan`, `magenta`, `yellow`, `black`, `white`
- `orange`, `purple`, `brown`, `pink`
- `gray`/`grey`, `lightgray`/`lightgrey`, `darkgray`/`darkgrey`
- `lightblue`, `lightgreen`, `lightcyan`
- `darkblue`, `darkgreen`, `darkred`

### Accepted non-name color inputs

- Hex format: `#RRGGBB` (for example `#1f77b4`)
- RGB tuple/list in [0, 1]: `(0.1, 0.2, 0.8)`

## Marker Mapping

gleplot accepts matplotlib marker symbols and maps them to GLE marker types.

### Common matplotlib markers

- `o` -> `FCIRCLE`
- `s` -> `FSQUARE`
- `^` -> `FTRIANGLE`
- `v` -> `FTRIANGLED`
- `D` -> `FDIAMOND`
- `*` -> `FSTARR`
- `+` / `P` -> `PLUS`
- `x` / `X` -> `PCROSS`
- `.` / `,` -> `DOT`

### Additional accepted symbols

- `<`, `>` -> `TRIANGLE`
- `p` -> `STARR`
- `H` -> `HEART`
- `h` -> `DIAMOND`
- `|`, `_` -> `PLUS`

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
ax.errorbar(t, a1, yerr=e1, marker='o', fmt='none', label='2 K')                   # filled
ax.errorbar(t, a2, yerr=e2, marker='o', fmt='none', fillstyle='none', label='20 K')  # open
ax.errorbar(t, a3, yerr=e3, marker='o', fmt='none', mfc='none')                     # same thing
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

## Practical Notes

- Marker size in `plot` and `errorbar` uses `markersize` (matplotlib-style) and is scaled internally for GLE.
- Marker size in `scatter` uses `s` (area-like style) and is converted to a GLE marker size.
- If a color cannot be resolved, gleplot falls back to `BLACK`.
- An **unrecognized marker** (neither a matplotlib code nor a GLE marker name)
  falls back to `FCIRCLE` *and emits a `UserWarning`*. It used to fall back
  silently, which turned a typo into a wrong-shaped marker with no indication
  anything had happened.
- A few long-standing mappings point at outline shapes because GLE has no
  filled counterpart at all: `<`/`>` → `TRIANGLE` (GLE has no sideways
  triangle), `p` → `STARR`, `h` → `DIAMOND`. These are kept verbatim so
  existing scripts render identically.
