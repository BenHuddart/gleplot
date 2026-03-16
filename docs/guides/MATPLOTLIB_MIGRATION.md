# Matplotlib Migration Guide

gleplot intentionally mirrors the matplotlib style for core plotting tasks.

## Quick Mapping

| matplotlib | gleplot |
|---|---|
| `plt.figure()` | `glp.figure()` |
| `fig.add_subplot(...)` | same |
| `ax.plot(...)` | same |
| `ax.scatter(...)` | same |
| `ax.errorbar(...)` | same |
| `ax.fill_between(...)` | same |
| `ax.set_xlabel(...)` | same |
| `ax.set_ylabel(...)` | same |
| `ax.set_title(...)` | same |
| `ax.legend(...)` | same |
| `plt.savefig(...)` | `fig.savefig(...)` or `glp.savefig(...)` |

## Minimal Porting Example

Matplotlib:

```python
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(x, y, color='blue', label='sin(x)')
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.legend()
fig.savefig('plot.pdf')
```

gleplot:

```python
import gleplot as glp
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

fig, ax = glp.subplots(figsize=(8, 5))
ax.plot(x, y, color='blue', label='sin(x)')
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.legend()
fig.savefig('plot.pdf')
```

## Key Behavioral Differences

1. Primary output model is GLE script generation.
2. Saving to `.gle` always works without external compiler.
3. Saving to `.pdf`, `.png`, `.eps` requires a working GLE installation.
4. Sidecar `.dat` files are generated for in-memory series unless file-based series methods are used.
5. `ax.grid(...)` is currently a compatibility placeholder.

## Migration Strategy

1. Port plotting code with minimal edits (`plt` -> `glp`).
2. Validate scripts first by saving as `.gle`.
3. Add `data_prefix` for deterministic sidecar names in batch pipelines.
4. Replace custom file parsers with `errorbar_from_file()`/`line_from_file()` where possible.
5. Add project-specific style defaults via `GlobalConfig`.
