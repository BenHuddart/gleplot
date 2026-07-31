# Reference Lines and Shaded Spans

`axvline`, `axhline`, `axvspan` and `axhspan` draw guides that span the whole
axes: a critical temperature, a zero level, a background band, an excluded
region. They are available on `Axes`, on `Figure` (acting on the current
axes), on the module (`glp.axvline(...)`), and on a broken x-axis
(see [BROKEN_AXES.md](BROKEN_AXES.md)).

Before these existed the usual workaround was a two-point `plot()` call and a
hand-built `fill_between()` band, which had to be redone by hand whenever the
axis limits changed.

## Quick start

```python
import numpy as np
import gleplot as glp

fig = glp.figure(figsize=(6, 4))
ax = fig.add_subplot(111)
ax.plot(x, y, color='blue')
ax.set_ylim(-1.5, 1.5)

ax.axhline(0.0, color='gray', linestyle=':')        # zero level
ax.axvline(3.14, color='red', linestyle='--')       # a transition
ax.axvspan(6.0, 8.0, color='lightgray')             # excluded window
ax.axhspan(-0.25, 0.25, xmin=0.0, xmax=0.4,         # band over the left 40%
           color='lightcyan')

fig.savefig('guides.pdf')
```

## API

```python
ax.axvline(x=0.0, ymin=0.0, ymax=1.0, color=None,
           linestyle='-', linewidth=1, label=None)
ax.axhline(y=0.0, xmin=0.0, xmax=1.0, color=None,
           linestyle='-', linewidth=1, label=None)
ax.axvspan(xmin, xmax, ymin=0.0, ymax=1.0, color=None, alpha=0.3, label=None)
ax.axhspan(ymin, ymax, xmin=0.0, xmax=1.0, color=None, alpha=0.3, label=None)
```

Argument semantics follow matplotlib exactly:

- the **value** arguments (`x` for `axvline`, `ymin`/`ymax` for `axhspan`, …)
  are in **data coordinates**;
- the **extent** arguments along the other axis (`ymin`/`ymax` for `axvline`,
  `xmin`/`xmax` for `axhline`) are **axes fractions** in `[0, 1]`: `0` is the
  bottom/left of the axes, `1` the top/right. Out-of-range values raise
  `ValueError`.

Each call returns the stored declaration dict and appends it to `ax.reflines`
or `ax.spans`.

## How it works (and why that matters)

GLE has no "line across the whole axis" primitive: everything inside a graph
block is a dataset with concrete numbers. gleplot therefore stores a
*declaration* at call time and turns it into a concrete two-point line — or a
two-point `fill` band — **at write time**, once the axis limits are known.

Three consequences:

1. **Later limit changes are respected.** `ax.axvline(1.5)` followed by
   `ax.set_ylim(-1, 1)` produces a line from −1 to 1, and so does adding more
   data that widens the autoscale afterwards.
2. **Guides participate in autoscaling** along their data direction, as in
   matplotlib: an `axvline` at *x* = −5 extends the x range; its *y* extent is
   a fraction and never feeds back into the y autoscale.
3. **Guides are drawn underneath the data.** Spans go out with the
   `fill_between` layer, reference lines immediately after, and all data
   series after that. Use the matplotlib-compatible ``zorder`` argument on
   ``plot``, ``scatter``, and ``errorbar`` when you need a fit line or curve
   drawn above markers (the default keeps markers and error bars on top of
   plain lines).

Generating a figure twice does not duplicate anything: materialization
returns a fresh list and never writes back onto the axes. The `.dat` sidecar
name, on the other hand, is reserved at call time, so it is stable across
repeated saves.

If an axes has no data *and* no explicit limits, there is nothing for a guide
to span; it is dropped with a `UserWarning` rather than emitting a broken
dataset.

## Limitations

- **`alpha` is not rendered.** It is accepted and stored for matplotlib API
  compatibility, but GLE 4.3.10 refuses semi-transparency unless it is driven
  with `-cairo` (*"semi-transparency only supported with command line option
  `-cairo`"*), which gleplot's compiler does not use. Use a light colour
  (`'lightgray'`, `'lightcyan'`, …) instead. This matches the existing
  behaviour of `fill_between`.
- **Round-tripping.** Reading a generated `.gle` file back with `open_gle()`
  recovers the guides as ordinary line/fill series, not as `reflines`/`spans`.
  Nothing is lost or silently dropped, but re-saving bakes in the limits that
  were in force when the file was written.
