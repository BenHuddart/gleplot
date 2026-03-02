Gallery
=======

This gallery showcases the variety of plots you can create with gleplot.
All examples are generated from the test suite in ``generate_test_graphics.py``.

Basic Plots
-----------

Line Plot
~~~~~~~~~

A simple line plot showing trigonometric functions with custom colors and line styles.

.. image:: _static/gallery/test_01_line_plot.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig = glp.figure(figsize=(6, 4.5))
   ax = fig.add_subplot(111)
   
   x = np.linspace(0, 10, 100)
   ax.plot(x, np.sin(x), color='blue', label='sin(x)', linewidth=2)
   ax.plot(x, np.cos(x), color='red', linestyle='--', label='cos(x)', linewidth=2)
   
   ax.set_xlabel('x')
   ax.set_ylabel('y')
   ax.set_title('Basic Line Plot')
   ax.legend()
   
   fig.savefig('test_01_line_plot.pdf')

Scatter Plot
~~~~~~~~~~~~

Scatter plot demonstrating point markers with correlation.

.. image:: _static/gallery/test_02_scatter.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig = glp.figure(figsize=(6, 4.5))
   ax = fig.add_subplot(111)
   
   np.random.seed(42)
   x = np.random.randn(50)
   y = 2 * x + np.random.randn(50) * 0.5
   
   ax.scatter(x, y, color='green', marker='o', label='Data points')
   ax.set_xlabel('X variable')
   ax.set_ylabel('Y variable')
   ax.set_title('Scatter Plot with Correlation')
   ax.legend()
   
   fig.savefig('test_02_scatter.pdf')

Bar Chart
~~~~~~~~~

Multi-color bar chart showing categorical data.

.. image:: _static/gallery/test_03_bar_chart.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig = glp.figure(figsize=(6, 4.5))
   ax = fig.add_subplot(111)
   
   categories = np.array([1, 2, 3, 4, 5])
   values = np.array([23, 45, 56, 78, 32])
   colors = ['red', 'blue', 'green', 'orange', 'purple']
   
   ax.bar(categories, values, color=colors)
   ax.set_xlabel('Category')
   ax.set_ylabel('Value')
   ax.set_title('Colorful Bar Chart')
   
   fig.savefig('test_03_bar_chart.pdf')

Error Bars
~~~~~~~~~~

Data visualization with error bars showing measurement uncertainty.

.. image:: _static/gallery/test_04_error_bars.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig = glp.figure(figsize=(6, 4.5))
   ax = fig.add_subplot(111)
   
   x = np.array([1, 2, 3, 4, 5])
   y = np.array([2.3, 4.5, 3.8, 5.2, 4.9])
   yerr = np.array([0.3, 0.4, 0.2, 0.5, 0.3])
   
   ax.errorbar(x, y, yerr=yerr, marker='o', color='blue', 
               label='Measurements', capsize=5)
   ax.set_xlabel('Measurement number')
   ax.set_ylabel('Value')
   ax.set_title('Data with Error Bars')
   ax.legend()
   
   fig.savefig('test_04_error_bars.pdf')

Advanced Plots
--------------

Fill Between
~~~~~~~~~~~~

Shaded uncertainty band around a central line.

.. image:: _static/gallery/test_05_fill_between.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig = glp.figure(figsize=(6, 4.5))
   ax = fig.add_subplot(111)
   
   x = np.linspace(0, 10, 100)
   y = np.sin(x)
   y_upper = y + 0.3
   y_lower = y - 0.3
   
   ax.fill_between(x, y_lower, y_upper, color='lightblue', alpha=0.5, 
                    label='Uncertainty band')
   ax.plot(x, y, color='blue', linewidth=2, label='Mean')
   
   ax.set_xlabel('x')
   ax.set_ylabel('y')
   ax.set_title('Fill Between Example')
   ax.legend()
   
   fig.savefig('test_05_fill_between.pdf')

Logarithmic Scale
~~~~~~~~~~~~~~~~~

Log-log plot demonstrating power-law relationships.

.. image:: _static/gallery/test_06_log_scale.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig = glp.figure(figsize=(6, 4.5))
   ax = fig.add_subplot(111)
   
   x = np.logspace(0, 3, 50)
   y = x ** 2
   
   ax.plot(x, y, color='red', marker='o', markersize=4)
   ax.set_xscale('log')
   ax.set_yscale('log')
   ax.set_xlabel('x (log scale)')
   ax.set_ylabel('y (log scale)')
   ax.set_title('Logarithmic Scale Plot')
   
   fig.savefig('test_06_log_scale.pdf')

Subplots and Multi-Panel Figures
---------------------------------

Basic Subplots (2×2)
~~~~~~~~~~~~~~~~~~~~

Four-panel figure showing different trigonometric functions.

.. image:: _static/gallery/test_07_subplots_basic.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig, axes = glp.subplots(2, 2, figsize=(8, 7))
   
   x = np.linspace(0, 2*np.pi, 100)
   
   axes[0].plot(x, np.sin(x), color='blue')
   axes[0].set_title('sin(x)')
   
   axes[1].plot(x, np.cos(x), color='red')
   axes[1].set_title('cos(x)')
   
   axes[2].plot(x, np.tan(x), color='green')
   axes[2].set_title('tan(x)')
   axes[2].set_ylim(-5, 5)
   
   axes[3].plot(x, np.sin(x) * np.cos(x), color='purple')
   axes[3].set_title('sin(x)·cos(x)')
   
   fig.savefig('test_07_subplots_basic.pdf')

Shared X-Axis
~~~~~~~~~~~~~

Three vertically-stacked plots sharing a common x-axis. Only the bottom panel
shows x-tick labels, creating a clean aligned layout.

.. image:: _static/gallery/test_08_shared_x_axis.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig, axes = glp.subplots(3, 1, sharex=True, figsize=(7, 9))
   
   x = np.linspace(0, 10, 100)
   
   axes[0].plot(x, np.sin(x), color='blue', label='Signal A')
   axes[0].set_ylabel('Amplitude')
   axes[0].set_title('Shared X-Axis Example')
   axes[0].legend()
   
   axes[1].plot(x, np.sin(2*x), color='red', label='Signal B')
   axes[1].set_ylabel('Amplitude')
   axes[1].legend()
   
   axes[2].plot(x, np.sin(x) + np.sin(2*x), color='green', label='Combined')
   axes[2].set_xlabel('Time (s)')
   axes[2].set_ylabel('Amplitude')
   axes[2].legend()
   
   fig.savefig('test_08_shared_x_axis.pdf')

Shared Y-Axis
~~~~~~~~~~~~~

Three side-by-side plots sharing a common y-axis. Only the leftmost panel shows
y-tick labels for direct comparison across conditions.

.. image:: _static/gallery/test_09_shared_y_axis.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig, axes = glp.subplots(1, 3, sharey=True, figsize=(12, 4.5))
   
   x1 = np.linspace(0, 5, 50)
   x2 = np.linspace(0, 5, 50)
   x3 = np.linspace(0, 5, 50)
   
   axes[0].scatter(x1, x1**2, color='blue', marker='o')
   axes[0].set_xlabel('Input A')
   axes[0].set_ylabel('Response')
   axes[0].set_title('Condition A')
   
   axes[1].scatter(x2, 1.5*x2**2, color='red', marker='s')
   axes[1].set_xlabel('Input B')
   axes[1].set_title('Condition B')
   
   axes[2].scatter(x3, 0.8*x3**2, color='green', marker='^')
   axes[2].set_xlabel('Input C')
   axes[2].set_title('Condition C')
   
   fig.savefig('test_09_shared_y_axis.pdf')

Shared Both Axes (2×2)
~~~~~~~~~~~~~~~~~~~~~~

Four panels with both x and y axes shared. Only the left column shows y-tick labels
and the bottom row shows x-tick labels. Ideal for comparing similar data across conditions.

.. image:: _static/gallery/test_10_shared_both.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig, axes = glp.subplots(2, 2, sharex=True, sharey=True, figsize=(7, 6))
   
   x = np.linspace(-3, 3, 60)
   
   axes[0].plot(x, x, color='blue', label='y=x')
   axes[0].set_ylabel('y')
   axes[0].set_title('Linear')
   axes[0].legend()
   
   axes[1].plot(x, x**2 - 5, color='red', label='y=x²-5')
   axes[1].set_title('Quadratic')
   axes[1].legend()
   
   axes[2].plot(x, 0.3*x**3, color='green', label='y=0.3x³')
   axes[2].set_xlabel('x')
   axes[2].set_ylabel('y')
   axes[2].set_title('Cubic')
   axes[2].legend()
   
   axes[3].plot(x, 8*np.sin(x), color='purple', label='y=8sin(x)')
   axes[3].set_xlabel('x')
   axes[3].set_title('Sine')
   axes[3].legend()
   
   fig.savefig('test_10_shared_both.pdf')

Complex Combined Plot
~~~~~~~~~~~~~~~~~~~~~

A sophisticated plot combining multiple plot types: fill_between regions,
overlaid line plots, and scatter markers at intersection points.

.. image:: _static/gallery/test_11_complex_combined.png
   :width: 600px
   :align: center

.. code-block:: python

   import numpy as np
   import gleplot as glp

   fig = glp.figure(figsize=(7, 6))
   ax = fig.add_subplot(111)
   
   x = np.linspace(0, 10, 100)
   y1 = np.sin(x)
   y2 = np.cos(x)
   
   # Fill between
   ax.fill_between(x, y1, y2, where=(y1 >= y2), color='lightblue', 
                    alpha=0.3, label='sin > cos')
   ax.fill_between(x, y1, y2, where=(y1 < y2), color='lightcoral', 
                    alpha=0.3, label='cos > sin')
   
   # Lines
   ax.plot(x, y1, color='blue', linewidth=2, label='sin(x)')
   ax.plot(x, y2, color='red', linewidth=2, linestyle='--', label='cos(x)')
   
   # Scatter at intersections
   intersections_x = [np.pi/4, 5*np.pi/4]
   intersections_y = [np.sin(np.pi/4), np.sin(5*np.pi/4)]
   ax.scatter(intersections_x, intersections_y, color='black', 
              marker='o', s=100, zorder=5, label='Intersections')
   
   ax.set_xlabel('x')
   ax.set_ylabel('y')
   ax.set_title('Complex Combined Plot')
   ax.legend()
   ax.set_xlim(0, 10)
   
   fig.savefig('test_11_complex_combined.pdf')

Generating Your Own Gallery
----------------------------

All plots shown here are generated by running:

.. code-block:: bash

   python generate_test_graphics.py

The script creates both ``.gle`` scripts and compiled PDF outputs in the
``test_graphics_output`` directory. GLE source files are tracked in the repository
for reference, while PDFs are excluded via ``.gitignore``.
