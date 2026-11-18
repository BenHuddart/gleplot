# Configuration Guide

This guide explains how to customize gleplot's appearance and behavior through the
configuration system.

## Overview

gleplot provides three levels of configuration:

1. **Global defaults** - Applied to all new figures
2. **Per-figure configuration** - Applied to individual figures
3. **Per-element settings** - Applied to individual plot elements (lines, markers, etc.)

## Global Configuration

Access and modify global defaults through `GlobalConfig`:

    import gleplot as glp
    
    # Modify global defaults
    glp.GlobalConfig.style.font = 'helvetica'
    glp.GlobalConfig.style.fontsize = 12
    glp.GlobalConfig.graph.legend_position = 'tl'
    
    # All new figures will use these settings
    fig = glp.figure()

**Copy-at-construction.** A figure created with no explicit `style=`/`graph=`/
`marker=` takes an independent COPY of the current `GlobalConfig` values at
the moment it is constructed -- not a live reference to `GlobalConfig`
itself. So the order above matters (set the global default, *then* create
the figure), and the reverse is also true: once `fig = glp.figure()` has
run, editing `fig.style.font` in place changes only `fig` -- it cannot leak
into other figures, and it cannot write back into `GlobalConfig.style`
either. (This is the fix for a real bug in earlier gleplot releases, where
`fig.style` for a default-styled figure *was* `GlobalConfig.style` itself,
so an in-place edit on one figure silently changed every other
default-styled figure in the process.) An explicit `style=`/`graph=`/
`marker=` object you construct and pass in yourself is unaffected by this --
it is still stored by reference, as it always was.

## Style Configuration (GLEStyleConfig)

Controls text and line rendering:

    style = glp.GLEStyleConfig(
        font='helvetica',          # 'texcmr' (default), 'helvetica', 'timesroman', etc.
        fontsize=10,               # Points (default: 12)
        default_linewidth=1.0,     # Line width in points (default: 1.5)
        default_color='BLUE',      # Default line color
        default_marker_color='BLUE',  # Default marker color
    )
    
    fig = glp.figure(style=style)

### Available Fonts

Common GLE fonts:
- `texcmr` (default) - TeX Computer Modern Roman
- `helvetica` - Sans-serif
- `timesroman` - Serif
- `courier` - Monospace

### Line Styles

Customize how different line styles are rendered:

    style = glp.GLEStyleConfig()
    style.line_style_solid = 1    # `-` (solid)
    style.line_style_dashed = 3   # `--` (dashed)
    style.line_style_dotted = 2   # `:` (dotted)
    style.line_style_dashdot = 6  # `-.` (dash-dot)

The numbers are GLE's own `lstyle` codes, and they are not in
solid/dashed/dotted/dash-dot order: GLE renders 2 as dotted, 3 as dashed and 6
as dash-dot. The defaults above are the codes that match their names.

### Line Caps, Joins and Dash Length

GLE sets how lines end, how they turn corners, and how long a dash is for the
whole page, so these are figure-wide:

    style = glp.GLEStyleConfig(
        line_cap='round',    # GLE `set cap`: 'butt', 'round' or 'square'
        line_join='round',   # GLE `set join`: 'mitre', 'round' or 'bevel'
        dashlen=0.1,         # GLE `set dashlen`, in cm
    )

Each is `None` by default, which writes nothing and keeps GLE's own butt caps,
mitre joins and 0.04 cm dash unit. The digits of an `lstyle` code are
multiples of `dashlen`. GLE does not lengthen dashes for a thicker line, so a
thick dashed line can read as dotted until `dashlen` is raised. matplotlib's
per-line `solid_capstyle` and friends are covered in
[Migrating from matplotlib](MATPLOTLIB_MIGRATION.md).

### LaTeX Labels (`usetex`)

`usetex=True` typesets every label with LaTeX, as matplotlib's `text.usetex`
does, so a figure for a LaTeX document can share its fonts and math:

    fig = glp.figure(style=glp.GLEStyleConfig(usetex=True))
    ax = fig.add_subplot(111)
    ax.set_xlabel(r'$\mu_0 H$ (T)')
    fig.savefig('plot.pdf')

The script gets GLE's `set texlabels 1`. Titles, axis labels, tick labels,
legend entries, `text` and `annotate` strings reach LaTeX as written: `$...$`
is LaTeX math rather than gleplot's mathtext translation, and text outside it
must be valid LaTeX, so an underscore is `\_` and a percent sign `\%` (pie
`autopct` percent signs are escaped for you, as in matplotlib). Set it when
creating the figure: a label set before `usetex` was turned on keeps its GLE
markup. The `font` setting does not reach LaTeX labels, and their size is the
standard LaTeX size nearest `fontsize`.

Saving the `.gle` script needs nothing extra. Compiling needs a LaTeX
installation that GLE can run, and a LaTeX error fails the compile with
LaTeX's message in the `GLECompileError`. PDF, EPS, PNG and JPG work; SVG
raises `ValueError`, because GLE cannot put LaTeX in SVG. GLE keeps LaTeX's
working files in a `.gle` directory beside the script, which is safe to
delete.

## Graph Configuration (GLEGraphConfig)

Controls graph layout and rendering:

    graph = glp.GLEGraphConfig(
        scale_mode='auto',           # 'auto', 'fixed', or 'fullsize'
        title_distance=None,         # Default Axes.title_dist (cm)
        xlabel_distance=None,        # Default Axes.xlabel_dist (cm)
        ylabel_distance=None,        # Default Axes.ylabel_dist (cm)
        legend_position='tr',        # Legend position: 'tr', 'tl', 'br', 'bl', etc.
        legend_offset_x=0.0,         # Legend x-offset (cm)
        legend_offset_y=0.0,         # Legend y-offset (cm)
        smooth_curves=False,         # Spline-smooth lines (GLE `smooth`); opt-in
        show_grid=False,             # Default grid on new axes
    )
    
    fig = glp.figure(graph=graph)

### Curve Smoothing (`smooth_curves`)

**A line series is drawn as a polyline through your points.** Straight
segments join consecutive measurements; nothing is drawn that is not in the
data.

`smooth_curves=True` opts into GLE's `smooth` keyword instead, which draws a
fitted piecewise-cubic spline. The curve then passes *near*, not through, the
points: it overshoots steep steps and rings around noise. That is a model of
the data, not the data, so keep it off for anything meant to be read
quantitatively. The legitimate uses are cosmetic -- a guide to the eye through
widely spaced points, or a densely sampled model curve where the spline and
the polyline are indistinguishable anyway.

    # Per figure
    fig = glp.figure(graph=glp.GLEGraphConfig(smooth_curves=True))

    # Or globally, for every figure created afterwards
    glp.GlobalConfig.graph.smooth_curves = True

The flag is per figure and is the *default* for every line series in it
(`plot`, `line_from_file`, and the line drawn by `errorbar`). Fills and
contour lines are never smoothed: GLE's `fill` command takes no `smooth`
qualifier, and contour polylines come out of GLE's own contouring of the
gridded surface, where splining would move the level off the surface it was
computed from.

#### Per-series smoothing

A `plot()` series can override the figure default, and can use GLE's other
smoothing option, by setting two fields on the series itself:

    ax.plot(x, y)
    ax.lines[0]["smooth_mode"] = "smoothm"   # 'none' | 'smooth' | 'smoothm'
    ax.lines[0]["svg_smooth"] = 3            # Savitzky-Golay iterations

* **`smooth_mode`** — leave it unset to follow `smooth_curves`; set it to
  override that one series. `'smooth'` is the piecewise-cubic fit described
  above, which is a fit *of a function of x* (gleplot sorts the series' rows
  by x for it). `'smoothm'` is GLE's multi-valued variant, for curves that
  have more than one y per x — a hysteresis loop, a closed contour; those
  keep their point order. `'none'` switches smoothing off for the series even
  when the figure default is on.
* **`svg_smooth`** — the number of passes of GLE's 7-point Savitzky–Golay
  filter (an integer ≥ 1; unset means off). This is a *filter of the values*,
  not a fit through them, and is independent of `smooth_mode`: set both and
  both are applied.

Both are limited to `plot()` line series. Error bars and `line_from_file`
series still follow the figure-wide flag.

> **Behaviour change in 1.9.0.** Before 1.9.0, `smooth_curves` defaulted to
> **`True`**: every line gleplot drew was a spline through the data, and no
> figure showed the measured polyline unless its author had found the flag and
> turned it off. Figures regenerated with 1.9.0 render as polylines --
> visibly more angular between sparse points, with no overshoot past local
> maxima. **That is the correct rendering.** If a curve now looks jagged, the
> jaggedness is in the data and was previously being hidden.
>
> To reproduce a pre-1.9.0 figure exactly, ask for smoothing explicitly:
> `glp.figure(graph=glp.GLEGraphConfig(smooth_curves=True))`, or one
> `glp.GlobalConfig.graph.smooth_curves = True` at the top of the script to
> restore the old behaviour everywhere in it.

#### Point order

A series is drawn, and written to its `.dat` file, in the order you passed its
points -- as in matplotlib. Consecutive points are joined in that order, so a
curve whose x is non-monotonic by design comes out as drawn: a hysteresis loop
closes, a parametric curve traces its parameter, a field sweep taken up and
back down shows both legs.

    # A circle, parameterised by angle: x runs 1 -> -1 -> 1
    t = np.linspace(0, 2 * np.pi, 200)
    ax.plot(np.cos(t), np.sin(t))

**Smoothing is the one exception.** GLE's `smooth` fits a piecewise cubic *as
a function of x* and needs the points in ascending x, so a series that will
actually be drawn with `smooth` -- it draws a line and `smooth_curves` is on
-- has its rows sorted by x (stably: points sharing an x keep their input
order). A closed or doubling-back curve cannot be smoothed meaningfully for
that reason; leave `smooth_curves` off for one, which is the default.

Sorting never applies to a series that draws no line (`scatter`), to
`fill_between`, or to `line_from_file`/`errorbar_from_file` (which reference
your file's rows and write nothing).

> **Behaviour change in 1.9.0.** Before 1.9.0, `plot()` and `errorbar()`
> sorted their points by ascending x before writing the data file -- a habit
> left over from when smoothing was on by default. Any series with
> non-monotonic x was silently reordered, both on screen and on disk. Figures
> regenerated with 1.9.0 draw the points in the order they were given; a loop
> that previously came out torn into two overlapping arcs now closes. If a
> figure depended on the old ordering, sort before plotting:
> `order = np.argsort(x); ax.plot(x[order], y[order])`.

#### Draw order (`zorder`)

By default gleplot emits data series in a fixed layer stack (fills and guide
bands at the back, reference lines next, then bars, lines, scatters, and
error bars, with file-based series last). That stack matches the historical
behaviour: markers and error bars stay on top of plain fit lines unless you
say otherwise.

Pass matplotlib's ``zorder`` on ``plot``, ``scatter``, or ``errorbar`` to
raise or lower a series relative to the others on the same axes. Higher
``zorder`` is drawn on top in the compiled figure. When two series share the
same ``zorder``, call order breaks the tie.

    ax.errorbar(t, y, yerr=e, fmt='o', zorder=1, label='data')
    ax.plot(t, y_fit, '--', zorder=2, label='fit')  # dashed fit above markers

Guide calls (`axvline`, `axhspan`, …) keep their fixed under-data layer in
this release; use ``zorder`` on the data series when you need fits above
points.

### Scale Modes

- **`'auto'` (default)** - Automatically sizes and centers axes within the graph box
  - Best for most plots
  - Leaves room for labels and titles
  
- **`'fixed'`** - Use explicit graph dimensions
  - Requires setting width/height in `add_graph_size()`
  - Axes scale to fill the specified box
  
- **`'fullsize'`** - Axes fill entire graph box with no margins
  - Equivalent to GLE's `fullsize` keyword
  - No automatic room for labels/titles (they may overlap axes)

### Legend Positions

`legend_position` takes GLE's two-letter key positions (`'tr'`, `'tl'`, …) or
the long forms such as `'top right'`. The full list is under
`GLEGraphConfig.legend_position` in the
[configuration API reference](https://benhuddart.github.io/gleplot/api_configuration.html).

## Marker Configuration (GLEMarkerConfig)

Controls marker/symbol appearance:

    marker_cfg = glp.GLEMarkerConfig(
        default_marker='fcircle',    # Default marker type
        msize_scale=1.0,             # Marker size scaling factor
        mdist=None,                  # cm between markers on marked lines (None = every point)
    )
    
    fig = glp.figure(marker=marker_cfg)

### Available Markers

Standard markers (matplotlib-compatible):
- `'o'`, `'circle'` - Circle
- `'s'`, `'square'` - Square
- `'^'`, `'triangle'` - Triangle
- `'d'`, `'diamond'` - Diamond
- `'+'`, `'cross'` - Cross

GLE-specific markers:
- `'fcircle'` (default) - Filled circle
- `'fsquare'` - Filled square
- `'ftriangle'` - Filled triangle
- `'fdiamond'` - Filled diamond
- `'wcircle'` - White-filled circle
- `'wsquare'` - White-filled square
- `'wtriangle'` - White-filled triangle
- `'wdiamond'` - White-filled diamond

## Usage Examples

### Example 1: Change Global Defaults

    import gleplot as glp
    
    # Set global defaults
    glp.GlobalConfig.style.font = 'helvetica'
    glp.GlobalConfig.style.fontsize = 12
    glp.GlobalConfig.graph.legend_position = 'tl'
    
    # Create figure (uses global defaults)
    fig = glp.figure()
    ax = fig.add_subplot(111)
    
    x = [1, 2, 3, 4, 5]
    y = [1, 4, 9, 16, 25]
    ax.plot(x, y, 'b-', label='Data')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.legend()
    
    fig.savefig('plot.pdf')

### Example 2: Per-Figure Configuration

    style = glp.GLEStyleConfig(
        font='courier',
        fontsize=10,
        default_linewidth=2.0,
    )
    
    graph = glp.GLEGraphConfig(
        scale_mode='fixed',
        legend_position='br',
    )
    
    fig = glp.figure(figsize=(10, 6), style=style, graph=graph)
    ax = fig.add_subplot(111)
    
    # ... plot commands ...

### Example 3: Different Styles for Different Figures

    # Figure 1: Publication (serif font, small labels)
    pub_style = glp.GLEStyleConfig(
        font='timesroman',
        fontsize=8,
        default_linewidth=1.5,
    )
    fig1 = glp.figure(style=pub_style)
    
    # Figure 2: Presentation (sans-serif, larger labels)
    pres_style = glp.GLEStyleConfig(
        font='helvetica',
        fontsize=14,
        default_linewidth=2.0,
    )
    fig2 = glp.figure(style=pres_style)

### Example 4: Tight Layout with No Margins

    graph = glp.GLEGraphConfig(scale_mode='fullsize')
    fig = glp.figure(graph=graph)
    ax = fig.add_subplot(111)
    
    # Plot + legends/labels will be in graph coordinate space
    # (May require manual positioning to avoid overlaps)

## Accessing Current Configuration

Get the current configuration of a figure:

    fig = glp.figure()
    
    # Access style config
    print(f"Font: {fig.style.font}")
    print(f"Font size: {fig.style.fontsize}")
    
    # Access graph config
    print(f"Scale mode: {fig.graph.scale_mode}")
    print(f"Legend position: {fig.graph.legend_position}")
    
    # Access marker config
    print(f"Default marker: {fig.marker_config.default_marker}")

## Layout and Output Naming Configuration

Margins and panel spacing (`subplots_adjust`) are in
[Figures and Subplots](FIGURES_AND_SUBPLOTS.md).

### Data Sidecar Naming with `data_prefix`

Set a figure-level `data_prefix` for deterministic sidecar `.dat` filenames in
batch workflows.

    import gleplot as glp
    import numpy as np

    x = np.linspace(0, 1, 50)
    fig = glp.figure(data_prefix='run42')
    ax = fig.add_subplot(111)
    ax.plot(x, x**2)
    fig.savefig('run42_result.gle')

Typical side files:

- `run42_0.dat`
- `run42_1.dat` (if additional series are generated)

`subplots` takes `data_prefix` too:

    fig, axes = glp.subplots(2, 1, sharex=True, data_prefix='experimentB')

For semantic per-series names, pass `data_name` to generated-data methods such
as `plot()` and `fill_between()`. The label is sanitized into a filename stem
(lowercased, punctuation collapsed to underscores), and reused names are
disambiguated with `_1`, `_2`, and so on:

    ax.plot(x, y_obs, data_name='Observed Signal')            # observed_signal.dat
    ax.fill_between(x, y_lo, y_hi, data_name='Confidence Band 95')  # confidence_band_95.dat

#### Allowed characters

The prefix is used **verbatim**, so the sidecar names stay predictable —
`data_prefix='experimentA'` yields `experimentA_0.dat`, not `experimenta_0.dat`.
In exchange it is validated when the figure is created, and an unusable prefix
raises `ValueError` immediately instead of producing a `.gle` script that fails
at compile time:

    glp.figure(data_prefix='mk+white')
    # ValueError: data_prefix 'mk+white' contains characters that cannot appear
    # in a GLE data filename: '+' at index 2. ...

Rejected: whitespace, control characters, and `!`, `"`, `+` (GLE cannot parse
these in the unquoted filename of a `data` statement), plus the path separators
`/` and `\`. An empty or whitespace-only prefix is rejected too; pass `None` for
the default `data_N.dat` naming.

Most other punctuation is allowed, including `.`, `-`, `_` and `#`. Note that
`data_name` behaves differently: it takes a free-form *label* and sanitizes it
into a filename stem, because no caller depends on its exact spelling.

## Resetting to Defaults

Reset all global configurations to defaults:

    glp.GlobalConfig.reset()

## Configuration Objects Reference

Every field of `GLEStyleConfig`, `GLEGraphConfig`, `GLEMarkerConfig` and
`GlobalConfig`, with its default, is in the
[configuration API reference](https://benhuddart.github.io/gleplot/api_configuration.html).

## Performance Notes

Configuration objects are lightweight and can be created/modified freely without
performance impact. Configurations are only used during GLE script generation
(when calling `savefig()`), not during plot creation.

## Troubleshooting

**"GLE compiler error: unknown option"**
- Some GLE versions may not support certain features
- Check GLE version: `gle --version`
- Refer to your GLE manual for supported options

**"Font not found"**
- Not all fonts are available on all systems
- Fallback fonts: 'texcmr' (always available), 'helvetica', 'courier'
- Check GLE installation for available fonts

**"Overlapping labels with fullsize mode"**
- `fullsize` leaves no automatic margins
- Use `scale_mode='auto'` (default) for automatic spacing
- Or manually adjust with `title_distance`, `xlabel_distance`, `ylabel_distance`
