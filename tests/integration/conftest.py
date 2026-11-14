"""Shared marks for integration tests that shell out to GLE."""

from __future__ import annotations

import sys

import pytest

# GLE 4.3.9 built on the macOS ARM CI runners aborts during the render pass of
# scripts containing a ``begin contour`` block, with no error output (banner
# "-C-R-" then a nonzero exit). Fitz-only scripts pass on the same runners, so
# the crash is in GLE's contour stage. The same scripts compile on Linux with
# the identically pinned GLE build. Non-strict: records XPASS if a later GLE
# or runner image fixes it.
darwin_gle_contour_crash = pytest.mark.xfail(
    sys.platform == "darwin",
    reason="GLE 4.3.9 crashes rendering begin-contour blocks on macOS ARM",
    strict=False,
)
