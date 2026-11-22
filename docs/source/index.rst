gleplot Documentation
=====================

A Python library to **write standard GLE (Graphics Layout Engine) from Python, with matplotlib-shaped names**, for publication-quality vector graphics. Where gleplot differs from matplotlib is listed in :doc:`guides/MATPLOTLIB_MIGRATION`.

Start with :doc:`getting_started` for installation and your first plot (coming from gleplot 5, see :doc:`guides/MIGRATING_TO_6`), then the user guide (starting with :doc:`guides/FIGURES_AND_SUBPLOTS`) and the :doc:`gallery` for common patterns.

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
   guides/MIGRATING_TO_6

.. toctree::
   :maxdepth: 1
   :caption: User guide

   guides/FIGURES_AND_SUBPLOTS
   guides/PLOT_TYPES
   guides/AXES_AND_LEGENDS
   guides/COLORS_AND_MARKERS
   guides/TEXT_ANNOTATIONS
   guides/REFERENCE_LINES_AND_SPANS
   guides/CONTOUR_AND_HEATMAPS
   guides/FILE_BASED_SERIES
   guides/VIEW_FUNCTION
   guides/CONFIGURATION
   guides/OPENING_GLE_FILES

.. toctree::
   :maxdepth: 1
   :caption: Gallery

   gallery

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

- **matplotlib-shaped names** -- matplotlib's function names and arguments, writing what GLE draws natively.
- **Direct GLE generation** -- compact ``.gle`` scripts (typically a few kilobytes) you can edit by hand.
- **Vector output** -- PDF, PNG, EPS, SVG, and JPG when GLE and its include library are installed.
- **Plot types** -- lines, scatter, bars, fill-between, error bars, heatmaps, contours, and more.
- **Publication-oriented defaults** -- styling aimed at journal figures.
- **Lightweight** -- pure Python; numpy is the only dependency.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`