# Troubleshooting

This page covers common issues and practical fixes.

## GLE Executable Not Found

Symptoms:

- Saving to `.pdf`, `.png`, or `.eps` fails
- Errors mention missing `gle` command

Fixes:

1. Install GLE from the official release page.
2. Ensure `gle` is available on your PATH.
3. Verify with:

```bash
gle -info
```

4. If needed, provide an explicit path via `GLECompiler(gle_path='...')`.

## Save to Vector/Raster Format Fails

Symptoms:

- `fig.savefig('plot.pdf')` raises a compile error

Fixes:

1. Save as `.gle` first to validate script generation:

```python
fig.savefig('plot.gle')
```

2. Compile manually for better diagnostics:

```bash
gle plot.gle -d PDF
```

3. If GLE reports `invalid font name`, set the font to a GLE font name; see
   "Available Fonts" in [Configuration](CONFIGURATION.md).
4. If GLE reports `include file not found`, install GLE's include library; see
   [GLE's include library](https://benhuddart.github.io/gleplot/getting_started.html#gle-s-include-library).

## Unexpected Data File Names

Symptoms:

- Sidecar files use global names like `data_12.dat`

Fixes:

Name them with `data_prefix` on the figure or `data_name` on a series; see
[Configuration](CONFIGURATION.md).

## Text or Legend Overlaps

Symptoms:

- Labels overlap data points or panel boundaries

Fixes:

1. Adjust layout using `fig.subplots_adjust(...)`.
2. Move legend with `ax.legend(loc='...')`.
3. Use `ax.text(..., bbox={...})` for readability.

## Shared Axes Not Displaying All Labels

This is expected: shared axes label only the outer panels, as described in
[Figures and Subplots](FIGURES_AND_SUBPLOTS.md). Disable sharing if each panel
must show all tick labels.

## Lines Look Angular

Symptoms:

- A line has visible kinks between sparse points, where a smoothed curve
  would flow through them

A line is drawn as a polyline *through* your points, as in matplotlib. GLE's
`smooth` qualifier draws a spline fitted *near* the points instead, which
can overshoot peaks. If the smoothed look is what you want (a guide to the
eye, a densely sampled model curve), ask for it explicitly:

```python
fig = glp.figure(graph=glp.GLEGraphConfig(smooth_curves=True))
# or, once per script, for every figure it creates:
glp.GlobalConfig.graph.smooth_curves = True
```

See "Curve Smoothing" in [Configuration](CONFIGURATION.md).

## Grid Call Has No Visual Effect

`ax.grid(...)` draws a real grid (GLE `xaxis grid`, which stretches that
axis' ticks across the graph). Two things to know if it does not look the way
matplotlib would:

- A grid always covers the **main ticks**; `which='minor'` alone is not
  expressible in GLE and is normalized to `which='both'` with a warning.
- Grid style **is** tick style (`xticks lstyle/lwidth/color`), so
  `ax.grid(True, color='gray40')` recolours that axis' ticks as well.

## A gleplot 5 Script Raises or Draws Differently

gleplot 6 raises for an argument value it cannot use, removed the features
GLE cannot draw natively, and changed some defaults, such as the colour of
an uncoloured series and the outline of a bar. Each change, and what to use
instead, is in [Migrating from gleplot 5 to 6](MIGRATING_TO_6.md).
