"""Rules about the library's source that are not about imports.

AGENTS.md ("Errors and warnings") states them; these tests read the source
with ``ast`` so a breach fails the suite rather than waiting for review.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List

import gleplot

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
