# gleplot

**gleplot** is a matplotlib-style Python library for scientific figures. It generates [GLE](https://glx.sourceforge.io/) (Graphics Layout Engine) scripts and, when GLE is installed, compiles them to PDF, PNG, EPS, SVG, or JPG.

## Documentation

**[Full documentation and API reference](https://benhuddart.github.io/gleplot/)**

- [Getting started](https://benhuddart.github.io/gleplot/getting_started.html) on the published site
- [Examples](examples/)

## Installation

**Library** (Python 3.9+, numpy):

```bash
git clone https://github.com/benhuddart/gleplot.git
cd gleplot
pip install -e .
```

**GLE 4.3+** (optional; needed to compile to PDF/PNG/etc.—saving `.gle` always works):

- Install from [GLE releases](https://github.com/vlabella/GLE/releases/latest)
- Verify: `gle -info`

Further install notes (Ghostscript, LaTeX, `gle -finddeps`) are in the [getting started guide](https://benhuddart.github.io/gleplot/getting_started.html).

## Quick start

```python
import numpy as np
import gleplot as glp

x = np.linspace(0, 2 * np.pi, 100)

fig = glp.figure(figsize=(8, 6))
ax = fig.add_subplot(111)
ax.plot(x, np.sin(x), color="blue", label="sin(x)")
ax.plot(x, np.cos(x), color="red", linestyle="--", label="cos(x)")

ax.set_xlabel("x (radians)")
ax.set_ylabel("y")
ax.set_title("Trigonometric Functions")
ax.legend()

fig.savefig("trig.pdf")
fig.savefig("trig.gle")
```

## Also

Subplots, file-based series, configuration, and more: see the [usage guide](https://benhuddart.github.io/gleplot/usage.html) and the [topic guides](https://benhuddart.github.io/gleplot/guides.html).

## License

gleplot is licensed under **GPL-2.0+** (compatible with GLE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Questions and feature requests: [GitHub issues](https://github.com/benhuddart/gleplot/issues).