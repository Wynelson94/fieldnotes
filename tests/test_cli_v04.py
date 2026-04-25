"""Tests for v0.4 CLI changes: range-pinned --refs syntax."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fieldnotes.cli import _parse_ref_spec, app
from fieldnotes.store import notes_dir, parse_note_file

runner = CliRunner()


class TestParseRefSpec:
    def test_no_lines(self):
        assert _parse_ref_spec("src/foo.py") == ("src/foo.py", None, None)

    def test_single_line(self):
        assert _parse_ref_spec("src/foo.py:42") == ("src/foo.py", [42, 42], None)

    def test_range(self):
        assert _parse_ref_spec("src/foo.py:12-84") == ("src/foo.py", [12, 84], None)

    def test_symbol(self):
        assert _parse_ref_spec("src/foo.py:my_func") == ("src/foo.py", None, "my_func")

    def test_dotted_symbol(self):
        assert _parse_ref_spec("src/foo.py:Cls.method") == (
            "src/foo.py",
            None,
            "Cls.method",
        )

    def test_garbage_suffix_falls_back_to_path(self):
        # Anything that isn't a valid range, line, or symbol → treat whole spec as path.
        assert _parse_ref_spec("src/foo.py:not a symbol!") == (
            "src/foo.py:not a symbol!",
            None,
            None,
        )


class TestAddWithRangeRefs:
    def test_pins_range(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text("\n".join(f"line {i}" for i in range(1, 21)) + "\n")

        result = runner.invoke(
            app,
            [
                "add",
                "--topic", "x",
                "--title", "T",
                "--body", "b",
                "--refs", "src/thing.py:3-5",
                "--repo", str(repo),
            ],
        )
        assert result.exit_code == 0, result.output
        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        ref = note.references[0]
        assert ref.path == "src/thing.py"
        assert ref.lines == [3, 5]
        assert ref.sha is not None
        assert len(ref.sha) == 64

    def test_pinned_range_survives_outside_edit(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text("\n".join(f"line {i}" for i in range(1, 21)) + "\n")
        runner.invoke(
            app,
            [
                "add",
                "--topic", "x", "--title", "T", "--body", "b",
                "--refs", "src/thing.py:3-5",
                "--repo", str(repo),
            ],
        )
        # Edit line 18 — outside the pinned range.
        text = src.read_text().splitlines()
        text[17] = "line 18 EDITED"
        src.write_text("\n".join(text) + "\n")
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert result.exit_code == 0
        assert "verified" in result.output, result.output

    def test_pinned_range_drifts_on_inside_edit(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text("\n".join(f"line {i}" for i in range(1, 21)) + "\n")
        runner.invoke(
            app,
            [
                "add",
                "--topic", "x", "--title", "T", "--body", "b",
                "--refs", "src/thing.py:3-5",
                "--repo", str(repo),
            ],
        )
        text = src.read_text().splitlines()
        text[3] = "line 4 EDITED"  # inside [3, 5]
        src.write_text("\n".join(text) + "\n")
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert "stale" in result.output.lower()

    def test_single_line_pin(self, repo: Path):
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text("line 1\nline 2\nline 3\n")
        runner.invoke(
            app,
            [
                "add",
                "--topic", "x", "--title", "T", "--body", "b",
                "--refs", "src/thing.py:2",
                "--repo", str(repo),
            ],
        )
        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        assert note.references[0].lines == [2, 2]
