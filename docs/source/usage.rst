Usage Guide
===========

This guide focuses on practical patterns you will reuse often:

- Start with single-axis plots
- Scale to subplot layouts
- Use shared axes for clean comparative panels
- Use custom data file prefixes for reproducible outputs

Creating Figures
----------------

Creating a new figure:

.. code-block:: python

   import gleplot as glp

   fig = glp.figure(figsize=(10, 6))
   ax = fig.add_subplot(111)

You can specify the figure size in inches:

.. code-block:: python

   fig = glp.figure(figsize=(8, 6))  # 8 inches wide, 6 inches tall

Creating Multiple Subplots
----------------------------

For multiple subplots, use the standard matplotlib approach:

.. code-block:: python

   fig = glp.figure(figsize=(12, 8))
   
   ax1 = fig.add_subplot(2, 2, 1)
   ax1.plot(x, y1)
   ax1.set_title('Plot 1')
   
   ax2 = fig.add_subplot(2, 2, 2)
   ax2.plot(x, y2)
   ax2.set_title('Plot 2')
   
   ax3 = fig.add_subplot(2, 2, 3)
   ax3.plot(x, y3)
   ax3.set_title('Plot 3')
   
   ax4 = fig.add_subplot(2, 2, 4)
   ax4.plot(x, y4)
   ax4.set_title('Plot 4')

Shared Axes
-----------

Shared axes are useful when panels should be compared directly.

Shared x-axis (stacked plots):

.. code-block:: python

   fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 10))
   axes[0].plot(x, y_top)
   axes[1].plot(x, y_mid)
   axes[2].plot(x, y_bottom)
   axes[2].set_xlabel('Time')

Shared y-axis (side-by-side plots):

.. code-block:: python

   fig, axes = glp.subplots(1, 3, sharey=True, figsize=(14, 4))
   axes[0].scatter(x1, y1)
   axes[1].scatter(x2, y2)
   axes[2].scatter(x3, y3)
   axes[0].set_ylabel('Response')

Behavior summary:

- ``sharex=True``: only bottom row shows x-axis labels/ticks
- ``sharey=True``: only leftmost column shows y-axis labels/ticks
- Axis limits are synchronized across shared dimensions

Adjusting Subplot Layout
------------------------

Use ``Figure.subplots_adjust(...)`` to fine-tune subplot margins and spacing
when default panel geometry needs more room for labels, titles, or annotations.

- ``left``, ``right``, ``bottom``, ``top`` are normalized figure fractions in ``[0, 1]``
- ``wspace`` and ``hspace`` follow matplotlib semantics (fraction of average panel size)

.. code-block:: python

   fig, axes = glp.subplots(2, 2, figsize=(10, 8))

   axes[0].plot(x, y_a)
   axes[1].plot(x, y_b)
   axes[2].plot(x, y_c)
   axes[3].plot(x, y_d)

   # Increase outer margins and panel spacing.
   fig.subplots_adjust(
      left=0.12,
      right=0.98,
      bottom=0.1,
      top=0.92,
      wspace=0.35,
      hspace=0.4,
   )

Validation rules match expected matplotlib-style constraints:

- ``left < right`` and ``bottom < top``
- ``wspace >= 0`` and ``hspace >= 0``

Plotting Data
-------------

Line Plots
~~~~~~~~~~

.. code-block:: python

   ax.plot(x, y, label='data', color='blue', linestyle='-', linewidth=2)

Scatter Plots
~~~~~~~~~~~~~

.. code-block:: python

   ax.scatter(x, y, s=50, color='red', marker='o', alpha=0.6)

Bar Plots
~~~~~~~~~

.. code-block:: python

   ax.bar(x, y, width=0.8, color='green', label='bars')

Fill Between
~~~~~~~~~~~~~

.. code-block:: python

   ax.fill_between(x, y1, y2, alpha=0.3, color='blue')

File-Based Series
~~~~~~~~~~~~~~~~~

Use existing data files directly when you already have tabular outputs from
an external pipeline. Column indices are 1-based, matching GLE syntax.

.. code-block:: python

   # Data columns: c1=time, c2=signal, c3=sigma, c4=model
   ax.errorbar_from_file(
      'results.dat',
      x_col=1,
      y_col=2,
      yerr_col=3,
      color='blue',
      marker='o',
      label='Measured'
   )

   # Overlay model/fit curve from the same file without generating data_*.dat
   ax.line_from_file(
      'results.dat',
      x_col=1,
      y_col=4,
      color='red',
      linestyle='--',
      linewidth=2,
      label='Fit'
   )

Text Annotations
~~~~~~~~~~~~~~~~

Add labels directly in data coordinates.

.. code-block:: python

   ax.plot(x, y)
   ax.text(3.2, 1.5, 'Peak A', color='black', fontsize=11, ha='center')

   # pyplot-style convenience
   import gleplot as glp
   glp.text(1.0, 0.5, 'Reference')

Customizing Axes
----------------

Axis Labels and Title
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   ax.set_xlabel('X Axis Label')
   ax.set_ylabel('Y Axis Label')
   ax.set_title('Plot Title')

Axis Limits
~~~~~~~~~~~~

.. code-block:: python

   ax.set_xlim(0, 10)
   ax.set_ylim(-1, 1)

Axis Scale
~~~~~~~~~~~

.. code-block:: python

   ax.set_xscale('log')   # Logarithmic scale
   ax.set_yscale('log')

Grid
~~~~~

.. code-block:: python

   ax.grid(True)          # Show grid
   ax.grid(True, which='both')  # Show both major and minor grid

Legends
-------

.. code-block:: python

   ax.plot(x, y1, label='Series 1')
   ax.plot(x, y2, label='Series 2')
   ax.legend()           # Show legend with default location
   ax.legend(loc='upper right')  # Custom location

Line Styles and Colors
----------------------

Available line styles:

- ``'-'`` : solid line (default)
- ``'--'`` : dashed line
- ``'-.'`` : dash-dot line
- ``':'`` : dotted line

Available colors:

- Named colors: ``'red'``, ``'blue'``, ``'green'``, ``'black'``, etc.
- Hex colors: ``'#FF0000'``
- RGB tuples: ``(0.5, 0.5, 0.5)``

.. code-block:: python

   ax.plot(x, y, color='red', linestyle='--', linewidth=2)
   ax.scatter(x, y, color='#0000FF', s=100)

Saving Figures
--------------

Save as PDF (requires GLE):

.. code-block:: python

   fig.savefig('plot.pdf')

Save as PNG (requires GLE):

.. code-block:: python

   fig.savefig('plot.png', dpi=300)

Save as GLE script (for manual editing or compilation):

.. code-block:: python

   fig.savefig('plot.gle')

Save as EPS:

.. code-block:: python

   fig.savefig('plot.eps')

You can also specify output directory:

.. code-block:: python

   fig.savefig('/path/to/output/plot.pdf')

Custom Data File Naming
-----------------------

Each saved figure writes one ``.gle`` script plus one or more external ``.dat`` files.
To make data-file names easier to trace in batch workflows, pass ``data_prefix``.

.. code-block:: python

   fig = glp.figure(data_prefix='run42')
   ax = fig.add_subplot(111)
   ax.plot(x, y)
   fig.savefig('run42_result.gle')

Expected side files include:

- ``run42_0.dat``
- ``run42_1.dat`` (if additional plot series are written)

For per-series naming, pass ``data_name`` to generated-data plot methods:

.. code-block:: python

   ax.plot(x, y_obs, data_name='Observed Signal')
   ax.fill_between(x, y_lo, y_hi, data_name='Confidence Band 95')

These names are sanitized to safe filenames, for example:

- ``Observed Signal`` -> ``observed_signal.dat``
- ``Confidence Band 95`` -> ``confidence_band_95.dat``

If a name is reused, gleplot automatically disambiguates it by suffixing
``_1``, ``_2``, and so on.

You can also combine this with subplots:

.. code-block:: python

   fig, axes = glp.subplots(2, 1, sharex=True, data_prefix='experimentB')
   axes[0].plot(x, y1)
   axes[1].plot(x, y2)
   fig.savefig('experimentB_summary.gle')
