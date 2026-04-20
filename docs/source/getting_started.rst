Getting Started
===============

This guide is designed as a short, practical path:

1. Install dependencies
2. Generate your first plot
3. Learn how output files are created
4. Use shared axes and custom data file names

Installation
------------

Requirements
~~~~~~~~~~~~

- Python 3.7 or later
- numpy >= 1.16.0

Install gleplot
~~~~~~~~~~~~~~~

From source (recommended for development):

.. code-block:: bash

   git clone https://github.com/BenHuddart/gleplot.git
   cd gleplot
   pip install -e .

With development dependencies:

.. code-block:: bash

   pip install -e ".[dev]"

Install GLE (optional but recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GLE is required for direct PDF/PNG/EPS compilation. The recommended install path is
the official release page:

- https://github.com/vlabella/GLE/releases/latest
- https://glx.sourceforge.io/download/

Verify your install:

.. code-block:: bash

   gle -finddeps
   gle -info

First Plot (Step by Step)
-------------------------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   # 1) Create data
   x = np.linspace(0, 10, 100)
   y = np.sin(x)

   # 2) Create figure and axis
   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)

   # 3) Plot and label
   ax.plot(x, y, label='sin(x)')
   ax.set_xlabel('x')
   ax.set_ylabel('y')
   ax.set_title('My first gleplot figure')
   ax.legend()

   # 4) Save
   fig.savefig('first_plot.gle')  # Always works (script + data files)
   fig.savefig('first_plot.pdf')  # Requires GLE installed

How Output Files Work
---------------------

When you call ``savefig``, gleplot writes:

- a main ``.gle`` script file
- one or more external ``.dat`` files containing plotting data

By default, data files use a global pattern like ``data_0.dat``, ``data_1.dat``, etc.

If you want to keep each export self-contained, pass ``folder=True`` to ``savefig``.
For example, ``fig.savefig('first_plot.pdf', folder=True)`` creates a
``first_plot.gleplot`` directory containing the compiled output, the
intermediate ``.gle`` script, and the generated ``.dat`` files.

New: Custom Data File Names
---------------------------

Use ``data_prefix`` when creating a figure (or via ``subplots``) to control the
data-file naming scheme.

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(0, 1, 20)
   y = x**2

   fig = glp.figure(data_prefix='experimentA')
   ax = fig.add_subplot(111)
   ax.plot(x, y)
   fig.savefig('experimentA_plot.gle')

This produces files such as:

- ``experimentA_plot.gle``
- ``experimentA_0.dat``

New: Shared Axes in Subplots
----------------------------

For aligned multi-panel figures, share the x-axis or y-axis across subplots.

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(0, 10, 200)
   fig, axes = glp.subplots(3, 1, sharex=True, figsize=(8, 10))

   axes[0].plot(x, np.sin(x))
   axes[1].plot(x, np.cos(x))
   axes[2].plot(x, np.sin(x) + np.cos(x))
   axes[2].set_xlabel('time')

   fig.savefig('shared_x_example.gle')

With ``sharex=True``, only the bottom row shows x tick labels and x-axis label.
With ``sharey=True``, only the leftmost column shows y tick labels and y-axis label.
