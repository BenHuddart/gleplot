gleplot Documentation
=====================

A Python library that provides a **matplotlib-compatible API** for creating scientific plots that directly generate GLE (Graphics Layout Engine) scripts for publication-quality vector graphics.

gleplot also ships an optional **desktop editor** for building figures interactively -- load data, style series from dockable panels, arrange subplots, and export, all with a live preview. Prebuilt Windows and macOS binaries are available from the `GitHub Releases page <https://github.com/benhuddart/gleplot/releases>`_, or install it with ``pip install "gleplot[gui]"``. See :doc:`gui` for details.

Live Documentation
------------------

View the published documentation at:

https://benhuddart.github.io/gleplot/

**Explore the Project**

- 🧑‍💻 `View the GitHub Repository <https://github.com/BenHuddart/gleplot>`_
- 📝 `Report Issues or Request Features <https://github.com/BenHuddart/gleplot/issues>`_
- 🤝 `Contribute to gleplot <https://github.com/BenHuddart/gleplot>`_

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   usage
   gui
   gallery
   api
   examples
   contributing

Features
--------

✨ **Matplotlib-Compatible API** - All familiar functions work identically

✨ **Direct GLE Generation** - Optimized script output (1-2 KB)

✨ **Vector Graphics** - PDF, PNG, EPS export with publication quality

✨ **Full Plotting Support** - Lines, scatter, bars, fill_between

✨ **Publication Ready** - Suitable for all major academic journals

✨ **Lightweight** - Pure Python, minimal dependencies

Quick Start
-----------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   # Create data
   x = np.linspace(0, 2*np.pi, 100)

   # Create figure and plot
   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)
   ax.plot(x, np.sin(x), color='blue', label='sin(x)')
   ax.plot(x, np.cos(x), color='red', linestyle='--', label='cos(x)')

   # Configure plot
   ax.set_xlabel('x (radians)')
   ax.set_ylabel('y')
   ax.set_title('Trigonometric Functions')
   ax.legend()

   # Save as PDF (auto-compiles via GLE)
   fig.savefig('trig.pdf')

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
