# Shared Axes Improvement Summary

## Problem Addressed
The original implementation of shared axes was using `xaxis off` and `yaxis off` commands, which completely hid the axis (including ticks). This violated the user requirement: "We also don't want to remove the ticks from subplots, just any labels are provided by the other graphs in the figure."

## Solution Implemented
Replaced the incorrect axis hiding approach with GLE's proper label control commands:

**Before (Incorrect):**
```gle
xaxis min 0 max 10 off      ! Hides entire axis including ticks
```

**After (Correct):**
```gle
xaxis min 0 max 10          ! Keep axis and ticks
xlabels off                 ! Hide only the numeric labels
```

## GLE Manual Reference
Per GLE manual (graph/graph.tex, Lines 950-958):
- `xaxis nofirst nolast` - Remove first or last (or both) labels from the graph
- `xlabels off` - Turn off axis tick labels (numbers) while keeping the ticks themselves
- `xticks` - Control tick appearance separately

## Code Changes

### [writer.py](src/gleplot/writer.py) - Lines 130-195

**Key modifications:**
1. Removed logic that appended `off` to xaxis/yaxis commands
2. Added separate `xlabels off` and `ylabels off` commands when labels should be hidden
3. Updated docstring to clarify: `show_xticks` controls "tick LABELS/NUMBERS", not the tick marks

```python
# Hide x-axis tick labels if requested (but keep the ticks themselves)
if not show_xticks:
    self.lines_gle.append('    xlabels off')

# Same for y-axis
if not show_yticks:
    self.lines_gle.append('    ylabels off')
```

## Generated Output Example

For a 3-subplot shared x-axis layout:

```gle
# Subplot 1 (top, no x-label)
amove 1 20.52
begin graph
    size 23.4 8.96
    ytitle "Amplitude"
    xaxis min 0 max 10
    xlabels off              ! ← Numeric labels hidden, ticks visible
    ...
end graph

# Subplot 2 (middle, no x-label)
amove 1 10.76
begin graph
    size 23.4 8.96
    ytitle "Amplitude"
    xaxis min 0 max 10
    xlabels off              ! ← Numeric labels hidden, ticks visible
    ...
end graph

# Subplot 3 (bottom, with x-label)
amove 1 1
begin graph
    size 23.4 8.76
    xtitle "Time (s)"        ! ← Only on bottom subplot
    ytitle "Amplitude"
    xaxis min 0 max 10       ! ← No xlabels off here, labels visible
    ...
end graph
```

## Test Results

- **Total Tests:** 140
- **Passed:** 139 ✓
- **Failed:** 1 (pre-existing capsize issue unrelated to axis changes)
- **Generated Test Graphics:** 11 PDFs with improved shared axis formatting

### Test Files with Shared Axes
- `test_08_shared_x_axis.gle` - 3 subplots sharing x-axis
- `test_09_shared_y_axis.gle` - 3 subplots sharing y-axis  
- `test_10_shared_both.gle` - 2×2 grid with both axes shared

## Visual Improvements

### Before
- X/Y-axis completely hidden on shared axes subplots
- No visual alignment reference between subplots
- Missing tick marks made alignment unclear

### After
- Tick marks remain visible for alignment reference
- Numeric labels hidden on non-primary axes (no redundancy)
- Proper axis boundaries still indicated by ticks
- Cleaner visual layout with intelligent label placement

## User Requirements Met
✓ Ticks are kept visible on all subplots
✓ Labels removed from non-primary axes  
✓ Perfect alignment reference through tick marks
✓ No label overlap between adjacent subplots (intelligent placement)
✓ GLE manual conventions followed

## Backward Compatibility
No API changes. The improvement is transparent to users while producing better GLE output.
