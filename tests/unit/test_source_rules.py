"""Rules about the library's source that are not about imports.

AGENTS.md ("Errors and warnings") states them; these tests read the source
with ``ast`` so a breach fails the suite rather than waiting for review.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path
from typing import List

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


def _warn_calls_without_stacklevel(source: str) -> List[int]:
    """Line numbers of ``warnings.warn`` calls in *source* with no ``stacklevel``.

    Follows the names the module binds: ``import warnings as _w`` and
    ``from warnings import warn`` are caught as well as the plain spelling.
    """
    tree = ast.parse(source)
    modules, functions = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "warnings"}
        elif isinstance(node, ast.ImportFrom) and node.module == "warnings":
            functions |= {a.asname or a.name for a in node.names if a.name == "warn"}
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "warn"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in modules
            )
            or (isinstance(node.func, ast.Name) and node.func.id in functions)
        )
        and not any(k.arg == "stacklevel" for k in node.keywords)
    ]


def test_every_library_warning_has_a_stacklevel():
    # A warning points at the caller's line, not at gleplot's. Presence only:
    # whether the level is right is what the attribution tests below check.
    found = [
        f"{path.relative_to(PACKAGE_ROOT.parent)}:{line}"
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        for line in _warn_calls_without_stacklevel(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_stacklevel_check_follows_import_aliases():
    source = (
        "import warnings\n"
        "import warnings as _w\n"
        "from warnings import warn as w\n"
        "warnings.warn('a')\n"
        "_w.warn('b', stacklevel=2)\n"
        "_w.warn('c')\n"
        "w('d')\n"
        "logger.warn('not the warnings module')\n"
    )
    assert sorted(_warn_calls_without_stacklevel(source)) == [4, 6, 7]


# One warning per public entry point, called the two ways a script calls it:
# as an ``Axes`` method and through the module-level function that forwards to
# it, one frame deeper. Each must be attributed to this file.
_X, _Y = np.array([1.0, 2.0]), np.array([1.0, 2.0])
_ENTRY_POINTS = {
    "plot": lambda m: m.plot(_X, _Y, linestyle="none", drawstyle="steps-mid"),
    "bar": lambda m: m.bar(_X, _Y, align="edge"),
    "hist": lambda m: m.hist(_Y, density=True),
    "fill_between": lambda m: m.fill_between(_X, _Y, color="r", facecolor="b"),
    "errorbar": lambda m: m.errorbar(_X, _Y, yerr=0.1, color="notacolor"),
}


@pytest.mark.parametrize("via", ["axes", "module"])
@pytest.mark.parametrize("name", sorted(_ENTRY_POINTS))
def test_a_warning_is_attributed_to_the_calling_script(name: str, via: str):
    glp.close()
    target = glp.subplots()[1] if via == "axes" else glp
    try:
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            _ENTRY_POINTS[name](target)
    finally:
        glp.close()
    assert record, f"{name} emitted no warning to attribute"
    assert {w.filename for w in record} == {__file__}
