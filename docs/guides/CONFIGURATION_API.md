"""gleplot Configuration API Reference

This document provides detailed API reference for gleplot's configuration system.

## Table of Contents

1. [GlobalConfig](#globalconfig) - Singleton for managing global defaults
2. [GLEStyleConfig](#glestyleconfig) - Text and line styling
3. [GLEGraphConfig](#glegraphconfig) - Graph layout and behavior
4. [GLEMarkerConfig](#glemarkerconfig) - Marker/symbol appearance
5. [Creating Custom Configurations](#creating-custom-configurations)
6. [Configuration Priority](#configuration-priority)

---

## GlobalConfig

**Class:** `gleplot.GlobalConfig`

Singleton class for managing global default configurations. All new figures
created without explicit configuration inherit from GlobalConfig.

### Usage

```python
import gleplot as glp

# Modify global defaults
glp.GlobalConfig.style.font = 'helvetica'
glp.GlobalConfig.graph.legend_position = 'tl'

# Reset to defaults
glp.GlobalConfig.reset()

# Access current global config
print(glp.GlobalConfig.get_style().font)
print(glp.GlobalConfig.get_graph().scale_mode)
```

### Methods

#### `GlobalConfig.reset() -> None`

Reset all configurations to factory defaults.

**Example:**
```python
glp.GlobalConfig.reset()  # All settings back to defaults
```

#### `GlobalConfig.get_style() -> GLEStyleConfig`

Get the global style configuration.

**Returns:** `GLEStyleConfig` instance

#### `GlobalConfig.get_graph() -> GLEGraphConfig`

Get the global graph configuration.

**Returns:** `GLEGraphConfig` instance

#### `GlobalConfig.get_marker() -> GLEMarkerConfig`

Get the global marker configuration.

**Returns:** `GLEMarkerConfig` instance

#### `GlobalConfig.to_dict() -> dict`

Export all configurations as nested dictionary.

**Returns:** Dictionary with keys 'style', 'graph', 'marker'

**Example:**
```python
config_dict = glp.GlobalConfig.to_dict()
print(config_dict['style']['font'])  # 'texcmr'
print(config_dict['graph']['scale_mode'])  # 'auto'
```

### Attributes

- `style` - `GLEStyleConfig` instance
- `graph` - `GLEGraphConfig` instance
- `marker` - `GLEMarkerConfig` instance

---

## GLEStyleConfig

**Class:** `gleplot.GLEStyleConfig`

Configuration for text and line styling.

### Constructor

```python
GLEStyleConfig(
    font: str = 'texcmr',
    fontsize: float = 10,
    default_linewidth: float = 1.0,
    default_color: str = 'BLUE',
    default_marker_color: str = 'BLUE',
    line_style_solid: int = 1,
    line_style_dashed: int = 2,
    line_style_dotted: int = 3,
    line_style_dashdot: int = 4,
)
```

### Attributes

#### `font: str`

GLE font name to use in all text.

**Valid values:** 'texcmr', 'helvetica', 'timesroman', 'courier', etc.
**Default:** 'texcmr'
**Type:** str
**Mutable:** Yes

**Example:**
```python
style = glp.GLEStyleConfig(font='helvetica')
# or modify existing
glp.GlobalConfig.style.font = 'timesroman'
```

#### `fontsize: float`

Font size in typographic points (1/72 inch).

**Valid range:** 1-100 points
**Default:** 10
**Type:** float
**Mutable:** Yes

**Example:**
```python
style = glp.GLEStyleConfig(fontsize=12)

# For very large fonts, use PostScript points
style.fontsize = 24  # 24pt = ~0.84cm
```

**Conversion:**
- 1 point = 1/72 inch ≈ 0.0352 cm
- 10 points ≈ 0.352 cm (default)
- 12 points ≈ 0.423 cm (standard)

#### `default_linewidth: float`

Default line width in typographic points.

**Valid range:** 0.1-10 points
**Default:** 1.0
**Type:** float
**Mutable:** Yes

**Note:** Individual plots can override this with the `linewidth` parameter.

**Example:**
```python
style = glp.GLEStyleConfig(default_linewidth=1.5)

fig = glp.figure(style=style)
ax = fig.add_subplot(111)
ax.plot([1, 2, 3], [1, 2, 3])  # Uses 1.5pt line width
ax.plot([1, 2, 3], [2, 3, 4], linewidth=3)  # Overrides with 3pt
```

#### `default_color: str`

Default color for lines and plot elements.

**Valid values:** GLE color names (see [Colors](#colors))
**Default:** 'BLUE'
**Type:** str
**Mutable:** Yes

**Example:**
```python
style = glp.GLEStyleConfig(default_color='RED')

fig = glp.figure(style=style)
ax = fig.add_subplot(111)
ax.plot([1, 2, 3], [1, 2, 3])  # Uses red
ax.plot([1, 2, 3], [2, 3, 4], color='blue')  # Overrides with blue
```

#### `default_marker_color: str`

Default color for markers in scatter plots.

**Valid values:** GLE color names
**Default:** 'BLUE'
**Type:** str
**Mutable:** Yes

#### `line_style_solid: int`

GLE line style code for solid lines (`'-'`).

**Valid range:** 1-9 (GLE style codes)
**Default:** 1
**Type:** int
**Mutable:** Yes

**GLE line styles:**
- 1 = solid (continuous)
- 2 = dashed (9-unit segments)
- 3 = dotted (3-unit segments)
- 4 = dash-dot (alternating 9-3 units)
- Custom: multi-digit codes (e.g., 12 = 1 black + 2 white repeating)

#### `line_style_dashed: int`

GLE line style code for dashed lines (`'--'`).

**Valid range:** 1-9
**Default:** 2
**Type:** int
**Mutable:** Yes

#### `line_style_dotted: int`

GLE line style code for dotted lines (`':'`).

**Valid range:** 1-9
**Default:** 3
**Type:** int
**Mutable:** Yes

#### `line_style_dashdot: int`

GLE line style code for dash-dot lines (`'-.'`).

**Valid range:** 1-9
**Default:** 4
**Type:** int
**Mutable:** Yes

### Methods

#### `to_dict() -> dict`

Export configuration as dictionary.

**Returns:** Dictionary with all attribute names as keys

**Example:**
```python
style = glp.GLEStyleConfig(font='helvetica', fontsize=12)
config_dict = style.to_dict()
# {'font': 'helvetica', 'fontsize': 12, 'default_linewidth': 1.0, ...}
```

---

## GLEGraphConfig

**Class:** `gleplot.GLEGraphConfig`

Configuration for graph layout and rendering behavior.

### Constructor

```python
GLEGraphConfig(
    scale_mode: str = 'auto',
    title_distance: float = 0.1,
    xlabel_distance: float = 0.1,
    ylabel_distance: float = 0.1,
    legend_position: str = 'tr',
    legend_offset_x: float = 0.0,
    legend_offset_y: float = 0.0,
    smooth_curves: bool = True,
    show_grid: bool = False,
)
```

### Attributes

#### `scale_mode: str`

How the graph axes are scaled within the graph box.

**Valid values:**
- `'auto'` - Auto-size and center axes (default)
- `'fixed'` - Use explicit dimensions from `add_graph_size()`
- `'fullsize'` - Axes fill entire box with no margins

**Default:** `'auto'`
**Type:** str
**Mutable:** Yes

**Behavior detail:**
- **`'auto'`** - Automatically calculates axis dimensions to leave room for labels
- **`'fixed'`** - Requires explicit size specification; axes scale proportionally
- **`'fullsize'`** - Equivalent to GLE's `fullsize` keyword; no automatic margins

**Example:**
```python
# Auto-scaling (recommended for most plots)
graph = glp.GLEGraphConfig(scale_mode='auto')

# Fixed dimensions
graph = glp.GLEGraphConfig(scale_mode='fixed')
fig = glp.figure(graph=graph)
# Later: writer.add_graph_size(width_cm=10, height_cm=8)

# Tight layout (no margins for labels)
graph = glp.GLEGraphConfig(scale_mode='fullsize')
```

#### `title_distance: float`

Distance (in cm) from graph box top to title text.

**Valid range:** 0.0-2.0 cm
**Default:** 0.1 cm
**Type:** float
**Mutable:** Yes

**Note:** Only applies to `'auto'` scale mode.

#### `xlabel_distance: float`

Distance (in cm) from graph box bottom to x-axis label.

**Valid range:** 0.0-2.0 cm
**Default:** 0.1 cm
**Type:** float
**Mutable:** Yes

**Note:** Only applies to `'auto'` scale mode.

#### `ylabel_distance: float`

Distance (in cm) from graph box left to y-axis label.

**Valid range:** 0.0-2.0 cm
**Default:** 0.1 cm
**Type:** float
**Mutable:** Yes

**Note:** Only applies to `'auto'` scale mode.

#### `legend_position: str`

Default position for legends/keys.

**Valid values:**
- Short form (GLE): `'tl'`, `'tr'`, `'bl'`, `'br'`, `'tc'`, `'bc'`, `'lc'`, `'rc'`, `'cc'`
- Long form: `'top right'`, `'top left'`, `'bottom right'`, `'bottom left'`, `'center'`

**Default:** `'tr'` (top right)
**Type:** str
**Mutable:** Yes

**Position codes:**
```
   tl --- tc --- tr
   |             |
   lc            rc
   |             |
   bl --- bc --- br
         cc
```

**Example:**
```python
graph = glp.GLEGraphConfig(legend_position='tl')
fig = glp.figure(graph=graph)
ax = fig.add_subplot(111)
ax.plot([1, 2, 3], [1, 2, 3], label='line')
ax.legend()  # Uses 'tl' position from config
ax.legend(loc='bottom right')  # Override with 'br'
```

#### `legend_offset_x: float`

X-offset for legend position (in cm).

**Valid range:** -5.0 to 5.0 cm
**Default:** 0.0 cm
**Type:** float
**Mutable:** Yes

**Positive:** Move legend right
**Negative:** Move legend left

#### `legend_offset_y: float`

Y-offset for legend position (in cm).

**Valid range:** -5.0 to 5.0 cm
**Default:** 0.0 cm
**Type:** float
**Mutable:** Yes

**Positive:** Move legend up
**Negative:** Move legend down

#### `smooth_curves: bool`

Enable smooth curve fitting on line plots (GLE `smooth` keyword).

**Valid values:** `True`, `False`
**Default:** `True`
**Type:** bool
**Mutable:** Yes

**Effect:**
- `True` - Fits piecewise cubic polynomials through data points
- `False` - Draws straight lines between points

**Example:**
```python
graph = glp.GLEGraphConfig(smooth_curves=False)
fig = glp.figure(graph=graph)
ax = fig.add_subplot(111)

x = [1, 2, 3, 4, 5]
y = [1, 4, 9, 16, 25]

ax.plot(x, y)  # Draws piecewise linear (not smooth)
```

**Performance note:** Smooth curves may be slightly slower to compile, but
the difference is negligible.

#### `show_grid: bool`

Show background grid in graph area.

**Valid values:** `True`, `False`
**Default:** `False`
**Type:** bool
**Mutable:** Yes

**Note:** Currently a placeholder for future implementation.

---

## GLEMarkerConfig

**Class:** `gleplot.GLEMarkerConfig`

Configuration for marker (symbol) appearance in scatter plots.

### Constructor

```python
GLEMarkerConfig(
    default_marker: str = 'fcircle',
    msize_scale: float = 1.0,
    mdist: Optional[float] = None,
)
```

### Attributes

#### `default_marker: str`

Default marker type for scatter plots when none is specified.

**Valid values:** See [Markers](#markers)
**Default:** `'fcircle'` (filled circle)
**Type:** str
**Mutable:** Yes

**Example:**
```python
marker_cfg = glp.GLEMarkerConfig(default_marker='fsquare')
fig = glp.figure(marker=marker_cfg)
ax = fig.add_subplot(111)

ax.scatter([1, 2, 3], [1, 2, 3])  # Uses filled square markers
ax.scatter([2, 3, 4], [2, 3, 4], marker='circle')  # Override with circle
```

#### `msize_scale: float`

Scaling factor applied to all marker sizes.

**Valid range:** 0.1-10.0
**Default:** 1.0
**Type:** float
**Mutable:** Yes

**Example:**
```python
marker_cfg = glp.GLEMarkerConfig(msize_scale=1.5)
fig = glp.figure(marker=marker_cfg)
ax = fig.add_subplot(111)

ax.scatter([1, 2, 3], [1, 2, 3], s=50)  # Marker size *= 1.5
```

#### `mdist: Optional[float]`

Default marker distance on continuous curves (in data or plot units).

**Valid range:** 0.1-10.0, or `None`
**Default:** `None` (markers at every data point)
**Type:** Optional[float]
**Mutable:** Yes

**Example:**
```python
# Sparse markers (every 0.5 units)
marker_cfg = glp.GLEMarkerConfig(mdist=0.5)
fig = glp.figure(marker=marker_cfg)
ax = fig.add_subplot(111)

x = np.linspace(0, 10, 100)
y = np.sin(x)
ax.plot(x, y, 'b-', marker='o')  # Shows ~20 markers instead of 100
```

### Methods

#### `to_dict() -> dict`

Export configuration as dictionary.

**Returns:** Dictionary with all attribute names as keys

---

## Creating Custom Configurations

### Complete Example: Publication-Quality Figure

```python
import gleplot as glp
import numpy as np

# Create publication-quality style
pub_style = glp.GLEStyleConfig(
    font='timesroman',        # Professional serif font
    fontsize=10,              # Standard publication size
    default_linewidth=1.5,    # Thicker lines for print
    default_color='BLACK',
)

# Create publication-quality layout
pub_graph = glp.GLEGraphConfig(
    scale_mode='auto',        # Leave room for labels
    legend_position='tl',     # Top-left (common in publications)
    smooth_curves=True,       # Smooth rendering
)

# Create publication-quality markers
pub_marker = glp.GLEMarkerConfig(
    default_marker='fsquare',
    msize_scale=0.8,          # Smaller for dense plots
)

# Create figure with all custom configs
fig = glp.figure(
    figsize=(10, 6),
    style=pub_style,
    graph=pub_graph,
    marker=pub_marker,
)

ax = fig.add_subplot(111)

# ... plot commands ...

fig.savefig('publication.pdf')
```

### Complete Example: Presentation Figure

```python
import gleplot as glp

# Create presentation style
pres_style = glp.GLEStyleConfig(
    font='helvetica',         # Clean sans-serif
    fontsize=14,              # Large for visibility
    default_linewidth=2.5,    # Bold lines
    default_color='DARKBLUE',
)

# Create presentation layout
pres_graph = glp.GLEGraphConfig(
    scale_mode='auto',
    legend_position='br',     # Bottom-right
    smooth_curves=True,
)

# Create figure
fig = glp.figure(figsize=(12, 8), style=pres_style, graph=pres_graph)
ax = fig.add_subplot(111)

# ... plot commands ...

fig.savefig('presentation.pdf')
```

---

## Configuration Priority

When creating plots, configurations are applied in this order (lowest to highest priority):

1. **Factory defaults** - Settings hard-coded in config classes
2. **Global defaults** - `GlobalConfig` settings
3. **Figure-level config** - Config passed to `figure()`
4. **Element-level parameters** - Parameters to `plot()`, `scatter()`, etc.

**Example showing priority:**

```python
import gleplot as glp

# 1. Set global default
glp.GlobalConfig.style.default_color = 'RED'

# 2. Create figure with different style
fig_style = glp.GLEStyleConfig(default_color='GREEN')
fig = glp.figure(style=fig_style)
ax = fig.add_subplot(111)

# 3. Plot with element-level parameter
ax.plot([1, 2, 3], [1, 2, 3])                    # Uses GREEN (from fig config)
ax.plot([1, 2, 3], [2, 3, 4], color='BLUE')     # Uses BLUE (element parameter)

# Other figures still use RED (from global)
fig2 = glp.figure()
ax2 = fig2.add_subplot(111)
ax2.plot([1, 2, 3], [1, 2, 3])  # Uses RED
```

---

## Advanced Usage

### Saving and Loading Configurations

```python
import json

# Export global config
config_dict = glp.GlobalConfig.to_dict()

# Save to file
with open('config.json', 'w') as f:
    json.dump(config_dict, f, indent=2)

# Later: reload and apply
with open('config.json', 'r') as f:
    config_dict = json.load(f)

# Manually restore
glp.GlobalConfig.style.font = config_dict['style']['font']
glp.GlobalConfig.style.fontsize = config_dict['style']['fontsize']
# ... etc
```

### Creating a Config Factory

```python
def create_publication_config():
    \"\"\"Create configuration for publication-quality plots.\"\"\"
    return {
        'style': glp.GLEStyleConfig(
            font='timesroman',
            fontsize=10,
            default_linewidth=1.5,
        ),
        'graph': glp.GLEGraphConfig(
            scale_mode='auto',
            legend_position='tl',
        ),
        'marker': glp.GLEMarkerConfig(
            default_marker='fsquare',
            msize_scale=0.8,
        ),
    }

# Usage
config = create_publication_config()
fig = glp.figure(**config)
```

---

## See Also

- [Configuration Guide](CONFIGURATION.md) - Tutorial-style guide with examples
- [API Reference](../api.rst) - Complete API documentation
- [GLE Manual](https://www.gle-graphics.org/manual/) - Complete GLE documentation
"""
