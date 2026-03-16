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

You can also use GLE names directly:

- Filled: `FCIRCLE`, `FSQUARE`, `FTRIANGLE`, `FTRIANGLED`, `FDIAMOND`, `FSTARR`
- Outline: `CIRCLE`, `SQUARE`, `TRIANGLE`, `TRIANGLED`, `DIAMOND`, `STARR`
- Symbols: `DOT`, `PLUS`, `PCROSS`, `CROSS`, `CLUB`, `HEART`, `SPADE`, `STAR`, `DAG`, `DDAG`, `SNAKE`

## Practical Notes

- Marker size in `plot` and `errorbar` uses `markersize` (matplotlib-style) and is scaled internally for GLE.
- Marker size in `scatter` uses `s` (area-like style) and is converted to a GLE marker size.
- If a color or marker cannot be resolved, gleplot falls back to defaults (`BLACK` for color, `FCIRCLE` for marker).
