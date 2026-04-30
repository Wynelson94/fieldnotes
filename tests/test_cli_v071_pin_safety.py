"""Tests for v0.7.1 pin-safety bugfixes:
- Symbol pin on non-Python file degrades to whole-file (no orphan symbol field).
- Directory ref is rejected with a clear warning instead of persisting a
  broken Reference (sha=None, perpetually "missing").
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.store import notes_dir, parse_note_file

runner = CliRunner()


class TestSymbolOnNonPythonFile:
    def test_symbol_dropped_for_typescript(self, repo: Path):
        """`--refs path.ts:fnName` should pin whole file, not persist symbol."""
        src = repo / "src" / "auth.ts"
        src.parent.mkdir(parents=True)
        src.write_text("export function requireOwnership() { return true }\n")

        result = runner.invoke(
            app,
            [
                "add",
                "--topic", "x", "--title", "T", "--body", "b",
                "--refs", "src/auth.ts:requireOwnership",
                "--repo", str(repo),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Python-only" in result.output

        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        ref = note.references[0]
        assert ref.symbol is None, "symbol field must be dropped for non-Python files"
        assert ref.sha is not None, "sha should be computed for the whole file"
        assert ref.lines is None

    def test_python_symbol_typo_still_persists_to_flag_stale(self, repo: Path):
        """For Python files, missing symbol persists so it stays stale (typo signal)."""
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True)
        src.write_text("def real_fn():\n    return 1\n")

        result = runner.invoke(
            app,
            [
                "add",
                "--topic", "x", "--title", "T", "--body", "b",
                "--refs", "src/thing.py:nonexistent",
                "--repo", str(repo),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "could not resolve symbol" in result.output

        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        ref = note.references[0]
        # Existing v0.5 behavior preserved: symbol stays so verify flags it.
        assert ref.symbol == "nonexistent"


class TestSymbolOnNonPythonFileViaDraft:
    def test_draft_symbol_dropped_for_non_python(self, repo: Path, tmp_path: Path):
        """--from draft.md with symbol on non-Python file should also degrade."""
        src = repo / "src" / "auth.ts"
        src.parent.mkdir(parents=True)
        src.write_text("export function f() {}\n")

        draft = tmp_path / "draft.md"
        draft.write_text(dedent("""\
            ---
            topic: x
            title: T
            confidence: high
            written_by: claude-test
            written_at: '2026-04-30T00:00:00Z'
            references:
              - path: src/auth.ts
                symbol: f
            ---

            body
        """))

        result = runner.invoke(
            app,
            ["add", "--from", str(draft), "--repo", str(repo)],
        )
        assert result.exit_code == 0, result.output
        assert "Python-only" in result.output

        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        ref = note.references[0]
        assert ref.symbol is None
        assert ref.sha is not None


class TestDirectoryRef:
    def test_directory_ref_skipped_with_warning(self, repo: Path):
        """`--refs some/dir` should not persist a broken Reference."""
        d = repo / "supabase" / "migrations"
        d.mkdir(parents=True)
        (d / "001_init.sql").write_text("create table foo();\n")

        # Also add a valid ref so we can confirm the dir is dropped but
        # the rest of the add succeeds.
        valid = repo / "ok.txt"
        valid.write_text("hello\n")

        result = runner.invoke(
            app,
            [
                "add",
                "--topic", "x", "--title", "T", "--body", "b",
                "--refs", "supabase/migrations,ok.txt",
                "--repo", str(repo),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "is a directory" in result.output

        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        # Only the valid file ref should have made it.
        assert len(note.references) == 1
        assert note.references[0].path == "ok.txt"

    def test_directory_ref_in_draft_skipped(self, repo: Path, tmp_path: Path):
        d = repo / "supabase" / "migrations"
        d.mkdir(parents=True)
        valid = repo / "ok.txt"
        valid.write_text("hello\n")

        draft = tmp_path / "draft.md"
        draft.write_text(dedent("""\
            ---
            topic: x
            title: T
            confidence: high
            written_by: claude-test
            written_at: '2026-04-30T00:00:00Z'
            references:
              - path: supabase/migrations
              - path: ok.txt
            ---

            body
        """))

        result = runner.invoke(
            app,
            ["add", "--from", str(draft), "--repo", str(repo)],
        )
        assert result.exit_code == 0, result.output
        assert "is a directory" in result.output

        note, _body = parse_note_file(notes_dir(repo) / "0001-x.md")
        assert len(note.references) == 1
        assert note.references[0].path == "ok.txt"
