Examples
=========

Simple Line Plot
----------------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(0, 2*np.pi, 100)
   y = np.sin(x)

   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)
   ax.plot(x, y, label='sin(x)')
   ax.set_xlabel('x')
   ax.set_ylabel('y')
   ax.set_title('Sine Wave')
   ax.legend()
   fig.savefig('sine.pdf')

Multiple Series
---------------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(0, 2*np.pi, 100)

   fig = glp.figure(figsize=(10, 6))
   ax = fig.add_subplot(111)

   ax.plot(x, np.sin(x), label='sin(x)', color='blue')
   ax.plot(x, np.cos(x), label='cos(x)', color='red', linestyle='--')
   ax.plot(x, np.tan(x), label='tan(x)', color='green', linestyle=':')

   ax.set_xlabel('Angle (radians)')
   ax.set_ylabel('Value')
   ax.set_title('Trigonometric Functions')
   ax.set_ylim(-3, 3)
   ax.legend(loc='upper right')
   ax.grid(True)

   fig.savefig('trig_functions.pdf')

Subplots
--------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(0, 10, 100)

   fig = glp.figure(figsize=(12, 8))

   # Plot 1: Line plot
   ax1 = fig.add_subplot(2, 2, 1)
   ax1.plot(x, np.sin(x))
   ax1.set_title('sin(x)')

   # Plot 2: Scatter plot
   ax2 = fig.add_subplot(2, 2, 2)
   ax2.scatter(x[::5], np.cos(x[::5]), color='red')
   ax2.set_title('cos(x)')

   # Plot 3: Bar plot
   ax3 = fig.add_subplot(2, 2, 3)
   categories = ['A', 'B', 'C', 'D']
   values = [10, 24, 36, 18]
   ax3.bar(categories, values, color='green')
   ax3.set_title('Bar Chart')

   # Plot 4: Multiple lines
   ax4 = fig.add_subplot(2, 2, 4)
   ax4.plot(x, np.sin(x), label='sin')
   ax4.plot(x, np.cos(x), label='cos')
   ax4.set_title('Overlaid Functions')
   ax4.legend()

   fig.savefig('subplots.pdf')

Scatter with Different Sizes
-----------------------------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   np.random.seed(42)
   x = np.random.rand(50)
   y = np.random.rand(50)
   sizes = np.random.rand(50) * 100

   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)
   ax.scatter(x, y, s=sizes, alpha=0.6, color='blue')
   ax.set_xlabel('X')
   ax.set_ylabel('Y')
   ax.set_title('Scatter Plot with Variable Sizes')
   fig.savefig('scatter_sizes.pdf')

Filled Area
-----------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.linspace(0, 4*np.pi, 100)
   y1 = np.sin(x)
   y2 = np.sin(x) * 0.5

   fig = glp.figure(figsize=(10, 6))
   ax = fig.add_subplot(111)
   ax.fill_between(x, y1, y2, alpha=0.3, color='blue', label='Filled area')
   ax.plot(x, y1, color='darkblue', label='Upper bound')
   ax.plot(x, y2, color='lightblue', label='Lower bound')
   ax.set_title('Filled Between Plot')
   ax.legend()
   fig.savefig('filled_area.pdf')

Logarithmic Scale
------------------

.. code-block:: python

   import numpy as np
   import gleplot as glp

   x = np.logspace(0, 3, 100)
   y = x**2

   fig = glp.figure(figsize=(8, 6))
   ax = fig.add_subplot(111)
   ax.plot(x, y)
   ax.set_xscale('log')
   ax.set_yscale('log')
   ax.set_xlabel('X (log scale)')
   ax.set_ylabel('Y (log scale)')
   ax.set_title('Power Law on Log-Log Plot')
   ax.grid(True, which='both')
   fig.savefig('loglog.pdf')
