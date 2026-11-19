# gleplot

[![Tests](https://github.com/BenHuddart/gleplot/actions/workflows/test.yml/badge.svg)](https://github.com/BenHuddart/gleplot/actions/workflows/test.yml)
[![Docs](https://github.com/BenHuddart/gleplot/actions/workflows/publish_docs.yml/badge.svg)](https://benhuddart.github.io/gleplot/)
[![License: GPL-2.0-or-later](https://img.shields.io/badge/license-GPL--2.0--or--later-blue.svg)](https://github.com/BenHuddart/gleplot/blob/main/LICENSE)

**gleplot** lets you write plotting code the way you would for matplotlib and get a [GLE](https://glx.sourceforge.io/) (Graphics Layout Engine) script out, which GLE compiles to publication-quality PDF, EPS, SVG, PNG or JPG.

<img src="https://benhuddart.github.io/gleplot/_static/gallery/example_combined_errorbars.png" alt="Measured points with horizontal and vertical error bars, and a dashed y = x² curve through them" width="560">

```python
import numpy as np
import gleplot as glp

x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
y = np.array([1.8, 4.2, 9.1, 16.3, 24.8])
xerr = np.array([0.15, 0.20, 0.10, 0.25, 0.18])
yerr = np.array([0.3, 0.5, 0.6, 0.8, 1.0])

fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
ax.errorbar(x, y, yerr=yerr, xerr=xerr, marker="o", fmt="none",
            color="blue", capsize=4, label="Measured")
x_fit = np.linspace(0.5, 5.5, 100)
ax.plot(x_fit, x_fit**2, color="red", linestyle="--", label="y = x²")
ax.set_xlabel("x")
ax.set_ylabel("y")
ax.set_title("Combined X and Y Error Bars")
ax.legend()

fig.savefig("fit.gle")  # the GLE script and its data files; GLE not needed
fig.savefig("fit.pdf")  # compiled by GLE
```

## Why gleplot

- **The output is a script you can read and edit.** `fit.gle` is a few dozen lines of plain GLE, with the data in `.dat` files beside it. Change a label or a colour by hand, and GLE compiles it to vector PDF, EPS or SVG, or to PNG or JPG.
- **Scripts open again.** `glp.open_gle("fit.gle")` reads a `.gle` file back into a `Figure` you can change from Python and save.
- **Nothing is lost on the way back.** GLE that gleplot does not recognise is kept and written out again, not dropped, so a script you edited by hand survives a round trip.
- **GLE is optional for writing.** Saving `.gle` works without GLE installed; you need GLE only to compile.

## Install

gleplot needs Python 3.9 or later and numpy. It is not on PyPI yet; install it from GitHub:

```bash
pip install git+https://github.com/BenHuddart/gleplot.git
```

To compile figures, install **GLE 4.3+** from the [GLE releases](https://github.com/vlabella/GLE/releases/latest) and check it with `gle -info`. The [getting started guide](https://benhuddart.github.io/gleplot/getting_started.html) covers Ghostscript, LaTeX and `gle -finddeps`.

To work on gleplot itself, use an editable install with the development tools, as described in [CONTRIBUTING.md](https://github.com/BenHuddart/gleplot/blob/main/CONTRIBUTING.md):

```bash
git clone https://github.com/BenHuddart/gleplot.git
cd gleplot
pip install -e ".[dev]"
```

## What it can plot

- Lines, scatter, bars, [pie charts](https://benhuddart.github.io/gleplot/gallery.html#pie-chart), [box plots](https://benhuddart.github.io/gleplot/gallery.html#box-plot), steps, stems and histograms ([plot types](https://benhuddart.github.io/gleplot/guides/PLOT_TYPES.html))
- [Error bars](https://benhuddart.github.io/gleplot/gallery.html#combined-x-y-error-bars), symmetric or asymmetric, in x and y
- [Fills between curves](https://benhuddart.github.io/gleplot/gallery.html#fill-between)
- [Heatmaps](https://benhuddart.github.io/gleplot/gallery.html#heatmap-imshow) and [contours](https://benhuddart.github.io/gleplot/gallery.html#phase-diagram-tripcolor-tricontour) with colour bars
- [Subplots](https://benhuddart.github.io/gleplot/gallery.html#x2-subplot-grid), [shared axes](https://benhuddart.github.io/gleplot/gallery.html#shared-x-axis-stacked) and [broken axes](https://benhuddart.github.io/gleplot/gallery.html#broken-x-axis-double-slash-break)
- [Log scales](https://benhuddart.github.io/gleplot/gallery.html#log-scale), [secondary axes](https://benhuddart.github.io/gleplot/gallery.html#secondary-y-axis) and [polar plots](https://benhuddart.github.io/gleplot/gallery.html#polar-plot)
- [Reference lines and shaded spans](https://benhuddart.github.io/gleplot/guides/REFERENCE_LINES_AND_SPANS.html), [text and arrows](https://benhuddart.github.io/gleplot/gallery.html#text-annotations)
- [Series read from existing data files](https://benhuddart.github.io/gleplot/guides/FILE_BASED_SERIES.html)

The [gallery](https://benhuddart.github.io/gleplot/gallery.html) shows every example with its code.

## Coming from matplotlib

`figure`, `subplots`, `plot`, `scatter`, `errorbar`, `savefig` and the other matplotlib names take matplotlib's arguments. Where GLE cannot do what a keyword asks, gleplot accepts it and warns; the [matplotlib migration guide](https://benhuddart.github.io/gleplot/guides/MATPLOTLIB_MIGRATION.html) lists each difference.

## Documentation

The [documentation site](https://benhuddart.github.io/gleplot/) has the user guides and the API reference.

## Contributing

See [CONTRIBUTING.md](https://github.com/BenHuddart/gleplot/blob/main/CONTRIBUTING.md). Questions and feature requests go to [GitHub issues](https://github.com/BenHuddart/gleplot/issues).

## License

gleplot is licensed under the [GPL-2.0 or later](https://github.com/BenHuddart/gleplot/blob/main/LICENSE).
