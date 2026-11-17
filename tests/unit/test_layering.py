"""The package's import structure, checked statically.

gleplot's modules form layers (see AGENTS.md, "Invariants"). Nothing at
runtime stops a new import from quietly closing a cycle or pulling the object
model into the parser's syntax layer, and the usual way to make such an
import "work" is to hide it inside a function. These tests read the source
with ``ast`` so both the module-level graph and the function-level escapes
are held to an explicit list.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

import gleplot

PACKAGE_ROOT = Path(gleplot.__file__).parent
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

#: Parser modules that must depend on the standard library and each other
#: only. ``recognizer`` (the bridge to the object model) and ``tables``
#: (which re-exports the colour and marker tables) are deliberately absent.
SYNTAX_LAYER = {
    "gleplot.parser.lexer",
    "gleplot.parser.syntax",
    "gleplot.parser.expr",
    "gleplot.parser.units",
    "gleplot.parser.metadata",
    "gleplot.parser.report",
}

#: Function-level imports of gleplot modules that are allowed to exist, as
#: ``(importer, imported)``. Each one is deliberate:
#:
#: * ``open_gle`` loads the recognizer on first use, so ``import gleplot``
#:   does not pay for the largest module in the package.
#: * ``gleplot.parser`` exposes ``recognizer``/``report`` lazily (PEP 562)
#:   for the same reason.
#: * ``Figure.to_dict`` reads ``gleplot.__version__``; the package root
#:   imports ``figure``, so this one is a real cycle and has to stay deferred.
#:
#: Adding an entry here needs the same kind of reason. "It fixes a circular
#: import" means two modules are in the wrong layers.
ALLOWED_DEFERRED: Set[Tuple[str, str]] = {
    ("gleplot", "gleplot.parser.recognizer"),
    ("gleplot.parser", "gleplot.parser.recognizer"),
    ("gleplot.parser", "gleplot.parser.report"),
    ("gleplot.figure", "gleplot"),
}


#: Function-level imports of third-party packages that are allowed to exist,
#: as ``(importer, top-level package)``:
#:
#: * ``Figure.view`` displays the image inline when it runs under IPython. It
#:   is the only place that touches IPython, and IPython is never a dependency.
ALLOWED_DEFERRED_THIRD_PARTY: Set[Tuple[str, str]] = {
    ("gleplot.figure", "IPython"),
}

#: Standard-library modules newer than some supported Python, so absent from
#: ``sys.stdlib_module_names`` on older interpreters. ``series`` imports
#: ``annotationlib`` (3.14+) only under a version guard.
NEWER_STDLIB = {"annotationlib"}

needs_stdlib_names = pytest.mark.skipif(
    sys.version_info < (3, 10), reason="sys.stdlib_module_names is 3.10+"
)


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE_ROOT.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _modules() -> Dict[str, Path]:
    return {_module_name(p): p for p in sorted(PACKAGE_ROOT.rglob("*.py"))}


def _resolve(
    importer: str, is_package: bool, node: ast.AST, known: Set[str]
) -> List[str]:
    """Absolute names of the gleplot modules an import statement refers to."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    assert isinstance(node, ast.ImportFrom)
    if node.level == 0:
        base = node.module or ""
    else:
        package = importer.split(".") if is_package else importer.split(".")[:-1]
        package = package[: len(package) - (node.level - 1)]
        base = ".".join(package + ([node.module] if node.module else []))
    # ``from pkg import name`` names a submodule when there is one, and an
    # attribute of ``pkg`` otherwise.
    return [
        f"{base}.{alias.name}" if f"{base}.{alias.name}" in known else base
        for alias in node.names
    ]


def _imports(name: str, path: Path, known: Set[str]):
    """``(module_level, deferred)`` sets of gleplot modules ``name`` imports."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    is_package = path.name == "__init__.py"
    top: Set[str] = set()
    deferred: Set[str] = set()

    def visit(node: ast.AST, nested: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                for target in _resolve(name, is_package, child, known):
                    if target in known and target != name:
                        (deferred if nested else top).add(target)
            is_scope = isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            )
            visit(child, nested or is_scope)

    visit(tree, False)
    return top, deferred - top


def _third_party_imports(path: Path):
    """``(module_level, deferred)`` top-level third-party packages ``path`` imports."""
    stdlib = set(sys.stdlib_module_names) | NEWER_STDLIB
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top: Set[str] = set()
    deferred: Set[str] = set()

    def visit(node: ast.AST, nested: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Import):
                roots = [alias.name.split(".")[0] for alias in child.names]
            elif isinstance(child, ast.ImportFrom) and child.level == 0:
                roots = [(child.module or "").split(".")[0]]
            else:
                roots = []
            for root in roots:
                if root not in stdlib and root != "gleplot":
                    (deferred if nested else top).add(root)
            is_scope = isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            )
            visit(child, nested or is_scope)

    visit(tree, False)
    return top, deferred - top


def _runtime_dependencies() -> Set[str]:
    """Import names of ``[project].dependencies`` in ``pyproject.toml``.

    Read with a regular expression because ``tomllib`` is 3.11+. A
    distribution whose import name differs from its project name would need
    mapping here.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
    assert block, f"no [project].dependencies list in {PYPROJECT}"
    specs = re.findall(r"[\"']([^\"']+)[\"']", block.group(1))
    names = (re.match(r"[A-Za-z0-9_.-]+", spec) for spec in specs)
    return {m.group(0).replace("-", "_") for m in names if m}


def _graph():
    modules = _modules()
    known = set(modules)
    return {name: _imports(name, path, known) for name, path in modules.items()}


def _find_cycle(edges: Dict[str, Set[str]]) -> List[str]:
    """A module-level import cycle as a list of names, or ``[]``."""
    state: Dict[str, int] = {}
    stack: List[str] = []

    def walk(node: str) -> List[str]:
        state[node] = 1
        stack.append(node)
        for nxt in sorted(edges[node]):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt) :] + [nxt]
            if nxt not in state:
                found = walk(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return []

    for start in sorted(edges):
        if start not in state:
            found = walk(start)
            if found:
                return found
    return []


def test_module_level_imports_are_acyclic():
    """No cycle among module-level imports.

    A submodule importing its own package root is ignored: Python always
    initialises the parent package first, so that edge is implicit in every
    import and carries no layering information.
    """
    edges = {}
    for name, (top, _deferred) in _graph().items():
        edges[name] = {t for t in top if not name.startswith(t + ".")}
    cycle = _find_cycle(edges)
    assert not cycle, "module-level import cycle: " + " -> ".join(cycle)


def test_deferred_imports_are_the_documented_ones():
    """A function-level gleplot import must be on the explicit list."""
    found = {
        (name, target)
        for name, (_top, deferred) in _graph().items()
        for target in deferred
    }
    unexpected = sorted(found - ALLOWED_DEFERRED)
    assert not unexpected, (
        "function-level imports of gleplot modules that are not in "
        f"ALLOWED_DEFERRED: {unexpected}"
    )
    stale = sorted(ALLOWED_DEFERRED - found)
    assert not stale, f"ALLOWED_DEFERRED entries that no longer exist: {stale}"


def test_parser_syntax_layer_is_stdlib_only():
    """The syntax layer imports the standard library and itself, nothing else."""
    modules = _modules()
    for name in sorted(SYNTAX_LAYER):
        path = modules[name]
        top, deferred = _imports(name, path, set(modules))
        internal = (top | deferred) - SYNTAX_LAYER - {"gleplot.parser", "gleplot"}
        assert not internal, f"{name} imports {sorted(internal)}"

        if sys.version_info >= (3, 10):  # sys.stdlib_module_names is 3.10+
            third_party = set().union(*_third_party_imports(path))
            assert not third_party, f"{name} imports {sorted(third_party)}"


@needs_stdlib_names
def test_module_level_third_party_imports_are_the_runtime_dependencies():
    """Only the declared runtime dependencies are imported at module level."""
    found: Dict[str, Set[str]] = {}
    for name, path in _modules().items():
        for root in _third_party_imports(path)[0]:
            found.setdefault(root, set()).add(name)
    declared = _runtime_dependencies()
    undeclared = {root: sorted(found[root]) for root in sorted(set(found) - declared)}
    assert not undeclared, (
        "module-level imports of packages that are not runtime dependencies "
        f"in pyproject.toml: {undeclared}"
    )
    unused = sorted(declared - set(found))
    assert not unused, f"runtime dependencies that nothing imports: {unused}"


@needs_stdlib_names
def test_deferred_third_party_imports_are_the_documented_ones():
    """A function-level third-party import must be on the explicit list."""
    found = {
        (name, root)
        for name, path in _modules().items()
        for root in _third_party_imports(path)[1]
    }
    unexpected = sorted(found - ALLOWED_DEFERRED_THIRD_PARTY)
    assert not unexpected, (
        "function-level imports of third-party packages that are not in "
        f"ALLOWED_DEFERRED_THIRD_PARTY: {unexpected}"
    )
    stale = sorted(ALLOWED_DEFERRED_THIRD_PARTY - found)
    assert (
        not stale
    ), f"ALLOWED_DEFERRED_THIRD_PARTY entries that no longer exist: {stale}"


def test_import_does_not_load_ipython():
    """``import gleplot`` leaves IPython unloaded, even through a dependency.

    The static checks above see only gleplot's own source.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(PACKAGE_ROOT.parent), env.get("PYTHONPATH")])
    )
    result = subprocess.run(
        [sys.executable, "-c", "import sys, gleplot; print('IPython' in sys.modules)"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"
