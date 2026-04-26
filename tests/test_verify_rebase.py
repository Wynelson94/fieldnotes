"""Tests for line-range pin self-healing via verify --rebase."""

from __future__ import annotations

from pathlib import Path

from fieldnotes.models import Note, Reference
from fieldnotes.store import write_note
from fieldnotes.verify import (
    RebaseResult,
    check_note,
    compute_range_sha,
    find_moved_range,
    update_shas,
)


def _multiline_file(p: Path, n: int) -> None:
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n")


class TestFindMovedRange:
    def test_finds_block_at_original_position(self, tmp_path: Path):
        f = tmp_path / "x.py"
        _multiline_file(f, 20)
        target_sha = compute_range_sha(f, [3, 5])
        matches = find_moved_range(f, target_sha, range_size=3)
        assert (3, 5) in matches

    def test_finds_block_after_move(self, tmp_path: Path):
        f = tmp_path / "x.py"
        _multiline_file(f, 10)
        # Capture SHA of lines 3-5 ("line 3", "line 4", "line 5").
        target_sha = compute_range_sha(f, [3, 5])
        # Prepend 5 unrelated lines, pushing the original block to lines 8-10.
        prepended = "\n".join(f"new {i}" for i in range(1, 6)) + "\n" + f.read_text()
        f.write_text(prepended)
        matches = find_moved_range(f, target_sha, range_size=3)
        assert matches == [(8, 10)]

    def test_no_match_when_content_modified(self, tmp_path: Path):
        f = tmp_path / "x.py"
        _multiline_file(f, 10)
        target_sha = compute_range_sha(f, [3, 5])
        # Edit line 4 — content no longer exists anywhere in the file.
        text = f.read_text().splitlines()
        text[3] = "line 4 EDITED"
        f.write_text("\n".join(text) + "\n")
        assert find_moved_range(f, target_sha, range_size=3) == []

    def test_multiple_identical_blocks(self, tmp_path: Path):
        f = tmp_path / "x.py"
        f.write_text("a\nb\nc\nx\ny\na\nb\nc\nz\n")
        target_sha = compute_range_sha(f, [1, 3])
        matches = find_moved_range(f, target_sha, range_size=3)
        assert (1, 3) in matches and (6, 8) in matches

    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert find_moved_range(tmp_path / "nope.py", "deadbeef", range_size=3) == []

    def test_range_larger_than_file(self, tmp_path: Path):
        f = tmp_path / "x.py"
        _multiline_file(f, 3)
        assert find_moved_range(f, "deadbeef", range_size=10) == []


class TestUpdateShasRebase:
    def _stale_line_pin(self, repo: Path) -> tuple[Note, Path, Path]:
        f = repo / "src" / "code.py"
        f.parent.mkdir(parents=True)
        _multiline_file(f, 10)
        rel = f.relative_to(repo).as_posix()
        original_sha = compute_range_sha(f, [3, 5])
        n = Note(
            id="0001",
            topic="t",
            title="T",
            references=[Reference(path=rel, sha=original_sha, lines=[3, 5])],
        )
        path = write_note(repo, n, "body")
        # Push the original block down by 5 lines.
        f.write_text("\n".join(f"new {i}" for i in range(1, 6)) + "\n" + f.read_text())
        return n, f, path

    def test_rebase_relocates_moved_block(self, repo: Path):
        n, _f, path = self._stale_line_pin(repo)
        status = check_note(repo, n, path)
        assert status.is_stale
        results: list[RebaseResult] = []
        new_n = update_shas(
            n, status.references, repo_root=repo, rebase=True, rebase_results=results
        )
        assert new_n.references[0].lines == [8, 10]
        assert new_n.references[0].sha == n.references[0].sha  # same content, same sha
        assert len(results) == 1
        assert results[0].outcome == "rebased"
        assert results[0].new_lines == [8, 10]
        # And the rebased note now verifies clean.
        re_status = check_note(repo, new_n, path)
        assert not re_status.is_stale

    def test_rebase_falls_back_when_content_gone(self, repo: Path):
        f = repo / "src" / "code.py"
        f.parent.mkdir(parents=True)
        _multiline_file(f, 10)
        rel = f.relative_to(repo).as_posix()
        original_sha = compute_range_sha(f, [3, 5])
        n = Note(
            id="0001",
            topic="t",
            title="T",
            references=[Reference(path=rel, sha=original_sha, lines=[3, 5])],
        )
        path = write_note(repo, n, "body")
        # Mutate line 4 in place — original content vanishes from the file.
        text = f.read_text().splitlines()
        text[3] = "line 4 EDITED"
        f.write_text("\n".join(text) + "\n")
        status = check_note(repo, n, path)
        assert status.is_stale
        results: list[RebaseResult] = []
        new_n = update_shas(
            n, status.references, repo_root=repo, rebase=True, rebase_results=results
        )
        # Falls back to in-place re-pin: same lines, new sha.
        assert new_n.references[0].lines == [3, 5]
        assert new_n.references[0].sha != n.references[0].sha
        assert results[0].outcome == "no_match"

    def test_rebase_picks_closest_when_ambiguous(self, repo: Path):
        f = repo / "src" / "code.py"
        f.parent.mkdir(parents=True)
        # Build a file with two identical 3-line blocks.
        f.write_text("a\nb\nc\nx\ny\na\nb\nc\nz\n")
        rel = f.relative_to(repo).as_posix()
        original_sha = compute_range_sha(f, [1, 3])
        # Pin the second block (lines 6-8). After a refactor that swaps the
        # blocks, the second block's content might be at lines 1-3 OR 6-8 —
        # we should pick the match closest to the original pin.
        n = Note(
            id="0001",
            topic="t",
            title="T",
            references=[Reference(path=rel, sha=original_sha, lines=[6, 8])],
        )
        path = write_note(repo, n, "body")
        # Edit line 7 to invalidate the lines-6-8 pin while leaving lines 1-3
        # identical.
        text = f.read_text().splitlines()
        text[6] = "b EDITED"
        f.write_text("\n".join(text) + "\n")
        status = check_note(repo, n, path)
        assert status.is_stale
        results: list[RebaseResult] = []
        update_shas(
            n, status.references, repo_root=repo, rebase=True, rebase_results=results
        )
        assert results[0].outcome in {"rebased", "ambiguous"}
        # Only one match remains (lines 1-3); should land there.
        assert results[0].new_lines == [1, 3]

    def test_rebase_noop_for_symbol_pins(self, repo: Path):
        f = repo / "src" / "code.py"
        f.parent.mkdir(parents=True)
        f.write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n")
        rel = f.relative_to(repo).as_posix()
        # A symbol-pinned ref pinned to a stale SHA. update_shas should not
        # divert it through the rebase path even when --rebase is set.
        bogus_sha = "0" * 64
        ref = Reference(path=rel, symbol="foo", lines=[1, 2], sha=bogus_sha)
        n = Note(id="0001", topic="t", title="T", references=[ref])
        path = write_note(repo, n, "body")
        status = check_note(repo, n, path)
        results: list[RebaseResult] = []
        new_n = update_shas(
            n, status.references, repo_root=repo, rebase=True, rebase_results=results
        )
        # Symbol-pinned refs go through the standard path; no rebase entries.
        assert results == []
        # And the symbol pin still got its sha refreshed normally.
        assert new_n.references[0].symbol == "foo"

    def test_rebase_disabled_by_default(self, repo: Path):
        # update_shas without rebase=True must keep the legacy contract:
        # stale line-range pins re-pin SHA at original lines, no relocation.
        n, _f, path = self._stale_line_pin(repo)
        status = check_note(repo, n, path)
        new_n = update_shas(n, status.references)  # no rebase
        assert new_n.references[0].lines == [3, 5]  # unchanged
        # SHA differs because lines 3-5 now contain unrelated content.
        assert new_n.references[0].sha != n.references[0].sha
