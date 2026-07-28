# Broken (Split) X-Axes

A **broken axis** is one logical panel whose x-axis is cut into two or more
adjacent linear segments covering very different ranges, sharing a single
y-axis. It is the right tool when a dataset carries structure on two scales
at once and a log axis is not appropriate — for instance a muon relaxation
spectrum whose first 20 ns hold a fast Gaussian decay while the remaining
3 µs hold a slow exponential tail. On a single linear 0–3 µs axis the fast
component lives in the first 0.7 % of the panel and is invisible.

## Quick start

```python
import gleplot as glp

fig = glp.figure(figsize=(3.4, 2.7))
fig.subplots_adjust(left=0.17, right=0.98, bottom=0.19, top=0.96)

bax = fig.add_broken_xaxes(
    [(0.0, 0.02), (0.02, 3.0)],   # one (xmin, xmax) per segment
    width_ratios=[1, 3],          # the segments are NOT equal width
    divider='slash',              # double-slash break marks at the seam
)
bax.set_ylim(0.0, 28.0)

# Declared ONCE; drawn in every segment, from one shared data sidecar.
bax.errorbar(t, a, yerr=e, marker='o', fmt='none', color='blue', label='2 K')
bax.plot(t_model, a_model, color='blue', linestyle='--')
bax.axhline(2.4, color='gray', linestyle=':')     # background level

bax.set_ylabel('Asymmetry (%)')
bax.set_xlabel('t (\\mu s)')
bax[0].set_xticks(dticks=0.01)                    # per-segment tick spacing
bax[1].set_xticks(dticks=1.0)
bax.legend(loc='upper right')

fig.savefig('fig2a.pdf')
```

A full worked panel in the style of PRL 134, 046702 Fig. 2(a) is in
[`examples/advanced/prl_fig2a_style.py`](../../examples/advanced/prl_fig2a_style.py);
[`examples/advanced/broken_axis.py`](../../examples/advanced/broken_axis.py)
compares the three seam styles and shows a three-segment split.

## API

### `Figure.add_broken_xaxes(xlims, **kwargs) -> BrokenAxes`

| Argument | Default | Meaning |
|---|---|---|
| `xlims` | — | one `(xmin, xmax)` per segment, left to right; **at least two** |
| `width_ratios` | equal | relative *plotted* widths (gaps are taken out first) |
| `position` | `(1, 1, 1)` | the `(rows, cols, index)` grid cell the assembly occupies |
| `gap` | 0, or 0.15 cm for `'slash'` | physical gap between segments, in cm |
| `divider` | `'line'` | `'none'`, `'line'` (one vertical rule) or `'slash'` (double-slash break marks) |
| `divider_color` | `'black'` | seam colour |
| `divider_linewidth` | style default | seam line width, in points |
| `divider_lstyle` | — | GLE `lstyle` for a `'line'` divider |
| `break_mark_size` | 0.2 | height (cm) of each `'slash'` stroke; width and pair separation scale with it |
| `trim_seam_labels` | `True` | drop the second segment's first tick label when the ranges are contiguous |
| `xlabel_dist`, `title_dist` | matched to GLE | cm from the frame to the shared x title / title |

### On the returned `BrokenAxes`

**Fanned out to every segment** — declare a series once:
`plot`, `scatter`, `errorbar`, `bar`, `fill_between`, `line_from_file`,
`errorbar_from_file`, `axvline`, `axhline`, `axvspan`, `axhspan`.

**Shared state:** `set_ylabel`, `set_ylim`, `get_ylim`, `set_yscale`,
`set_yticks` (the y-axis is always shared), plus `set_xlabel`, `set_title`
and `legend` for the assembly as a whole.

**Per-segment:** `bax[i]` / `bax.segments` / `len(bax)` / iteration give the
underlying `Axes`. `bax.set_xticks(dticks=..., dsubticks=..., segment=...)`
accepts a scalar (applied to all) or one value per segment;
`bax.set_xscale(...)` likewise. Explicit tick positions are per-segment by
nature — use `bax[i].set_xticks(ticks, labels)`.

**`text(x, y, s)`** is routed to the segment whose range contains `x` (it
cannot be fanned out — a segment that excludes `x` would draw the label
outside its own box). Text falling in the break warns and is not drawn.

**`set_xlim`** raises `TypeError`: the ranges are the `xlims` argument.

## How it works

GLE has no split-axis primitive, so the assembly is built from ordinary graph
blocks — one `begin graph`/`end graph` per segment, positioned adjacently
with `amove` + `size` + `scale 1 1` (which makes the data area exactly fill
the requested box, so the boxes butt together with no internal padding). The
sides that face each other are switched off with GLE's per-side `off`
sub-command, leaving one continuous frame:

| segment | left side (`yaxis`) | right side (`y2axis`) |
|---|---|---|
| leftmost | full: line, ticks, labels, title | `off` |
| middle | `off` | `off` |
| rightmost | `off` | kept — the panel's right edge |

The seam itself is drawn explicitly, anchored to the left segment's
`xg(xgmax)` / `yg(ygmin)` / `yg(ygmax)` so it lands exactly where GLE drew
the box, and wrapped in `gsave`/`grestore` so the colour and line width do
not leak into the next graph block.

Series are stored once per segment but share **one** generated `.dat`
sidecar. GLE clips each dataset to its own graph's axis range, so a point
only appears in the segment whose range contains it — which is also what
makes `axvspan` land in the right segment automatically, with no work from
the caller.

The x title and the title are written as absolute page text centred on the
*whole* assembly, because GLE's own `xtitle`/`title` centre on their own
graph box. The default offsets reproduce GLE's native placement for the
figure's font size (measured against a native `xtitle` render to ~0.02 cm);
`xlabel_dist`/`title_dist` override them.

## Practical notes

- **Give the ranges their own tick intervals.** GLE picks ticks per graph
  block, so a narrow segment and a wide one will otherwise choose spacings
  that collide at the seam. `bax[i].set_xticks(dticks=...)` is usually the
  first thing to set after the data.
- **Leave headroom for the title.** Unlike GLE's `title`, the shared title is
  drawn just above the frame and does not reserve space of its own; use
  `fig.subplots_adjust(top=...)`.
- **The legend starts suppressed.** A fanned-out series carries its label in
  every segment, so the auto-legend rule would draw the same key N times.
  `bax.legend()` turns exactly one segment's key back on — by default the
  widest segment, or pass `segment=`.
- **Model curves across the seam:** if you build the curve's x grid by
  concatenating a fine grid and a coarse one, drop the duplicated boundary
  point (`np.unique`). gleplot draws lines with GLE's `smooth` by default and
  a repeated x makes that spline spike.
- **Mixing with ordinary subplots** works: pass `position=(rows, cols, index)`
  and use `add_subplot` for the other cells.

## Limitations

- **No broken y-axis.** The y-axis is always shared across segments.
- **The `.gle` parser does not reconstruct a `BrokenAxes`.** Reading a
  generated file back with `open_gle()` yields the segments as independent
  subplots; the axis options the recognizer cannot model (`dticks`, the
  per-side `off`) are preserved as per-axes passthrough *with warnings*, and
  the seam decoration and shared titles are preserved as trailer passthrough.
  Nothing is dropped, but the assembly's geometry is re-derived from the
  subplot grid on re-save, so a round-tripped file will not lay out
  identically. Keep the producing script as the source of truth.
- **The GUI editor** has no broken-axis panel; a figure containing one opens
  as its segments.
