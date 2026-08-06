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

## Legends

`ax.legend()` becomes GLE's graph-block `key` command, which understands only
a position, a text height and whether to draw a box. The kwargs that map onto
those are honoured; every other matplotlib legend kwarg raises a
`UserWarning` instead of being silently dropped.

| `legend()` kwarg | gleplot |
|---|---|
| `loc` | wired — all eleven matplotlib strings map onto GLE's nine key anchors (`key pos`). `'best'` is not computed; like matplotlib's own fallback it means top right. GLE short forms (`'tr'`, `'bl'`, …) are accepted too. An unrecognized value warns. |
| `fontsize` | wired — points converted to cm as `key ... hei`, using the same pt→cm conversion as `set hei`. matplotlib's relative names (`'small'`, `'x-large'`, …) resolve against the figure style's fontsize. |
| `frameon` | wired — `False` emits `key ... nobox`. |
| `ncol`/`ncols` | `1` accepted, more warns: a GLE graph-block key is always one column (multiple columns need a standalone `begin key` block with `separator` commands). |
| handles/labels (first positional) | warns — legend text always comes from each series' `label=`. |
| `title`, `framealpha`, `edgecolor`, `facecolor`, `shadow`, `bbox_to_anchor`, `markerscale`, `borderpad`, `labelspacing`, … | warn — no GLE `key` equivalent. |

```python
# an 8.6 cm journal column wants legend text smaller than the axis labels
ax.legend(loc='upper left', fontsize=6.5, frameon=False)
```

## Key Behavioral Differences

1. Primary output model is GLE script generation.
2. Saving to `.gle` always works without external compiler.
3. Saving to `.pdf`, `.png`, `.eps` requires a working GLE installation.
4. Sidecar `.dat` files are generated for in-memory series unless file-based series methods are used.
5. `ax.grid(visible, which=, axis=, color=, linestyle=, linewidth=)` maps to
   GLE's `xaxis grid` (+ `xsubticks on` for `which='both'`). A minor-only
   grid is not expressible and is normalized to both, with a warning.
6. Display strings follow matplotlib's contract: plain text renders literally
   (`'lambda_tail'` is not a subscript) and math is opt-in via `$...$`. Unlike
   matplotlib, a backslash outside `$...$` still opens GLE's own text markup
   (`r'\chi{}'`), as do braced scripts (`'T_{N}'`).

## Migration Strategy

1. Port plotting code with minimal edits (`plt` -> `glp`).
2. Validate scripts first by saving as `.gle`.
3. Add `data_prefix` for deterministic sidecar names in batch pipelines.
4. Replace custom file parsers with `errorbar_from_file()`/`line_from_file()` where possible.
5. Add project-specific style defaults via `GlobalConfig`.
