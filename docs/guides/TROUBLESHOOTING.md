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

3. Check that fonts referenced by your style are available in your GLE install.

## Unexpected Data File Names

Symptoms:

- Sidecar files use global names like `data_12.dat`

Fixes:

1. Use figure-level `data_prefix` for deterministic naming.
2. Use per-series `data_name` for semantic labels where supported.

## Text or Legend Overlaps

Symptoms:

- Labels overlap data points or panel boundaries

Fixes:

1. Adjust layout using `fig.subplots_adjust(...)`.
2. Move legend with `ax.legend(loc='...')`.
3. Use `ax.text(..., bbox={...})` for readability.

## Shared Axes Not Displaying All Labels

This is expected behavior.

- `sharex=True`: only bottom row shows x labels/ticks
- `sharey=True`: only leftmost column shows y labels/ticks

Disable sharing if each panel must show all tick labels.

## Lines Look More Angular Than They Used To

Symptoms:

- A figure regenerated with gleplot 1.9.0 or later has visibly kinked lines
  where the old one had flowing curves, and peaks no longer overshoot

This is the fix, not a regression. Before 1.9.0, `GLEGraphConfig.smooth_curves`
defaulted to `True`, so every line series was emitted with GLE's `smooth`
qualifier and rendered as a spline fitted *near* the data instead of a
polyline *through* it. The new default draws the data. Any jaggedness you now
see is in your points and was previously being smoothed away.

If the smoothed look is what you want (a guide to the eye, a densely sampled
model curve), ask for it explicitly:

```python
fig = glp.figure(graph=glp.GLEGraphConfig(smooth_curves=True))
# or, once per script, for every figure it creates:
glp.GlobalConfig.graph.smooth_curves = True
```

See the Curve Smoothing section of `CONFIGURATION.md`.

## Grid Call Has No Visual Effect

`ax.grid(...)` draws a real grid (GLE `xaxis grid`, which stretches that
axis' ticks across the graph). Two things to know if it does not look the way
matplotlib would:

- A grid always covers the **main ticks**; `which='minor'` alone is not
  expressible in GLE and is normalized to `which='both'` with a warning.
- Grid style **is** tick style (`xticks lstyle/lwidth/color`), so
  `ax.grid(True, color='gray40')` recolours that axis' ticks as well.
