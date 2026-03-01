# gleplot Configuration System - Implementation Summary

## Overview

A comprehensive configuration system has been added to gleplot, allowing users to customize appearance and behavior through configurable objects rather than hardcoded values. This provides three levels of customization: global defaults, per-figure settings, and per-element parameters.

## What Was Changed

### 1. New Module: `src/gleplot/config.py`

Created a complete configuration system with four main classes:

#### **GLEStyleConfig** - Text and Line Styling
- `font` (str) - Font name (default: 'texcmr')
- `fontsize` (float) - Font size in points (default: 10)
- `default_linewidth` (float) - Line width in points (default: 1.0)
- `default_color` (str) - Default line color (default: 'BLUE')
- `default_marker_color` (str) - Default marker color (default: 'BLUE')
- Line style codes for solid/dashed/dotted/dash-dot patterns

#### **GLEGraphConfig** - Graph Layout and Rendering
- `scale_mode` (str) - Axis scaling mode: 'auto', 'fixed', or 'fullsize'
- `title_distance` (float) - Title distance from graph (cm)
- `xlabel_distance` (float) - X-label distance (cm)
- `ylabel_distance` (float) - Y-label distance (cm)
- `legend_position` (str) - Legend position (default: 'tr')
- `legend_offset_x`, `legend_offset_y` (float) - Legend offset (cm)
- `smooth_curves` (bool) - Enable smooth curve fitting (default: True)
- `show_grid` (bool) - Show background grid (default: False)

#### **GLEMarkerConfig** - Marker Appearance
- `default_marker` (str) - Default marker type (default: 'fcircle')
- `msize_scale` (float) - Marker size scaling factor (default: 1.0)
- `mdist` (Optional[float]) - Marker distance on curves (default: None)

#### **GlobalConfig** - Singleton for Global Defaults
- Manages global `style`, `graph`, and `marker` configurations
- Methods: `reset()`, `get_style()`, `get_graph()`, `get_marker()`, `to_dict()`

### 2. Updated `src/gleplot/writer.py`

Modified `GLEWriter` class to use configuration instead of hardcoded values:

**Changes:**
- Constructor now accepts `style`, `graph`, and `marker` parameters
- `add_preamble()` uses `style.font` and `style.fontsize`
- `add_graph_size()` respects `graph.scale_mode` (auto/fixed/fullsize)
- `add_plot_line()` uses `style.default_linewidth` and `graph.smooth_curves`
- `add_plot_line()` uses configured line style codes
- `add_legend()` uses `graph.legend_position` with override support
- Font size conversion: points to cm (1 point = 0.0352 cm, GLE uses `set hei`)

**Line width handling improved:**
- Converts matplotlib points to GLE cm: `lwidth = linewidth × 0.03528`
- Falls back to `style.default_linewidth` when linewidth is 0 or 1
- Per-plot linewidth parameter overrides defaults

### 3. Updated `src/gleplot/figure.py`

Modified `Figure` class to support configuration:

**Changes:**
- Constructor accepts `style`, `graph`, and `marker` parameters
- Stores configurations as instance attributes
- `_generate_gle_with_files()` passes configs to `GLEWriter`
- Maintains backward compatibility (all parameters optional)

### 4. Updated `src/gleplot/__init__.py`

**Added exports:**
- `GLEStyleConfig`
- `GLEGraphConfig`
- `GLEMarkerConfig`
- `GlobalConfig`

**Enhanced `figure()` function:**
- Now accepts `style`, `graph`, and `marker` parameters
- Comprehensive docstring with examples
- Maintains backward compatibility

### 5. Documentation

Created two comprehensive guide documents:

#### **`docs/guides/CONFIGURATION.md`**
- Overview of three-level configuration system
- Style, Graph, and Marker configuration examples
- Usage examples for different scenarios
- Troubleshooting section
- Reference tables for colors, fonts, markers, positions

#### **`docs/guides/CONFIGURATION_API.md`**
- Complete API reference for all classes and methods
- Detailed attribute descriptions
- Valid value ranges and defaults
- Usage examples for each class
- Advanced usage patterns
- Configuration priority explanation

### 6. Example Script

Created `examples/example_configuration.py`:
- Demonstrates global configuration
- Shows per-figure configuration
- Illustrates marker customization
- Smooth curve control
- Custom line styles

## Backward Compatibility

✅ **All changes are fully backward compatible**
- All new parameters are optional with sensible defaults
- Existing code works without any changes
- Default behavior unchanged from user perspective

## Testing

✅ **All 114 tests pass**
- Configuration system works seamlessly with existing tests
- No breaking changes
- All plot types supported (lines, scatter, bar, fill_between)
- All output formats supported (PDF, EPS, PNG)

## Example Usage

### Global Configuration
```python
import gleplot as glp

# Modify global defaults
glp.GlobalConfig.style.font = 'helvetica'
glp.GlobalConfig.graph.legend_position = 'tl'

# All new figures use these settings
fig = glp.figure()
```

### Per-Figure Configuration
```python
style = glp.GLEStyleConfig(font='courier', fontsize=12)
graph = glp.GLEGraphConfig(scale_mode='auto', smooth_curves=True)

fig = glp.figure(style=style, graph=graph)
```

### Element-Level Override
```python
ax.plot([1, 2, 3], [1, 2, 3], linewidth=2.0, color='red')
```

## Key Features

1. **Three-level configuration hierarchy**
   - Factory defaults < Global < Figure < Element

2. **Sensible defaults**
   - No configuration needed for basic usage
   - All defaults optimized for typical plots

3. **Easy customization**
   - Modify global defaults for consistency across figures
   - Create custom configs for specific figure types
   - Override at element level when needed

4. **Well documented**
   - Complete API reference
   - Tutorial-style guide
   - Examples for common scenarios
   - Troubleshooting tips

5. **Type-safe configuration**
   - Dataclass-based with type hints
   - IDE autocomplete support
   - Clear validation messages

## Files Modified/Created

### Created:
- `src/gleplot/config.py` - Configuration system
- `docs/guides/CONFIGURATION.md` - Configuration guide
- `docs/guides/CONFIGURATION_API.md` - API reference
- `examples/example_configuration.py` - Configuration examples

### Modified:
- `src/gleplot/writer.py` - Use configs instead of hardcoded values
- `src/gleplot/figure.py` - Accept and pass configuration objects
- `src/gleplot/__init__.py` - Export config classes, enhance figure()

### Tests:
- `tests/integration/test_api.py` - Updated for log axis syntax

## Performance Impact

✅ **Negligible**
- Configuration is only used during script generation (not interactive)
- No runtime overhead for plotting
- One-time cost at figure creation

## Future Enhancements

Potential areas for future expansion:
- Grid configuration (colors, styles, spacing)
- Axis tick configuration (format, precision, spacing)
- Color palette definitions
- Style themes (publication, presentation, poster)
- Configuration file support (JSON/YAML)

## Summary

The new configuration system makes gleplot significantly more flexible and user-friendly while maintaining full backward compatibility. Users can now:

1. ✅ Customize global appearance across all figures
2. ✅ Create publication-quality plots with consistent styling
3. ✅ Build presentation-ready figures with specific configurations
4. ✅ Override specific elements without affecting others
5. ✅ Switch between different style schemes easily

All while maintaining clean, intuitive API consistent with matplotlib.
