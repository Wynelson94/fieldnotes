"""Tests for fieldnotes.store."""

from __future__ import annotations

from pathlib import Path

import pytest

from fieldnotes.models import Note, Reference
from fieldnotes.store import (
    AmbiguousNoteSelectorError,
    NoteNotFoundError,
    RepoNotInitializedError,
    find_repo_root,
    index_path,
    init_repo,
    iter_note_files,
    list_notes,
    next_id,
    notes_dir,
    parse_note_file,
    read_note,
    resolve_note_path,
    serialize_note,
    write_note,
)


def _make_note(id_: str = "0001", topic: str = "cli-entry-points", **kw) -> Note:
    base = {"id": id_, "topic": topic, "title": f"Note {id_}"}
    base.update(kw)
    return Note(**base)


class TestInit:
    def test_init_creates_scaffold(self, tmp_path: Path):
        init_repo(tmp_path)
        assert (tmp_path / ".fieldnotes").is_dir()
        assert notes_dir(tmp_path).is_dir()
        assert index_path(tmp_path).exists()
        assert (tmp_path / ".fieldnotes" / "config.toml").exists()

    def test_init_is_idempotent(self, tmp_path: Path):
        init_repo(tmp_path)
        idx_before = index_path(tmp_path).read_text()
        # Mutate the index, then re-init — init should not stomp it.
        index_path(tmp_path).write_text("custom\n")
        init_repo(tmp_path)
        assert index_path(tmp_path).read_text() == "custom\n"
        # but the empty default contents are not the same as "custom"
        assert idx_before != "custom\n"


class TestFindRepoRoot:
    def test_finds_in_self(self, repo: Path):
        assert find_repo_root(repo) == repo.resolve()

    def test_finds_from_subdir(self, repo: Path):
        sub = repo / "deep" / "nested"
        sub.mkdir(parents=True)
        assert find_repo_root(sub) == repo.resolve()

    def test_raises_when_not_initialized(self, tmp_path: Path):
        with pytest.raises(RepoNotInitializedError):
            find_repo_root(tmp_path)


class TestRoundTrip:
    def test_serialize_then_parse(self, tmp_path: Path):
        n = _make_note(
            tags=["cli", "typer"],
            references=[Reference(path="src/foo.py", sha="a" * 64, lines=[1, 5])],
        )
        text = serialize_note(n, "# Hello\n\nbody text")
        # Round-trip through file.
        f = tmp_path / "out.md"
        f.write_text(text)
        n2, body2 = parse_note_file(f)
        assert n2.id == n.id
        assert n2.topic == n.topic
        assert n2.tags == n.tags
        assert len(n2.references) == 1
        assert n2.references[0].path == "src/foo.py"
        assert n2.references[0].sha == "a" * 64
        assert "Hello" in body2

    def test_write_then_read(self, repo: Path):
        n = _make_note()
        write_note(repo, n, "body of 0001")
        out, body, path = read_note(repo, "0001")
        assert out.id == "0001"
        assert "0001" in path.name
        assert body.strip() == "body of 0001"


class TestNextId:
    def test_starts_at_0001(self, repo: Path):
        assert next_id(repo) == "0001"

    def test_increments(self, repo: Path):
        write_note(repo, _make_note("0001"), "a")
        write_note(repo, _make_note("0002", topic="b"), "b")
        assert next_id(repo) == "0003"

    def test_handles_gaps(self, repo: Path):
        write_note(repo, _make_note("0005", topic="five"), "f")
        assert next_id(repo) == "0006"


class TestResolveNotePath:
    def test_by_padded_id(self, repo: Path):
        write_note(repo, _make_note("0001"), "a")
        p = resolve_note_path(repo, "0001")
        assert p.name == "0001-cli-entry-points.md"

    def test_by_short_id(self, repo: Path):
        write_note(repo, _make_note("0001"), "a")
        p = resolve_note_path(repo, "1")
        assert p.name == "0001-cli-entry-points.md"

    def test_by_topic(self, repo: Path):
        write_note(repo, _make_note("0001", topic="event-loop-gotcha"), "a")
        p = resolve_note_path(repo, "event-loop-gotcha")
        assert "event-loop-gotcha" in p.name

    def test_not_found(self, repo: Path):
        write_note(repo, _make_note("0001"), "a")
        with pytest.raises(NoteNotFoundError):
            resolve_note_path(repo, "9999")

    def test_ambiguous_topic_raises(self, repo: Path):
        # Two notes with the same topic suffix shouldn't normally happen
        # (writes overwrite), but the resolver guards against duplicates.
        write_note(repo, _make_note("0001", topic="dup"), "a")
        write_note(repo, _make_note("0002", topic="dup"), "b")
        with pytest.raises(AmbiguousNoteSelectorError):
            resolve_note_path(repo, "dup")

    def test_empty_repo_raises(self, repo: Path):
        with pytest.raises(NoteNotFoundError):
            resolve_note_path(repo, "0001")


class TestListNotes:
    def test_empty(self, repo: Path):
        assert list_notes(repo) == []

    def test_lists_all(self, repo: Path):
        write_note(repo, _make_note("0001"), "a")
        write_note(repo, _make_note("0002", topic="other"), "b")
        notes = list_notes(repo)
        assert len(notes) == 2
        ids = [n.id for n, _ in notes]
        assert "0001" in ids and "0002" in ids

    def test_skips_malformed_silently(self, repo: Path):
        write_note(repo, _make_note("0001"), "ok")
        bad = notes_dir(repo) / "0002-broken.md"
        bad.write_text("not valid frontmatter at all\n")
        notes = list_notes(repo)
        # 0001 should still be there.
        assert any(n.id == "0001" for n, _ in notes)


class TestIterNoteFiles:
    def test_excludes_when_dir_missing(self, tmp_path: Path):
        # No .fieldnotes/ at all
        assert list(iter_note_files(tmp_path)) == []

    def test_returns_md_files_sorted(self, repo: Path):
        write_note(repo, _make_note("0002", topic="b"), "b")
        write_note(repo, _make_note("0001", topic="a"), "a")
        files = list(iter_note_files(repo))
        assert [f.name for f in files] == ["0001-a.md", "0002-b.md"]
