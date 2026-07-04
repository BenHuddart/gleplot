"""Shared fixtures for the gleplot GUI test suite.

These tests wrap *real* ``gleplot.Figure``/``Axes`` objects, and gleplot keeps
two pieces of process-global state that can otherwise leak between tests and
make the outcome depend on collection/run order:

* ``gleplot.axes._global_data_file_counter`` -- a module-global counter used to
  name auto-generated ``data_<N>.dat`` sidecars when a figure has no explicit
  ``data_prefix``. Left un-reset, its value depends on how many series every
  earlier test created, so any assertion touching a generated data-file name
  (or GLE output that embeds one) becomes order-sensitive.
* ``gleplot._current_figure`` -- the pyplot-style "current figure" pointer set
  by ``gleplot.figure()`` and cleared by ``gleplot.close()``. A test that
  forgets to ``close()`` leaves a stale current figure visible to the next
  test's ``gcf()``.

The autouse fixture below resets both around every GUI test so each starts from
a clean, deterministic global state regardless of run order. This is the proper
fix for the observed cross-file order dependence (a failure that migrated
between ``test_panels.py`` and ``test_data_panel.py`` depending on order): it
addresses the shared state at the source rather than pinning a test order.
"""

from __future__ import annotations

import pytest

import gleplot
from gleplot import axes as _gleplot_axes


@pytest.fixture(autouse=True)
def _reset_gleplot_global_state():
    """Reset gleplot's process-global state before and after every GUI test."""
    _gleplot_axes._global_data_file_counter = 0
    gleplot.close()  # clear any lingering "current figure"
    try:
        yield
    finally:
        _gleplot_axes._global_data_file_counter = 0
        gleplot.close()
