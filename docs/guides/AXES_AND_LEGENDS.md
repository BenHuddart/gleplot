# Axes and Legends

Labels, limits, scales, secondary axes, grids and legends. The snippets
assume an axes from `fig.add_subplot(111)`.

## Labels and title

```python
ax.set_xlabel('X Axis Label')
ax.set_ylabel('Y Axis Label')
ax.set_title('Plot Title')
```

Labels take matplotlib mathtext between `$...$`. See
[Contour Plots and Heatmaps](CONTOUR_AND_HEATMAPS.md) for Greek letters and
GLE's own text markup.

`fontname=` sets the font of one title, as a GLE font name such as
`'texcmr'` or `'psh'`. It is written as `font` on that `title` or `xtitle`
line. Leave it out to keep the current font.

```python
ax.set_title('Plot Title', fontname='texcmb')
ax.set_xlabel('t (s)', fontname='texcmr')
```

`fontsize` (points, or a name such as `'small'`), `color` and `labelpad`
(the gap to the tick labels, in points) work as in matplotlib, and so does
`pad` on `set_title` (the gap above the axes). They are written as `hei`,
`color` and `dist` on the same line:

```python
ax.set_xlabel('T (K)', fontsize=9, color='gray', labelpad=4)
ax.set_title('Run 12', fontsize=11, pad=6)
```

## Limits

```python
ax.set_xlim(0, 10)
ax.set_ylim(-1, 1)
```

Passing the limits in descending order inverts the axis, as in matplotlib.
This is useful for depth below ground, magnitudes, and anything else that
counts downwards:

```python
ax.set_ylim(500, 0)    # zero at the top, 500 at the bottom
```

`ax.invert_yaxis()` (and `invert_xaxis`) does the same by swapping the
limits. gleplot has no inverted-but-automatic axis, so an automatic limit is
replaced by the end of the data plotted so far: plot first, then invert.

The one exception is a log axis, which GLE cannot invert; a descending log
range is drawn the usual way round, with a `UserWarning`.

## Aspect ratio

`ax.set_aspect('equal')` gives a unit the same length on both axes, so a
circle is drawn round; a number `a` makes a y unit `a` times as long as an x
unit, and on a log axis a unit is a decade:

```python
import numpy as np
import gleplot as glp

t = np.linspace(0, 2 * np.pi, 200)
fig, ax = glp.subplots(figsize=(6, 4))
ax.plot(np.cos(t), np.sin(t))
ax.set_aspect('equal')
```

When the figure is saved, the frame is shrunk about its centre to fit the
ratio of the axis limits it is saved with. `ax.axis('equal')` only warns: use
`set_aspect`. A figure opened again with `open_gle` keeps the shrunk frame
but not the aspect, so changing its limits afterwards does not reshape the
frame.

## Log scales

```python
ax.set_xscale('log')
ax.set_yscale('log')
```

`ax.semilogx(x, y)`, `ax.semilogy(x, y)` and `ax.loglog(x, y)` set the scale
and call `plot`.

A log axis can only show strictly positive values, and GLE refuses to compile
a script that asks it to do otherwise. gleplot therefore resolves log limits
before writing them, as matplotlib does: non-positive data is masked when
autoscaling, and a non-positive limit passed to `set_xlim`/`set_ylim` is
replaced by the smallest positive value plotted. Either repair emits a
`UserWarning` saying what range was used instead; pass a positive range to
choose your own.

## Secondary axes

The right-hand scale is `yaxis="y2"` on a series, with `set_ylim`,
`set_ylabel`, `set_yscale` and `set_tick_format` taking `axis="y2"`:

```python
ax.plot(x, temperature, label='Temperature')
ax.plot(x, humidity, label='Humidity', yaxis='y2')
ax.set_ylabel('Temperature (°C)', axis='y')
ax.set_ylabel('Humidity (%)', axis='y2')
```

`ax.twinx()` is the matplotlib view of the same scale. The x axis stays the
one the view was opened on; limits, log, tick format and the label set on the
view belong to the right scale:

```python
right = ax.twinx()
right.plot(x, humidity, label='Humidity')
right.set_ylabel('Humidity (%)')
```

Each y scale fits its own series, as with matplotlib's `twinx`: the left
range gleplot writes leaves out the series on y2, and GLE scales y2 from
them. An axes with nothing at all on the left axis is the exception: its
left range spans the y2 series, where matplotlib's empty left axis runs
from 0 to 1.

The top scale is the same idea, and `ax.twiny()` is the matplotlib view that
binds it. The y axis stays the one the view was opened on; limits, log and
the label set on the view belong to the top scale:

```python
top = ax.twiny()
top.plot(x_alt, y)
top.set_xlim(0, 10)
top.set_xlabel("wavelength")
```

`xaxis="x2"` on `plot`, `scatter`, `errorbar`, `step`, `stem`, `hist` (step outline), `line_from_file` and `errorbar_from_file` is the same binding without the view. `set_xlim`, `set_xlabel`, `set_xscale` and `set_tick_format` take `axis="x2"`.

GLE copies an `xaxis` command onto x2. `min` and `max` are not copied, but `log` is, so a linear top scale under a log bottom axis is written `x2axis lin` after the `xaxis` line. A figure whose bottom axis is log and whose top scale is unused does not gain that line. `x2labels on` is written when the top scale has limits, a log scale, a title, or tick-label styling; a series on x2 is enough for GLE to number that axis on its own. There is no x2 grid. A filled histogram cannot use x2, and `bar` has no `x2axis`.

## Grid

```python
ax.grid(True)                 # major grid
ax.grid(True, which='both')   # major and minor grid
```

## Axis lines and tick placement

`set_axis_line` sets the colour and width (points) of an axis line, written
as GLE's `xside`. The ticks, tick labels and grid keep their colour.

```python
ax.set_axis_line(color='gray', linewidth=1.2)   # the x and y lines
ax.set_axis_line('x2', color='red')             # the top line on its own
```

GLE copies the x line's style onto the top line and the y line's onto the
right one, so `'x'` or `'both'` styles all four sides unless `'x2'` or `'y2'`
is set too.

`visible=False` hides one side, matplotlib's `spines[...].set_visible(False)`:

```python
ax.set_axis_line('x2', visible=False)   # no top line
ax.set_axis_line('y2', visible=False)   # no right line
```

The bottom and left lines keep their ticks and tick labels when hidden.
The top and right sides lose the tick marks GLE mirrors there too, and a
`twiny`/`twinx` scale on that side with them, which warns.

`set_xticks` and `set_yticks` also take GLE's own placement keywords:
`nticks` (number of major ticks), `ftick` (where the first one goes),
`shift` (move the tick labels along the axis, in cm), `symticks=True` (ticks
inside and outside the frame) and `noticks` (positions with no tick). GLE
copies them onto the top and right axes.

```python
ax.set_xticks(nticks=5, ftick=0)
ax.set_yticks(symticks=True, noticks=[0])
```

## Tick marks and minor ticks

`tick_params` sets the length, width (both in points), colour and direction
of the tick marks, written as GLE's `xticks` (major) and `xsubticks` (minor).
`minorticks_on` and `minorticks_off` switch the minor ticks of both axes.

```python
ax.tick_params(axis='x', length=4, width=0.8, direction='in')
ax.tick_params(axis='y', which='minor', length=2)
ax.minorticks_off()
```

GLE draws ticks inside the frame by default; matplotlib draws them outside.
`direction='out'` is a negative GLE length, so with no `length` it uses
matplotlib's default (3.5 points, 2 for minor ticks). `direction='inout'` is
GLE's `symticks`, one setting for an axis' major and minor ticks. An axis
with a grid draws the grid lines in place of its ticks, so its tick marks are
not written and saving warns; style the grid with `grid(color=...,
linewidth=...)` instead.

`set_xticks` and `set_yticks` also take `nsubticks` (minor ticks between two
major ones), `loglabels` (which sub-decades of a log axis get a label: `'off'`,
`'l1'`, `'l25'`, `'l25b'` or `'n1'`) and `nofirst` / `nolast` (leave out the
first or last tick label).

```python
ax.set_xscale('log')
ax.set_xticks(loglabels='l25', nofirst=True)
ax.set_yticks(nsubticks=4)
```

`set_math_mode` draws the x and y axes through the origin instead of around
the plot, with ticks on both sides. It is written as GLE's `math`. Both axes
move together. The top and right axes are hidden unless a series or label
uses them. Both limits must include 0, and neither axis can be log.

```python
ax.set_math_mode()          # axes cross at (0, 0)
ax.set_math_mode(False)     # back to a box around the plot
```

## Legends

```python
ax.plot(x, y1, label='Series 1')
ax.plot(x, y2, label='Series 2')
ax.legend()                   # default location
ax.legend(loc='upper right')  # custom location
```

The legend is GLE's `key` command. Which `legend()` keywords are honoured, and
what happens to the rest, is listed in the
[Matplotlib Migration Guide](MATPLOTLIB_MIGRATION.md).

One legend for several axes is `fig.legend()`. It lists the labelled series of
every axes, and while it exists an axes draws its own legend only if
`ax.legend()` was called on it:

```python
fig, axes = glp.subplots(1, 2)
axes[0].plot(x, y1, label='Series 1')
axes[1].plot(x, y2, label='Series 2')
fig.legend(loc='lower center', ncol=2)
fig.subplots_adjust(bottom=0.2)
```
