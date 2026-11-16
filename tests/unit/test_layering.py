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
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import gleplot

PACKAGE_ROOT = Path(gleplot.__file__).parent

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
    stdlib = set(sys.stdlib_module_names) if sys.version_info >= (3, 10) else None
    for name in sorted(SYNTAX_LAYER):
        path = modules[name]
        top, deferred = _imports(name, path, set(modules))
        internal = (top | deferred) - SYNTAX_LAYER - {"gleplot.parser", "gleplot"}
        assert not internal, f"{name} imports {sorted(internal)}"

        if stdlib is None:  # sys.stdlib_module_names is 3.10+
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots = [(node.module or "").split(".")[0]]
            else:
                continue
            third_party = [r for r in roots if r not in stdlib and r != "gleplot"]
            assert not third_party, f"{name} imports {third_party}"
