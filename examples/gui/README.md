# GUI Editor Example

A small, ready-to-open figure for the gleplot GUI editor (`gleplot-gui`).

## Files

- **`damped_oscillation.csv`** -- 100 rows of a simulated damped oscillation:
  `x`, `y_measured` (noisy), `yerr` (constant error estimate), `y_model`
  (the noise-free curve). Load this in the Data dock to try column picking
  and series creation from scratch.
- **`damped_oscillation.gle`** -- the finished figure as a native `.gle`
  file: an error-bar series for the measured data plus a dashed line for the
  model, with axis labels, a title, and a legend. `.gle` is the editor's
  native save format, so File > Open parses this straight back into the
  editor -- open it to see a fully styled result, then keep editing.
- **`data_0.dat`**, **`data_1.dat`** -- the two `.dat` sidecars the `.gle`
  references (the measured series and the model curve). They live alongside
  the `.gle` and are read on open and rewritten on save.

## Try it

1. Launch the editor: `gleplot-gui`
2. **Open the finished figure**: File > Open > `damped_oscillation.gle`.
   It parses into the editor and renders immediately in the live preview --
   fully editable, not a static preview.
3. **Or build it yourself** from the raw data:
   - Data dock > "Load data file..." > `damped_oscillation.csv`.
   - Pick `x` for X, `y_measured` for Y, `yerr` for Y error, plot type
     "Error bars", mode "Import data" > Add series.
   - Load the file again (or reselect it), pick `x` / `y_model`, plot type
     "Line", mode "Import data" > Add series.
   - Properties dock > Axes tab: set the title to "Damped Oscillation",
     X label to "Time (s)", Y label to "Amplitude".
   - Properties dock > Series tab: style the model line (color, dash) and
     the measured series (marker, color) to taste; enable the legend.
   - File > Save As... to write your own `.gle`.
4. **Export**: File > Export (Ctrl+E) to produce a PDF/PNG/SVG/EPS/JPG, or a
   `.gle` script, or a folder bundle containing the script plus its data
   files.

## Regenerating

`damped_oscillation.gle` (and its `data_*.dat` sidecars) was generated
programmatically (not hand-edited) using the gleplot API plus
`Figure.savefig_gle`, mirroring what the Data dock's "Import data" mode
produces. It round-trips through `gleplot.parser.recognizer.parse_gle_figure`
with zero warnings. See `docs/guides/GUI_EDITOR.md` for the equivalent manual
workflow.
