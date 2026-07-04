# GUI Editor Example Project

A small, ready-to-open project for the gleplot GUI editor (`gleplot-gui`).

## Files

- **`damped_oscillation.csv`** -- 100 rows of a simulated damped oscillation:
  `x`, `y_measured` (noisy), `yerr` (constant error estimate), `y_model`
  (the noise-free curve). Load this in the Data dock to try column picking
  and series creation from scratch.
- **`damped_oscillation.glep`** -- a gleplot project file that already
  contains the finished figure: an error-bar series for the measured data
  plus a dashed line for the model, with axis labels, a title, and a legend.
  Open this to see a fully styled result, or as a reference for what the
  workflow below produces.

## Try it

1. Launch the editor: `gleplot-gui`
2. **Open the finished project**: File > Open > `damped_oscillation.glep`.
   The figure renders immediately in the live preview.
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
   - File > Save As... to write your own `.glep`.
4. **Export**: File > Export (Ctrl+E) to produce a PDF/PNG/SVG/EPS/JPG, or a
   `.gle` script, or a folder bundle containing the script plus its data
   files.

## Regenerating

`damped_oscillation.glep` was generated programmatically (not hand-edited)
using the gleplot API plus `gleplot.project.save_project`, mirroring what
the Data dock's "Import data" mode produces. See the gleplot test suite and
`docs/guides/GUI_EDITOR.md` for the equivalent manual workflow.
