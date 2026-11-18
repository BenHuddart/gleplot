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

The one exception is a log axis, which GLE cannot invert; a descending log
range is drawn the usual way round, with a `UserWarning`.

## Log scales

```python
ax.set_xscale('log')
ax.set_yscale('log')
```

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

`set_xticks` and `set_yticks` also take GLE's own placement keywords:
`nticks` (number of major ticks), `ftick` (where the first one goes),
`shift` (move the tick labels along the axis, in cm), `symticks=True` (ticks
inside and outside the frame) and `noticks` (positions with no tick). GLE
copies them onto the top and right axes.

```python
ax.set_xticks(nticks=5, ftick=0)
ax.set_yticks(symticks=True, noticks=[0])
```

`set_math_mode` draws the x and y axes through the origin instead of around
the plot, with ticks on both sides and no top or right axis. It is written
as GLE's `math`. GLE moves both axes together, so one axis cannot be moved
to zero on its own.

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
