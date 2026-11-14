gleplot Documentation
=====================

A Python library that provides a **matplotlib-compatible API** for creating scientific plots that directly generate GLE (Graphics Layout Engine) scripts for publication-quality vector graphics.

gleplot also ships an optional **desktop editor** for building figures interactively -- load data, style series from dockable panels, arrange subplots, and export, all with a live preview. Prebuilt Windows and macOS binaries are available from the `GitHub Releases page <https://github.com/benhuddart/gleplot/releases>`_, or install it from a clone with ``pip install -e ".[gui]"``. See :doc:`gui` for details.

Start with :doc:`getting_started` for installation and your first plot, then :doc:`usage` and the :doc:`gallery` for common patterns.

Live Documentation
------------------

View the published documentation at:

https://benhuddart.github.io/gleplot/

**Explore the Project**

- `View the GitHub Repository <https://github.com/BenHuddart/gleplot>`_
- `Report Issues or Request Features <https://github.com/BenHuddart/gleplot/issues>`_
- :doc:`Contribute to gleplot <contributing>`

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

- **Matplotlib-compatible API** -- familiar function names and call patterns for plots you already write.
- **Direct GLE generation** -- compact ``.gle`` scripts (typically a few kilobytes) you can edit by hand.
- **Vector output** -- PDF, PNG, EPS, SVG, and JPG when GLE is installed.
- **Plot types** -- lines, scatter, bars, fill-between, error bars, heatmaps, contours, and more.
- **Publication-oriented defaults** -- styling aimed at journal figures.
- **Lightweight core** -- pure Python with minimal dependencies (NumPy only for the library API).

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`