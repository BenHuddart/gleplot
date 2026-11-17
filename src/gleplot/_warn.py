"""Warnings attributed to the user's line rather than to gleplot's."""

from __future__ import annotations

import sys
import warnings
from types import FrameType
from typing import Optional, Type, Union


def warn_external(
    message: Union[str, Warning], category: Type[Warning] = UserWarning
) -> None:
    """``warnings.warn`` at the first calling frame outside the gleplot package.

    A fixed ``stacklevel`` is right for one call path only. The same warning is
    reached from ``Figure.savefig``, ``glp.savefig`` and ``Figure.view`` at
    different depths, and every ``glp.*`` function adds a frame in front of the
    ``Axes`` method it forwards to.
    """
    frame: Optional[FrameType] = sys._getframe(1)
    stacklevel = 2
    while frame is not None:
        module = frame.f_globals.get("__name__", "")
        if module != "gleplot" and not module.startswith("gleplot."):
            break
        frame = frame.f_back
        stacklevel += 1
    warnings.warn(message, category, stacklevel=stacklevel)
