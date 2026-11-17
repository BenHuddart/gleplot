Getting Started
===============

Install gleplot, make a first plot, and see which files it writes.

Installation
------------

Requirements
~~~~~~~~~~~~

- Python 3.9 or later
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
To name them yourself, see ``data_prefix`` and ``data_name`` in
:doc:`guides/CONFIGURATION`.

The file extension picks the output. A ``.gle`` script is always written and
needs nothing else; ``.pdf``, ``.png``, ``.eps``, ``.svg`` and ``.jpg`` are
compiled by GLE:

.. code-block:: python

   fig.savefig('plot.gle')
   fig.savefig('plot.pdf')
   fig.savefig('plot.png', dpi=300)
   fig.savefig('plot.eps')
   fig.savefig('/path/to/output/plot.pdf')

To keep each export self-contained, pass ``folder=True``.
``fig.savefig('plot.pdf', folder=True)`` creates a ``plot.gleplot`` directory
containing ``plot.pdf``, the intermediate ``plot.gle`` script, and the
generated ``.dat`` files.

Next steps
----------

The user guide covers each topic in turn, starting with
:doc:`guides/FIGURES_AND_SUBPLOTS` and :doc:`guides/PLOT_TYPES`. The
:doc:`gallery` shows every example with its code.
