"""Tests for fieldnotes.store.notes_referencing and to_repo_relative."""

from __future__ import annotations

from pathlib import Path

from fieldnotes.models import Note, Reference
from fieldnotes.store import notes_referencing, to_repo_relative, write_note


def _note(id_: str, refs: list[Reference]) -> Note:
    return Note(id=id_, topic=f"t{id_}", title=f"T {id_}", references=refs)


class TestToRepoRelative:
    def test_already_relative(self, tmp_path: Path):
        assert to_repo_relative(tmp_path, "src/x.py") == "src/x.py"

    def test_strips_dot_prefix(self, tmp_path: Path):
        assert to_repo_relative(tmp_path, "./src/x.py") == "src/x.py"

    def test_absolute_inside_repo(self, tmp_path: Path):
        target = tmp_path / "src" / "x.py"
        target.parent.mkdir(parents=True)
        target.write_text("")
        assert to_repo_relative(tmp_path, target) == "src/x.py"

    def test_absolute_outside_repo_returns_posix(self, tmp_path: Path):
        outside = Path("/tmp/elsewhere/x.py")
        # Just verify it returns *something* posix-like, not a crash.
        result = to_repo_relative(tmp_path, outside)
        assert "x.py" in result


class TestNotesReferencing:
    def test_finds_match(self, repo: Path):
        write_note(repo, _note("0001", [Reference(path="src/a.py")]), "x")
        write_note(repo, _note("0002", [Reference(path="src/b.py")]), "y")
        hits = notes_referencing(repo, "src/a.py")
        assert len(hits) == 1
        assert hits[0][0].id == "0001"

    def test_finds_via_absolute_path(self, repo: Path):
        write_note(repo, _note("0001", [Reference(path="src/a.py")]), "x")
        hits = notes_referencing(repo, repo / "src" / "a.py")
        assert len(hits) == 1

    def test_no_match(self, repo: Path):
        write_note(repo, _note("0001", [Reference(path="src/a.py")]), "x")
        assert notes_referencing(repo, "src/missing.py") == []

    def test_dedupes_per_note(self, repo: Path):
        # If a note happens to list the same file twice (path duplication), still
        # counts once.
        n = _note("0001", [Reference(path="src/a.py"), Reference(path="src/a.py")])
        write_note(repo, n, "x")
        hits = notes_referencing(repo, "src/a.py")
        assert len(hits) == 1

    def test_multiple_notes_same_file(self, repo: Path):
        write_note(repo, _note("0001", [Reference(path="src/a.py")]), "x")
        write_note(repo, _note("0002", [Reference(path="src/a.py")]), "y")
        hits = notes_referencing(repo, "src/a.py")
        assert len(hits) == 2
