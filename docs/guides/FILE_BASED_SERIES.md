# File-Based Series

gleplot can reference columns in an existing data file instead of generating new sidecar `.dat` files for every plot element.

This is useful when your data already exists in analysis outputs or experiment logs.

## Supported Methods

- `Axes.errorbar_from_file(data_file, x_col, y_col, yerr_col=None, ...)`
- `Axes.line_from_file(data_file, x_col, y_col, ...)`

Column indices are 1-based to match GLE conventions.

## Minimal Example

```python
import gleplot as glp

fig = glp.figure(figsize=(8, 5))
ax = fig.add_subplot(111)

ax.errorbar_from_file('results.dat', x_col=1, y_col=2, yerr_col=3, label='Measured')
ax.line_from_file('results.dat', x_col=1, y_col=4, linestyle='--', label='Model')
ax.legend()
fig.savefig('from_file.gle')
```

## Expected Data Format

Any whitespace-delimited file that GLE can read, for example:

```text
! c1=time  c2=signal  c3=signal_err  c4=model
0.0  1.20  0.08  1.17
0.5  1.33  0.09  1.31
1.0  1.41  0.10  1.39
```

## Typical Workflow

1. Produce `results.dat` in your analysis step.
2. Build figures that reference file columns.
3. Save `.gle` scripts without generating extra measurement sidecars.
4. Re-run plots against updated data files without changing plotting code.

## Notes

- Keep a clear column map in comments at the top of data files.
- Use consistent units per column.
- For mixed workflows, you can combine generated series (`plot`, `scatter`) and file-backed series in the same axes.
- For working examples, see:
  - `examples/advanced/errorbar_from_file.py`
  - `examples/advanced/line_from_file.py`
