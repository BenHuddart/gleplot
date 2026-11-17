gleplot Documentation
=====================

A Python library that provides a **matplotlib-compatible API** for creating scientific plots that directly generate GLE (Graphics Layout Engine) scripts for publication-quality vector graphics.

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
   :maxdepth: 1
   :caption: Getting started

   getting_started

.. toctree::
   :maxdepth: 1
   :caption: User guide

   usage
   guides/COLORS_AND_MARKERS
   guides/TEXT_ANNOTATIONS
   guides/REFERENCE_LINES_AND_SPANS
   guides/CONTOUR_AND_HEATMAPS
   guides/BROKEN_AXES
   guides/FILE_BASED_SERIES
   guides/VIEW_FUNCTION
   guides/CONFIGURATION
   guides/CONFIGURATION_API

.. toctree::
   :maxdepth: 1
   :caption: Gallery

   gallery
   examples

.. toctree::
   :maxdepth: 1
   :caption: Coming from matplotlib

   guides/MATPLOTLIB_MIGRATION

.. toctree::
   :maxdepth: 1
   :caption: API reference

   api

.. toctree::
   :maxdepth: 1
   :caption: Troubleshooting

   guides/TROUBLESHOOTING

.. toctree::
   :maxdepth: 1
   :caption: Contributing

   contributing
   guides/TESTING
   guides/VERSIONING

.. toctree::
   :maxdepth: 1
   :caption: Changelog

   changelog

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