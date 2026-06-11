"""Tests for fieldnotes.symbols."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from fieldnotes.symbols import resolve_symbol


class TestResolveSymbol:
    def test_top_level_function(self, tmp_path: Path):
        p = tmp_path / "x.py"
        p.write_text(
            dedent("""\
            import os

            def my_func():
                return 1


            def other():
                return 2
        """)
        )
        assert resolve_symbol(p, "my_func") == (3, 4)

    def test_async_function(self, tmp_path: Path):
        p = tmp_path / "x.py"
        p.write_text(
            dedent("""\
            async def fetch():
                return 1
        """)
        )
        assert resolve_symbol(p, "fetch") == (1, 2)

    def test_class(self, tmp_path: Path):
        p = tmp_path / "x.py"
        p.write_text(
            dedent("""\
            class Foo:
                x = 1

                def bar(self):
                    return self.x
        """)
        )
        result = resolve_symbol(p, "Foo")
        assert result is not None
        assert result[0] == 1

    def test_method_dotted(self, tmp_path: Path):
        p = tmp_path / "x.py"
        p.write_text(
            dedent("""\
            class Foo:
                def bar(self):
                    return 1
                def baz(self):
                    return 2
        """)
        )
        assert resolve_symbol(p, "Foo.bar") == (2, 3)
        assert resolve_symbol(p, "Foo.baz") == (4, 5)

    def test_missing_symbol(self, tmp_path: Path):
        p = tmp_path / "x.py"
        p.write_text("def a(): pass\n")
        assert resolve_symbol(p, "b") is None

    def test_missing_method_in_existing_class(self, tmp_path: Path):
        p = tmp_path / "x.py"
        p.write_text("class Foo:\n    def a(self): pass\n")
        assert resolve_symbol(p, "Foo.b") is None

    def test_non_python_file(self, tmp_path: Path):
        p = tmp_path / "x.js"
        p.write_text("function thing() {}\n")
        assert resolve_symbol(p, "thing") is None

    def test_syntax_error(self, tmp_path: Path):
        p = tmp_path / "x.py"
        p.write_text("def broken(:\n")
        assert resolve_symbol(p, "broken") is None

    def test_missing_file(self, tmp_path: Path):
        assert resolve_symbol(tmp_path / "nope.py", "anything") is None

    def test_handles_decorators(self, tmp_path: Path):
        # ast.FunctionDef.lineno is the def line, not the decorator line.
        p = tmp_path / "x.py"
        p.write_text(
            dedent("""\
            @decorator
            def my_func():
                return 1
        """)
        )
        # Either is acceptable; document the actual behavior.
        result = resolve_symbol(p, "my_func")
        assert result is not None
        # ast in Python 3.10+ reports lineno as the def line (decorators excluded).
        assert result[0] in (1, 2)
