"""Tests for fieldnotes.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from fieldnotes.models import Confidence, Note, Reference


class TestReference:
    def test_minimal(self):
        r = Reference(path="src/foo.py")
        assert r.path == "src/foo.py"
        assert r.sha is None
        assert r.lines is None

    def test_path_required_nonempty(self):
        with pytest.raises(ValueError):
            Reference(path="   ")

    def test_sha_must_be_sha256_hex(self):
        with pytest.raises(ValueError):
            Reference(path="x", sha="not-a-sha")

    def test_sha_normalized_to_lowercase(self):
        sha = "A" * 64
        r = Reference(path="x", sha=sha)
        assert r.sha == "a" * 64

    def test_lines_must_be_positive(self):
        with pytest.raises(ValueError):
            Reference(path="x", lines=[0, 5])

    def test_empty_lines_becomes_none(self):
        r = Reference(path="x", lines=[])
        assert r.lines is None


class TestNote:
    def _kw(self, **over):
        base = {"id": "0001", "topic": "cli-entry-points", "title": "How the CLI is wired"}
        base.update(over)
        return base

    def test_minimal(self):
        n = Note(**self._kw())
        assert n.id == "0001"
        assert n.topic == "cli-entry-points"
        assert n.confidence is Confidence.MEDIUM
        assert n.tags == []
        assert n.references == []
        assert n.written_at.tzinfo is not None

    def test_id_must_be_zero_padded(self):
        with pytest.raises(ValueError):
            Note(**self._kw(id="1"))
        with pytest.raises(ValueError):
            Note(**self._kw(id="abc1"))

    def test_topic_must_be_kebab(self):
        with pytest.raises(ValueError):
            Note(**self._kw(topic="Bad Topic"))
        with pytest.raises(ValueError):
            Note(**self._kw(topic="bad_topic"))
        # Valid kebab passes through.
        n = Note(**self._kw(topic="event-loop-gotcha"))
        assert n.topic == "event-loop-gotcha"

    def test_title_required(self):
        with pytest.raises(ValueError):
            Note(**self._kw(title=" "))

    def test_tags_normalized_and_deduped(self):
        n = Note(**self._kw(tags=["CLI", " cli ", "typer"]))
        assert n.tags == ["cli", "typer"]

    def test_tag_must_be_kebab(self):
        with pytest.raises(ValueError):
            Note(**self._kw(tags=["bad tag"]))

    def test_naive_datetime_gets_utc(self):
        n = Note(**self._kw(written_at=datetime(2026, 1, 1, 12, 0, 0)))
        assert n.written_at.tzinfo == timezone.utc

    def test_supersedes_must_be_valid_id(self):
        with pytest.raises(ValueError):
            Note(**self._kw(supersedes="not-an-id"))
        n = Note(**self._kw(supersedes="0002"))
        assert n.supersedes == "0002"

    def test_filename(self):
        n = Note(**self._kw())
        assert n.filename() == "0001-cli-entry-points.md"
