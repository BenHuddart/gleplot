# GUI Editor Example

A small, ready-to-open figure for the gleplot GUI editor (`gleplot-gui`).

## Files

- **`damped_oscillation.csv`** -- 100 rows of a simulated damped oscillation:
  `x`, `y_measured` (noisy), `yerr` (constant error estimate), `y_model`
  (the noise-free curve). Load this in the Data dock to try column picking
  and series creation from scratch.
- **`damped_oscillation.gle`** -- the finished figure as a native `.gle`
  file: an error-bar series for the measured data plus a dashed line for the
  model, with axis labels, a title, a legend, and three text annotations
  ("Initial peak", "Decay envelope", "Settling") marking points of interest
  on the curve. `.gle` is the editor's native save format, so File > Open
  parses this straight back into the editor -- open it to see a fully styled
  result, then keep editing.
- **`data_0.dat`**, **`data_1.dat`** -- the two `.dat` sidecars the `.gle`
  references (the measured series and the model curve). They live alongside
  the `.gle` and are read on open and rewritten on save. Each one starts with
  a named header row (`x measured err`, `x model_fit`) instead of anonymous
  column numbers -- open either in a text editor to see it.

## Try it

1. Launch the editor: `gleplot-gui`
2. **Open the finished figure**: File > Open > `damped_oscillation.gle`.
   It parses into the editor and renders immediately in the live preview --
   fully editable, not a static preview.
3. **Try the annotations**: hover over any of the three text labels on the
   preview and drag it to a new spot (a semi-transparent "ghost" follows the
   cursor until the next render lands with the text at its new position);
   double-click one to edit its wording inline; select one and press Delete
   to remove it. Or press **T** (Edit > Add text annotation) and click
   anywhere on the plot to place a new label. The Properties dock's **Texts**
   tab lists all three and lets you edit position, color, size, and
   horizontal alignment from a form instead -- selecting a row there
   highlights the matching label on the canvas, and vice versa.
4. **Or build it yourself** from the raw data:
   - Data dock > "Load data file..." > `damped_oscillation.csv`.
   - Pick `x` for X, `y_measured` for Y, `yerr` for Y error, plot type
     "Error bars", mode "Import data" > Add series.
   - Load the file again (or reselect it), pick `x` / `y_model`, plot type
     "Line", mode "Import data" > Add series.
   - Properties dock > Axes tab: set the title to "Damped Oscillation",
     X label to "Time (s)", Y label to "Amplitude".
   - Properties dock > Series tab: style the model line (color, dash) and
     the measured series (marker, color) to taste; enable the legend.
   - Add a label or two of your own with Edit > Add text annotation (or the
     Texts tab's Add button).
   - File > Save As... to write your own `.gle`.
5. **Export**: File > Export (Ctrl+E) to produce a PDF/PNG/SVG/EPS/JPG, or a
   `.gle` script, or a folder bundle containing the script plus its data
   files.

## Regenerating

`damped_oscillation.gle` (and its `data_*.dat` sidecars) was generated
programmatically (not hand-edited) using the gleplot API -- including the
three text annotations, added via `Axes.text()` -- plus `Figure.savefig_gle`,
mirroring what the Data dock's "Import data" mode plus manual annotation
placement produces. It round-trips through
`gleplot.parser.recognizer.parse_gle_figure` with zero warnings, and compiles
cleanly with GLE. See `docs/guides/GUI_EDITOR.md` for the equivalent manual
workflow.
