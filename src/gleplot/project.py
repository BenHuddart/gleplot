"""JSON project-file persistence for gleplot figures.

This module provides the on-disk project format used by the gleplot GUI
editor. A project file is a UTF-8 JSON document holding the lossless
serialization of a :class:`~gleplot.figure.Figure` (see
:meth:`~gleplot.figure.Figure.to_dict`). Files are written with
``indent=2`` for human readability and clean diffs, and use the ``.glep``
extension by convention (not enforced).
"""

import json
from pathlib import Path
from typing import Union

from .figure import Figure

__all__ = ['save_project', 'load_project']


def save_project(figure: Figure, path: Union[str, Path]) -> Path:
    """Save a figure to a JSON project file.

    Parameters
    ----------
    figure : Figure
        The figure to serialize.
    path : str or pathlib.Path
        Destination file path. The ``.glep`` extension is conventional but
        not required.

    Returns
    -------
    pathlib.Path
        The path the project was written to.

    Notes
    -----
    The file is written as UTF-8 JSON with ``indent=2`` and stable key order
    (``sort_keys=False`` preserves the deterministic order emitted by
    :meth:`Figure.to_dict`) so that project files diff cleanly and round-trip
    losslessly.
    """
    output_path = Path(path)
    payload = figure.to_dict()
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    output_path.write_text(text, encoding='utf-8')
    return output_path


def load_project(path: Union[str, Path]) -> Figure:
    """Load a figure from a JSON project file.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to a project file written by :func:`save_project`.

    Returns
    -------
    Figure
        The reconstructed figure.

    Raises
    ------
    ValueError
        If the file does not contain a recognized gleplot project envelope
        or targets an unsupported version (raised by
        :meth:`Figure.from_dict`).
    """
    input_path = Path(path)
    text = input_path.read_text(encoding='utf-8')
    payload = json.loads(text)
    return Figure.from_dict(payload)
