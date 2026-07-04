"""Backwards-compatible shim for :mod:`gleplot.gui.data.loader`.

.. deprecated::
    The pure-Python (no Qt) delimited data file loader has moved to
    :mod:`gleplot.dataio` as part of the GLE-parsing project (Track A3),
    since it is now also used by the core ``.gle`` parser, which must not
    depend on :mod:`gleplot.gui`. This module remains as a thin
    re-export so existing imports of ``gleplot.gui.data.loader`` (and
    ``gleplot.gui.data``) keep working unchanged. New code should import
    from :mod:`gleplot.dataio` directly.
"""

from __future__ import annotations

from gleplot.dataio import DataTable, load_data_file

__all__ = ["DataTable", "load_data_file"]
