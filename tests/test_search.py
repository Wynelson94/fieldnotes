"""Tests for fieldnotes.search."""

from __future__ import annotations

from pathlib import Path

from fieldnotes.models import Note
from fieldnotes.search import search
from fieldnotes.store import write_note


def _note(id_: str, topic: str, title: str = "t") -> Note:
    return Note(id=id_, topic=topic, title=title)


class TestSearch:
    def test_empty_query_returns_nothing(self, repo: Path):
        write_note(repo, _note("0001", "x"), "anything")
        assert search(repo, "  ") == []

    def test_match_in_body(self, repo: Path):
        write_note(repo, _note("0001", "x", title="hello"), "the QUICK brown fox")
        hits = search(repo, "quick")
        assert len(hits) == 1
        assert hits[0].body_matches
        assert "quick" in hits[0].body_matches[0].lower()

    def test_match_in_title(self, repo: Path):
        write_note(repo, _note("0001", "x", title="Event Loop Gotcha"), "body")
        hits = search(repo, "loop")
        assert len(hits) == 1
        assert hits[0].title_match is True

    def test_no_match(self, repo: Path):
        write_note(repo, _note("0001", "x", title="hello"), "body")
        assert search(repo, "elsewhere") == []

    def test_caps_excerpts_per_note(self, repo: Path):
        text = "needle " * 20
        write_note(repo, _note("0001", "x"), text)
        hits = search(repo, "needle")
        assert len(hits[0].body_matches) <= 5
