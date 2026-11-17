Examples
========

Illustrated plot recipes live in the :doc:`gallery`. This page covers a few
API details that are easy to miss when porting matplotlib scripts.

Custom data file prefix
-----------------------

Use ``data_prefix`` to control sidecar ``.dat`` names written next to your GLE
file. The prefix is used verbatim (invalid characters raise ``ValueError`` when
the figure is created).

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(0, 1, 50)

   fig = glp.figure(figsize=(8, 5), data_prefix='calibration')
   ax = fig.add_subplot(111)
   ax.plot(x, x, label='linear')
   ax.plot(x, x**2, label='quadratic')
   ax.legend()

   fig.savefig('calibration_curves.gle')

This writes ``calibration_0.dat``, ``calibration_1.dat``, and so on.

Scatter with different sizes
----------------------------

GLE's ``msize`` is a per-dataset attribute, so a per-point ``s`` array raises
``ValueError`` — plot one series per size band. ``s`` is an area in
points\ :sup:`2` (matplotlib's ``scatter`` convention); pass ``markersize=`` for
a diameter in points, as ``plot`` uses.

.. code-block:: python

   import numpy as np
   import gleplot as glp

   np.random.seed(42)
   x = np.random.rand(50)
   y = np.random.rand(50)
   weight = np.random.rand(50)

   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)
   for lo, hi, s, label in [(0.00, 0.33, 25, 'low'),
                            (0.33, 0.66, 100, 'mid'),
                            (0.66, 1.01, 400, 'high')]:
       band = (weight >= lo) & (weight < hi)
       ax.scatter(x[band], y[band], s=s, color='blue', label=label)
   ax.set_xlabel('X')
   ax.set_ylabel('Y')
   ax.set_title('Scatter Plot with Variable Sizes')
   ax.legend()
   fig.savefig('scatter_sizes.pdf')

Heatmaps and contour plots
--------------------------

See :doc:`guides/CONTOUR_AND_HEATMAPS`
for gridded and scattered raster plots, palettes, and colorbars. A minimal
gridded example:

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(-3, 3, 120)
   y = np.linspace(-2.5, 2.5, 100)
   X, Y = np.meshgrid(x, y)
   Z = np.exp(-(X**2 + Y**2) / 2.0)

   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)

   ax.imshow(Z, extent=(x[0], x[-1], y[0], y[-1]), cmap='viridis')
   ax.contour(x, y, Z, levels=6, colors='white', linewidths=0.7)

   ax.set_xlabel('x')
   ax.set_ylabel('y')
   fig.colorbar(label='amplitude')

   fig.savefig('example_heatmap_imshow.pdf')

``examples/advanced/phase_diagram.py`` builds a full antiferromagnet H-T phase
diagram with ``tripcolor``, ``tricontour``, and a colorbar.

Runnable scripts in the repository
----------------------------------

The ``examples/`` tree holds runnable scripts for focused workflows:

- ``text_annotations.py`` — alignment and boxed labels
- ``per_element_styling.py`` — different styles per element
- ``batch_figures.py`` — loop-based generation of many figures
- ``line_from_file.py`` — model overlays from existing data files
- ``data_prefix.py`` — deterministic sidecar naming
- ``phase_diagram.py`` — susceptibility phase diagram
- ``secondary_yaxis.py`` — data on a second y-axis
- ``configuration.py`` — global and per-figure configuration

``examples/basic/heatmap_imshow.py`` is a simple gridded ``imshow`` +
``contour`` example.

To run every example and compile it to PDF, EPS and PNG in
``examples/outputs/`` (requires GLE; these PNGs are the gallery images):

.. code-block:: bash

   python examples/run_and_compile.py

Without GLE, ``--no-compile`` runs the examples and writes only the ``.gle``
scripts and their data files.