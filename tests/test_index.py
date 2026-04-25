"""Tests for fieldnotes.index."""

from __future__ import annotations

from pathlib import Path

from fieldnotes.index import rebuild_index, render_index
from fieldnotes.models import Note
from fieldnotes.store import index_path, write_note


def _note(id_: str, topic: str = "x", tags=None, **kw) -> Note:
    return Note(id=id_, topic=topic, title=f"Title {id_}", tags=tags or [], **kw)


class TestRenderIndex:
    def test_empty(self):
        text = render_index([])
        assert "No notes yet" in text

    def test_single_note_appears(self, repo: Path):
        n = _note("0001", "cli", tags=["cli"])
        path = write_note(repo, n, "b")
        text = render_index([(n, path)])
        assert "0001" in text
        assert "Title 0001" in text
        assert "cli" in text

    def test_groups_by_tag(self, repo: Path):
        n1 = _note("0001", "a", tags=["alpha"])
        n2 = _note("0002", "b", tags=["beta"])
        p1 = write_note(repo, n1, "x")
        p2 = write_note(repo, n2, "y")
        text = render_index([(n1, p1), (n2, p2)])
        assert "### alpha" in text
        assert "### beta" in text

    def test_untagged_section(self, repo: Path):
        n = _note("0001", tags=[])
        p = write_note(repo, n, "x")
        text = render_index([(n, p)])
        assert "## Untagged" in text


class TestRebuildIndex:
    def test_writes_file(self, repo: Path):
        write_note(repo, _note("0001", "a", tags=["x"]), "body")
        write_note(repo, _note("0002", "b", tags=["y"]), "body")
        out = rebuild_index(repo)
        assert out == index_path(repo)
        text = out.read_text()
        assert "Title 0001" in text
        assert "Title 0002" in text

    def test_overwrites_default(self, repo: Path):
        # Default index says "No notes yet"
        write_note(repo, _note("0001"), "body")
        rebuild_index(repo)
        assert "No notes yet" not in index_path(repo).read_text()
