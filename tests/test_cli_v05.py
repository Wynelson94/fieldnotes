"""Tests for v0.5 CLI: symbol-pinned --refs."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.store import notes_dir, parse_note_file

runner = CliRunner()


class TestSymbolPinning:
    def test_pins_symbol(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text(
            dedent("""\
            def foo():
                return 1
            def bar():
                return 2
        """)
        )
        result = runner.invoke(
            app,
            [
                "add",
                "--topic",
                "x",
                "--title",
                "T",
                "--body",
                "b",
                "--refs",
                "src/thing.py:foo",
                "--repo",
                str(repo),
            ],
        )
        assert result.exit_code == 0, result.output
        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        ref = note.references[0]
        assert ref.symbol == "foo"
        assert ref.lines == [1, 2]
        assert ref.sha is not None

    def test_symbol_survives_reorder(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text(
            dedent("""\
            def foo():
                return 1
            def bar():
                return 2
        """)
        )
        runner.invoke(
            app,
            [
                "add",
                "--topic",
                "x",
                "--title",
                "T",
                "--body",
                "b",
                "--refs",
                "src/thing.py:foo",
                "--repo",
                str(repo),
            ],
        )
        # Reorder so foo is below bar — symbol moved, body unchanged.
        src.write_text(
            dedent("""\
            def bar():
                return 2
            def foo():
                return 1
        """)
        )
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert "verified" in result.output, result.output

    def test_symbol_drift_detected(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text("def foo():\n    return 1\n")
        runner.invoke(
            app,
            [
                "add",
                "--topic",
                "x",
                "--title",
                "T",
                "--body",
                "b",
                "--refs",
                "src/thing.py:foo",
                "--repo",
                str(repo),
            ],
        )
        # Edit foo's body.
        src.write_text("def foo():\n    return 99\n")
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert "stale" in result.output.lower()

    def test_unresolvable_symbol_warns(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text("def foo():\n    return 1\n")
        result = runner.invoke(
            app,
            [
                "add",
                "--topic",
                "x",
                "--title",
                "T",
                "--body",
                "b",
                "--refs",
                "src/thing.py:nonexistent",
                "--repo",
                str(repo),
            ],
        )
        # Still succeeds, but emits a warning to stderr (CliRunner mixes streams).
        assert result.exit_code == 0
        assert "could not resolve symbol" in result.output

    def test_dotted_symbol(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text(
            dedent("""\
            class Foo:
                def bar(self):
                    return 1
                def baz(self):
                    return 2
        """)
        )
        runner.invoke(
            app,
            [
                "add",
                "--topic",
                "x",
                "--title",
                "T",
                "--body",
                "b",
                "--refs",
                "src/thing.py:Foo.bar",
                "--repo",
                str(repo),
            ],
        )
        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        ref = note.references[0]
        assert ref.symbol == "Foo.bar"
        assert ref.lines == [2, 3]
