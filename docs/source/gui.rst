GUI Editor
==========

gleplot ships an optional desktop editor built on PySide6 for building figures
interactively -- load data, map columns to series, style everything from
dockable property panels, arrange subplots, and export -- all with a live
preview that recompiles as you edit.

Installation
------------

.. code-block:: bash

   pip install "gleplot[gui]"

This adds ``PySide6>=6.5`` on top of gleplot's core dependencies. Importing
the base ``gleplot`` package never pulls in Qt -- only ``gleplot.gui`` does --
so scripts that only generate GLE output are unaffected either way.

Launching
---------

.. code-block:: bash

   gleplot-gui

This is a console-script entry point (``gleplot.gui.app:main``) that opens
the main editor window and runs the Qt event loop.

What it provides
-----------------

- A central **live preview** that recompiles the figure to PNG via GLE as you
  edit, debounced so rapid edits don't trigger a compile per keystroke.
- A **Data** dock for loading delimited data files (CSV/``.dat``/``.txt``)
  and creating series by mapping columns, either importing the data or
  referencing the file in place.
- A **Properties** dock with **Layout**, **Figure**, **Axes**, and **Series**
  tabs for point-and-click styling and subplot arrangement.
- An **Output** dock listing structured compile errors with line/column
  information when GLE reports it, plus any recovery warnings raised when a
  ``.gle`` file is opened.
- **Native ``.gle`` files** via File |menu| Save / Open: Save writes a plain
  GLE script (``Figure.savefig_gle``, with imported data as ``.dat``
  sidecars) and Open parses it back into the editor
  (``gleplot.parser.recognizer.parse_gle_figure``), tolerantly preserving any
  unrecognized content as raw GLE (a read-only **Raw GLE** tab).
- An **export dialog** producing PDF, PNG, EPS, SVG, JPG, or a raw ``.gle``
  script, optionally bundled into a folder with its data files.
- **Undo/redo** and a read-only preview mode for ``.gle`` files that use GLE
  programming constructs.

.. |menu| unicode:: U+25B8 .. black right-pointing small triangle

For a full walkthrough -- loading data, picking columns, styling series,
arranging subplots, saving a figure, and exporting -- along with the native
``.gle`` format (open-time normalizations and raw-GLE preservation),
GLE-discovery behavior, and current limitations, see the
`GUI Editor Guide
<https://github.com/benhuddart/gleplot/blob/main/docs/guides/GUI_EDITOR.md>`_.
A ready-to-open example figure lives in ``examples/gui/`` in the source
repository.
