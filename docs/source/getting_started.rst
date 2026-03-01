Getting Started
===============

Installation
------------

Requirements
~~~~~~~~~~~~

- Python 3.7 or later
- numpy >= 1.16.0

Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~

To compile plots to PDF, PNG, or EPS, you need GLE installed:

.. code-block:: bash

   # macOS (Homebrew)
   brew install gle

   # Ubuntu/Debian
   sudo apt-get install gle

   # Fedora/RHEL
   sudo dnf install gle

Install gleplot
~~~~~~~~~~~~~~~

From PyPI:

.. code-block:: bash

   pip install gleplot

From source:

.. code-block:: bash

   git clone https://github.com/yourusername/gleplot.git
   cd gleplot
   pip install -e .

With development dependencies:

.. code-block:: bash

   pip install -e ".[dev]"

Basic Usage
-----------

Here's a simple example to get you started:

.. code-block:: python

   import numpy as np
   import gleplot as glp

   # Create linspace data
   x = np.linspace(0, 10, 100)
   y = np.sin(x)

   # Create figure and axis
   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)

   # Plot data
   ax.plot(x, y, label='sin(x)')

   # Customize plot
   ax.set_xlabel('X')
   ax.set_ylabel('Y')
   ax.set_title('Simple Plot')
   ax.legend()

   # Save the figure
   fig.savefig('plot.pdf')  # Requires GLE to be installed

You can also save as a GLE script without compiling:

.. code-block:: python

   fig.savefig('plot.gle')  # Save as GLE script

Then compile manually with GLE:

.. code-block:: bash

   gle -d pdf plot.gle
