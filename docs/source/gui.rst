GUI Editor
==========

gleplot ships an optional desktop editor built on PySide6 for building figures
interactively -- load data, map columns to series, style everything from
dockable property panels, arrange subplots, and export -- all with a live
preview that recompiles as you edit.

Downloads
---------

Two ways to get the editor:

- **Prebuilt desktop app** (no Python needed) -- download the Windows
  ``.exe`` installer or the macOS (Apple silicon / arm64) ``.dmg`` from the
  `GitHub Releases page <https://github.com/benhuddart/gleplot/releases>`_.
  The macOS build is unsigned, so the first launch needs a right-click
  |menu| **Open** (or ``xattr -dr com.apple.quarantine`` on the ``.app``).

- **From pip** -- install into a Python environment:

  .. code-block:: bash

     pip install "gleplot[gui]"

Either way, GLE 4.3+ is a separate prerequisite (see below).

The pip extra adds ``PySide6>=6.5`` on top of gleplot's core dependencies.
Importing the base ``gleplot`` package never pulls in Qt -- only
``gleplot.gui`` does -- so scripts that only generate GLE output are
unaffected either way.

GLE prerequisite
----------------

The editor needs **GLE 4.3 or newer** for the live preview and for exporting
any compiled format (PDF/PNG/EPS/SVG/JPG). GLE is a separate program: install
it from the `GLE releases page
<https://github.com/vlabella/GLE/releases/latest>`_ and make it discoverable:
point the editor at it via **Tools ▸ GLE Setup…**, put it on ``PATH``, or set
the ``GLE_PATH`` environment variable. The status bar shows
the detected GLE path or ``GLE: not found``. Without GLE the object-model
editing still works (load data, add and style series, arrange subplots, Save
and Open native ``.gle`` files) -- only the live preview and compiled exports
are unavailable; the raw ``.gle``-script export still works.

Launching
---------

.. code-block:: bash

   gleplot-gui

This is a console-script entry point (``gleplot.gui.app:main``) that opens
the main editor window and runs the Qt event loop.

What it provides
-----------------

- A central **live preview** that recompiles the figure via GLE as you edit,
  debounced so rapid edits don't trigger a compile per keystroke. It renders
  as a vector **SVG** by default, with an automatic, sticky fallback to PNG
  for the rest of the session if SVG output isn't usable (a **View ▸ Vector
  preview (SVG)** toggle switches between the two manually).
- **On-canvas text annotations**: add, drag, double-click-edit, and delete
  free-form text labels directly on the preview, in sync both ways with a
  dedicated **Texts** tab in the Properties dock.
- A **Data** dock for loading delimited data files (CSV/``.dat``/``.txt``)
  and creating series by mapping columns, either importing the data or
  referencing the file in place. Generated ``.dat`` sidecars carry a named
  header row (derived from each series' label) instead of anonymous column
  numbers.
- A **Properties** dock with **Layout**, **Figure**, **Axes**, **Series**,
  and **Texts** tabs for point-and-click styling, subplot arrangement, and
  annotation editing.
- An **Output** dock listing structured compile errors with line/column
  information when GLE reports it, plus any recovery warnings raised when a
  ``.gle`` file is opened.
- **Native ``.gle`` files** via File |menu| Save / Open: Save writes a plain
  GLE script (``Figure.savefig_gle``, with imported data as named ``.dat``
  sidecars) and Open parses it back into the editor
  (``gleplot.parser.recognizer.parse_gle_figure``), tolerantly preserving any
  unrecognized content as raw GLE (a read-only **Raw GLE** tab).
- An **export dialog** producing PDF, PNG, EPS, SVG, JPG, or a raw ``.gle``
  script, optionally bundled into a folder with its data files. Exports
  always compile the figure exactly as saved, independent of anything the
  live preview substitutes for on-screen rendering.
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
