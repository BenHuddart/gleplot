"""Rules about the library's source that are not about imports.

AGENTS.md ("Errors and warnings") states them; these tests read the source
with ``ast`` so a breach fails the suite rather than waiting for review.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path
from typing import List
from unittest import mock

import numpy as np
import pytest

import gleplot
import gleplot as glp

PACKAGE_ROOT = Path(gleplot.__file__).parent


def _print_call_lines(source: str) -> List[int]:
    """Line numbers of every call to the builtin ``print`` in *source*."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def test_library_code_does_not_print():
    # Results go through return values, exceptions and warnings; output a
    # user opts into goes through the ``gleplot`` logger.
    found = [
        f"{path.relative_to(PACKAGE_ROOT.parent)}:{line}"
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        for line in _print_call_lines(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_print_check_finds_calls_at_any_depth():
    source = "def f(x):\n    if x:\n        print(x)\n\n\nprint('top')\n"
    assert sorted(_print_call_lines(source)) == [3, 6]


_WARN = {"warn", "warn_explicit"}


def _direct_warn_calls(source: str) -> List[int]:
    """Line numbers of every ``warnings.warn``/``warn_explicit`` call in *source*.

    Follows the names the module binds: ``import warnings as _w`` and
    ``from warnings import warn`` are caught as well as the plain spelling.
    """
    tree = ast.parse(source)
    modules, functions = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "warnings"}
        elif isinstance(node, ast.ImportFrom) and node.module == "warnings":
            functions |= {a.asname or a.name for a in node.names if a.name in _WARN}
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _WARN
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in modules
            )
            or (isinstance(node.func, ast.Name) and node.func.id in functions)
        )
    ]


def test_library_warnings_go_through_warn_external():
    # A warning points at the caller's line, not at gleplot's. Any fixed
    # ``stacklevel`` is wrong for some call path (``glp.*`` adds a frame), so
    # only ``_warn.warn_external`` calls ``warnings.warn``.
    found = [
        f"{path.relative_to(PACKAGE_ROOT.parent)}:{line}"
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if path != PACKAGE_ROOT / "_warn.py"
        for line in _direct_warn_calls(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_warn_check_follows_import_aliases():
    source = (
        "import warnings\n"
        "import warnings as _w\n"
        "from warnings import warn as w\n"
        "warnings.warn('a')\n"
        "_w.warn('b', stacklevel=2)\n"
        "w('c')\n"
        "warnings.warn_explicit('d', UserWarning, 'f.py', 1)\n"
        "logger.warn('not the warnings module')\n"
    )
    assert sorted(_direct_warn_calls(source)) == [4, 5, 6, 7]


# One warning per public entry point, called the two ways a script calls it:
# as an ``Axes`` method and through the module-level function that forwards to
# it, one frame deeper. Each must be attributed to this file.
_X, _Y = np.array([1.0, 2.0]), np.array([1.0, 2.0])
_ENTRY_POINTS = {
    "plot": lambda m: m.plot(_X, _Y, linestyle="none", drawstyle="steps-mid"),
    "bar": lambda m: m.bar(_X, _Y, align="edge"),
    "hist": lambda m: m.hist(_Y, density=True),
    "fill_between": lambda m: m.fill_between(_X, _Y, color="r", facecolor="b"),
    "fill_betweenx": lambda m: m.fill_betweenx(_Y, _X, step="pre"),
    "stackplot": lambda m: m.stackplot(_X, _Y, hatch="//"),
    "hlines": lambda m: m.hlines(_Y, 0, 1, alpha=0.5),
    "vlines": lambda m: m.vlines(_X, 0, 1, linestyles=[(0, (5, 5))]),
    "errorbar": lambda m: m.errorbar(_X, _Y, yerr=0.1, color="notacolor"),
    "step": lambda m: m.step(_X, _Y, "r-"),
    "stem": lambda m: m.stem(_X, _Y, orientation="horizontal"),
    "text": lambda m: m.text(1.0, 1.0, "t", ha="justify"),
    "annotate": lambda m: m.annotate("a", (1.0, 1.0), annotation_clip=True),
    "annotate arrow": lambda m: m.annotate(
        "a", (1.0, 1.0), xytext=(2.0, 2.0), arrowprops={"arrowstyle": "fancy"}
    ),
    "legend": lambda m: m.legend(loc="nowhere"),
    "bar aliases": lambda m: m.bar(_X, _Y, color="r", facecolor="b"),
    "bar edge": lambda m: m.bar(_X, _Y, linestyle="zigzag"),
}


@pytest.mark.parametrize("via", ["axes", "module"])
@pytest.mark.parametrize("name", sorted(_ENTRY_POINTS))
def test_a_warning_is_attributed_to_the_calling_script(name: str, via: str):
    glp.close()
    try:
        target = glp.subplots()[1] if via == "axes" else glp
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            _ENTRY_POINTS[name](target)
    finally:
        glp.close()
    assert record, f"{name} emitted no warning to attribute"
    assert {w.filename for w in record} == {__file__}


# Entry points with no module-level function: reached as methods only, some
# through a wrapper (the twin axes, the broken axes) that adds a frame.
_METHOD_ENTRY_POINTS = {
    "grid": lambda fig, ax: ax.grid(True, which="minor"),
    "line_from_file": lambda fig, ax: ax.line_from_file(
        "d.dat", 1, 2, linestyle="none", drawstyle="steps-mid"
    ),
    "twiny line_from_file": lambda fig, ax: ax.twiny().line_from_file(
        "d.dat", 1, 2, linestyle="none", drawstyle="steps-mid"
    ),
    "broken text": lambda fig, ax: fig.add_broken_xaxes([(0, 1), (2, 3)]).text(
        1.5, 1.0, "t"
    ),
    "broken text alignment": lambda fig, ax: fig.add_broken_xaxes(
        [(0, 1), (2, 3)]
    ).text(0.5, 1.0, "t", ha="justify"),
    "broken annotate": lambda fig, ax: fig.add_broken_xaxes([(0, 1), (2, 3)]).annotate(
        "a", (2.5, 1.0), xytext=(0.5, 1.0), arrowprops={}
    ),
}


@pytest.mark.parametrize("name", sorted(_METHOD_ENTRY_POINTS))
def test_a_method_only_warning_is_attributed_to_the_calling_script(name: str):
    glp.close()
    try:
        fig, ax = glp.subplots()
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            _METHOD_ENTRY_POINTS[name](fig, ax)
    finally:
        glp.close()
    assert record, f"{name} emitted no warning to attribute"
    assert {w.filename for w in record} == {__file__}


@pytest.mark.parametrize("via", ["figure", "module"])
def test_a_savefig_warning_is_attributed_to_the_calling_script(
    via: str, tmp_path: Path
):
    # A semi-transparent figure in a font Cairo rejects warns at compile time;
    # the stub compiler stands in for GLE, which is never run.
    glp.close()
    try:
        fig = glp.figure(style=glp.GLEStyleConfig(font="rm"))
        fig.compiler = mock.Mock()
        fig.add_subplot(111).fill_between(_X, _Y, _Y + 1, alpha=0.5)
        target = fig if via == "figure" else glp
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            target.savefig(str(tmp_path / "out.pdf"))
    finally:
        glp.close()
    assert record, "savefig emitted no warning to attribute"
    assert {w.filename for w in record} == {__file__}


def test_a_gle_discovery_warning_is_attributed_to_the_calling_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    from gleplot import compiler

    monkeypatch.setenv("GLE_PATH", str(tmp_path / "missing-gle"))
    compiler.set_gle_path_override(str(tmp_path / "missing"))
    try:
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            compiler.find_gle()
    finally:
        compiler.set_gle_path_override(None)
    assert len(record) == 2, [str(w.message) for w in record]
    assert {w.filename for w in record} == {__file__}
