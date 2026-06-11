"""Resolve a symbol name to a line range in a source file.

Python (v0.5): AST-based. Top-level function/class, or a method inside a
class via dotted notation ('MyClass.my_method').

TypeScript/JavaScript and SQL (v0.10): regex + block-scan based — no parser
dependency, top-level declarations only, identifier-style names. Imperfect by
design: a wrong range surfaces as stale on the next verify, never silently.

Returns the line range (1-indexed, inclusive), or None if the file type is
unsupported, the file can't be parsed, or the symbol can't be found.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

TS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
SQL_SUFFIXES = {".sql"}
SYMBOL_SUFFIXES = {".py"} | TS_SUFFIXES | SQL_SUFFIXES


def resolve_symbol(path: Path, symbol: str) -> tuple[int, int] | None:
    """Find the [start_line, end_line] of `symbol` in `path`. None if not found."""
    if not path.exists() or not path.is_file():
        return None
    suffix = path.suffix.lower()
    if suffix == ".py":
        return _resolve_python(path, symbol)
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if suffix in TS_SUFFIXES:
        return _resolve_ts(lines, symbol)
    if suffix in SQL_SUFFIXES:
        return _resolve_sql(lines, symbol)
    return None


# ── Python ──────────────────────────────────────────────────────────────────


def _resolve_python(path: Path, symbol: str) -> tuple[int, int] | None:
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


# ── TypeScript / JavaScript ─────────────────────────────────────────────────


def _ts_decl_patterns(name: str) -> list[re.Pattern[str]]:
    n = re.escape(name)
    return [
        re.compile(p)
        for p in (
            rf"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?function\s*\*?\s+{n}\s*[(<]",
            rf"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?class\s+{n}\b",
            rf"^\s*(?:export\s+)?(?:declare\s+)?(?:const|let|var)\s+{n}\s*[:=]",
            rf"^\s*(?:export\s+)?(?:declare\s+)?interface\s+{n}\b",
            rf"^\s*(?:export\s+)?type\s+{n}\s*[=<]",
            rf"^\s*(?:export\s+)?(?:declare\s+)?(?:const\s+)?enum\s+{n}\b",
        )
    ]


def _strip_ts_noise(line: str) -> str:
    """Drop string literals and line comments so their braces don't count.

    Single-line only — a template literal spanning lines with braces inside
    can misbalance the scan. The pin then reads as stale, which is the safe
    failure mode.
    """
    line = re.sub(r"'(?:\\.|[^'\\])*'", "''", line)
    line = re.sub(r'"(?:\\.|[^"\\])*"', '""', line)
    line = re.sub(r"`(?:\\.|[^`\\])*`", "``", line)
    return re.sub(r"//.*", "", line)


def _resolve_ts(lines: list[str], symbol: str) -> tuple[int, int] | None:
    patterns = _ts_decl_patterns(symbol)
    for i, line in enumerate(lines):
        if any(p.search(line) for p in patterns):
            return (i + 1, _ts_block_end(lines, i) + 1)
    return None


def _ts_block_end(lines: list[str], start_idx: int) -> int:
    """Index of the line closing the block opened at `start_idx`.

    Brace-balance from the declaration; a braceless statement ends at the
    first `;`-terminated line.
    """
    depth = 0
    opened = False
    for j in range(start_idx, len(lines)):
        s = _strip_ts_noise(lines[j])
        for ch in s:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            return j
        if not opened and s.rstrip().endswith(";"):
            return j
    return len(lines) - 1


# ── SQL ─────────────────────────────────────────────────────────────────────

_SQL_CREATE = re.compile(
    r"^\s*create\s+(?:or\s+replace\s+)?(?:unique\s+)?"
    r"(?:table|policy|function|trigger|view|materialized\s+view|index)\s+"
    r"(?:concurrently\s+)?(?:if\s+not\s+exists\s+)?"
    r'(?P<name>[A-Za-z0-9_."]+)',
    re.IGNORECASE,
)


def _sql_name_matches(raw: str, symbol: str) -> bool:
    """`public.contacts` and `"contacts"` both answer to the symbol `contacts`."""
    last = raw.split(".")[-1].strip('"')
    return last.lower() == symbol.lower()


def _resolve_sql(lines: list[str], symbol: str) -> tuple[int, int] | None:
    for i, line in enumerate(lines):
        m = _SQL_CREATE.match(line)
        if m and _sql_name_matches(m.group("name"), symbol):
            return (i + 1, _sql_block_end(lines, i) + 1)
    return None


def _sql_block_end(lines: list[str], start_idx: int) -> int:
    """Index of the line carrying the statement's terminating `;`.

    `$$`-quoted bodies are skipped so a function's internal semicolons don't
    end the block early. Tagged dollar-quotes ($body$) aren't handled in v1.
    """
    in_dollar = False
    for j in range(start_idx, len(lines)):
        line = lines[j]
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
            if not in_dollar and ";" in line.split("$$")[-1]:
                return j
            continue
        if in_dollar:
            continue
        s = re.sub(r"'(?:[^']|'')*'", "''", line)
        s = re.sub(r"--.*", "", s)
        if ";" in s:
            return j
    return len(lines) - 1
