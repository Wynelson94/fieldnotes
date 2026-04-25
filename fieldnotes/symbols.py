"""Resolve a symbol name to a line range in a source file.

v0.5: Python only. Returns the line range (1-indexed, inclusive) of a top-level
function/class definition, or a method inside a class via dotted notation
('MyClass.my_method'). Returns None if the file isn't Python, can't be parsed,
or the symbol can't be found.
"""

from __future__ import annotations

import ast
from pathlib import Path

DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def resolve_symbol(path: Path, symbol: str) -> tuple[int, int] | None:
    """Find the [start_line, end_line] of `symbol` in `path`. None if not found."""
    if not path.exists() or not path.is_file():
        return None
    if path.suffix != ".py":
        return None
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None
    parts = symbol.split(".")
    return _walk(tree.body, parts)


def _walk(nodes: list[ast.stmt], parts: list[str]) -> tuple[int, int] | None:
    head, *tail = parts
    for node in nodes:
        if not isinstance(node, DEFINITION_NODES):
            continue
        if node.name != head:
            continue
        if not tail:
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            return (node.lineno, end)
        # Recurse into class body for dotted lookups.
        if isinstance(node, ast.ClassDef):
            found = _walk(node.body, tail)
            if found is not None:
                return found
            # Don't keep searching siblings if we matched the class but not the
            # nested name — that's almost certainly the right class with a typo
            # in the method name. Returning None here yields a clearer error.
            return None
        # Function bodies aren't searchable via dotted notation in v0.5.
        return None
    return None
