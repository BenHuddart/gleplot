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

## Grid Call Has No Visual Effect

Current behavior: `ax.grid(...)` exists for API compatibility and future extension. If grid lines are not rendered in your output, rely on explicit axis styling for now.
