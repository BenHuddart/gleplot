"""Configuration Guide for gleplot

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

## Style Configuration (GLEStyleConfig)

Controls text and line rendering:

    style = glp.GLEStyleConfig(
        font='helvetica',          # 'texcmr' (default), 'helvetica', 'timesroman', etc.
        fontsize=10,               # Points (1-100)
        default_linewidth=1.0,     # Line width in points (default: 1pt = 0.035cm)
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
    style.line_style_dashed = 2   # `--` (dashed)
    style.line_style_dotted = 3   # `:` (dotted)
    style.line_style_dashdot = 4  # `-.` (dash-dot)

## Graph Configuration (GLEGraphConfig)

Controls graph layout and rendering:

    graph = glp.GLEGraphConfig(
        scale_mode='auto',           # 'auto', 'fixed', or 'fullsize'
        title_distance=0.1,          # Distance (cm) from title to graph
        xlabel_distance=0.1,         # Distance (cm) from x-label to graph
        ylabel_distance=0.1,         # Distance (cm) from y-label to graph
        legend_position='tr',        # Legend position: 'tr', 'tl', 'br', 'bl', etc.
        legend_offset_x=0.0,         # Legend x-offset (cm)
        legend_offset_y=0.0,         # Legend y-offset (cm)
        smooth_curves=True,          # Enable GLE smooth keyword on lines
        show_grid=False,             # Show background grid
    )
    
    fig = glp.figure(graph=graph)

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

Short form (2-letter):
- `'tr'` - Top right (default)
- `'tl'` - Top left
- `'br'` - Bottom right
- `'bl'` - Bottom left
- `'tc'` - Top center
- `'bc'` - Bottom center
- `'lc'` - Left center
- `'rc'` - Right center
- `'cc'` - Center

Long form (accepted by both `figure()` and `ax.legend()`):
- `'top right'`
- `'top left'`
- `'bottom right'`
- `'bottom left'`
- `'center'`

## Marker Configuration (GLEMarkerConfig)

Controls marker/symbol appearance:

    marker_cfg = glp.GLEMarkerConfig(
        default_marker='fcircle',    # Default marker type
        msize_scale=1.0,             # Marker size scaling factor
        mdist=None,                  # Marker distance (None = every point)
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
    glp.GlobalConfig.graph.smooth_curves = True
    
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

## Resetting to Defaults

Reset all global configurations to defaults:

    glp.GlobalConfig.reset()

## Configuration Objects Reference

### GLEStyleConfig

Attributes:
- `font` (str) - Font name. Default: 'texcmr'
- `fontsize` (float) - Font size in points. Default: 10
- `default_linewidth` (float) - Default line width in points. Default: 1.0
- `default_color` (str) - Default line color. Default: 'BLUE'
- `default_marker_color` (str) - Default marker color. Default: 'BLUE'
- `line_style_solid` (int) - GLE style for solid lines. Default: 1
- `line_style_dashed` (int) - GLE style for dashed lines. Default: 2
- `line_style_dotted` (int) - GLE style for dotted lines. Default: 3
- `line_style_dashdot` (int) - GLE style for dash-dot lines. Default: 4

### GLEGraphConfig

Attributes:
- `scale_mode` (str) - ['auto', 'fixed', 'fullsize']. Default: 'auto'
- `title_distance` (float) - Title distance from graph (cm). Default: 0.1
- `xlabel_distance` (float) - X-label distance from graph (cm). Default: 0.1
- `ylabel_distance` (float) - Y-label distance from graph (cm). Default: 0.1
- `legend_position` (str) - Legend position code. Default: 'tr'
- `legend_offset_x` (float) - Legend x-offset (cm). Default: 0.0
- `legend_offset_y` (float) - Legend y-offset (cm). Default: 0.0
- `smooth_curves` (bool) - Enable smooth curves. Default: True
- `show_grid` (bool) - Show background grid. Default: False

### GLEMarkerConfig

Attributes:
- `default_marker` (str) - Default marker type. Default: 'fcircle'
- `msize_scale` (float) - Marker size scale factor. Default: 1.0
- `mdist` (Optional[float]) - Marker distance. Default: None

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
"""
