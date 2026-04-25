"""Tests for line-range SHA pinning."""

from __future__ import annotations

from pathlib import Path

from fieldnotes.models import Note, Reference
from fieldnotes.store import write_note
from fieldnotes.verify import (
    check_note,
    check_reference,
    compute_range_sha,
    compute_sha,
)


def _multiline_file(p: Path, n: int) -> None:
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n")


class TestComputeRangeSha:
    def test_no_lines_falls_back_to_whole_file(self, tmp_path: Path):
        f = tmp_path / "x.py"
        f.write_text("hello\n")
        assert compute_range_sha(f, None) == compute_sha(f)
        assert compute_range_sha(f, []) == compute_sha(f)

    def test_range_is_subset_of_whole(self, tmp_path: Path):
        f = tmp_path / "x.py"
        _multiline_file(f, 10)
        whole = compute_sha(f)
        ranged = compute_range_sha(f, [3, 5])
        assert ranged != whole

    def test_range_stable_across_unrelated_changes(self, tmp_path: Path):
        f = tmp_path / "x.py"
        _multiline_file(f, 10)
        before = compute_range_sha(f, [3, 5])
        # Append a new line at the end — outside [3, 5].
        with f.open("a") as fh:
            fh.write("line 11\n")
        after = compute_range_sha(f, [3, 5])
        assert before == after, "edits outside the pinned range must not invalidate the SHA"

    def test_range_changes_when_inside_edited(self, tmp_path: Path):
        f = tmp_path / "x.py"
        _multiline_file(f, 10)
        before = compute_range_sha(f, [3, 5])
        # Edit line 4.
        text = f.read_text().splitlines()
        text[3] = "line 4 EDITED"
        f.write_text("\n".join(text) + "\n")
        after = compute_range_sha(f, [3, 5])
        assert before != after

    def test_range_beyond_eof(self, tmp_path: Path):
        f = tmp_path / "x.py"
        f.write_text("a\nb\n")
        # File has 2 lines; ask for lines 100-200 → empty slice → empty hash.
        result = compute_range_sha(f, [100, 200])
        assert result == compute_range_sha(tmp_path / "empty.py.placeholder", [1, 1]) or result is not None
        # The deterministic check: it equals sha of empty bytes.
        import hashlib
        assert result == hashlib.sha256(b"").hexdigest()

    def test_missing_file(self, tmp_path: Path):
        assert compute_range_sha(tmp_path / "nope.py", [1, 5]) is None


class TestCheckReferenceWithRange:
    def test_ok_when_range_unchanged(self, repo: Path):
        f = repo / "src" / "thing.py"
        f.parent.mkdir(parents=True)
        _multiline_file(f, 20)
        rel = f.relative_to(repo).as_posix()
        sha = compute_range_sha(f, [3, 5])
        ref = Reference(path=rel, sha=sha, lines=[3, 5])
        st = check_reference(repo, ref)
        assert st.state == "ok"

    def test_ok_when_only_unpinned_lines_change(self, repo: Path):
        f = repo / "src" / "thing.py"
        f.parent.mkdir(parents=True)
        _multiline_file(f, 20)
        rel = f.relative_to(repo).as_posix()
        sha = compute_range_sha(f, [3, 5])
        ref = Reference(path=rel, sha=sha, lines=[3, 5])
        # Edit line 18 — outside [3, 5].
        text = f.read_text().splitlines()
        text[17] = "line 18 EDITED"
        f.write_text("\n".join(text) + "\n")
        st = check_reference(repo, ref)
        assert st.state == "ok", "outside-range edits must not invalidate a line-pinned ref"

    def test_stale_when_pinned_lines_change(self, repo: Path):
        f = repo / "src" / "thing.py"
        f.parent.mkdir(parents=True)
        _multiline_file(f, 20)
        rel = f.relative_to(repo).as_posix()
        sha = compute_range_sha(f, [3, 5])
        ref = Reference(path=rel, sha=sha, lines=[3, 5])
        # Edit line 4 — inside the pinned range.
        text = f.read_text().splitlines()
        text[3] = "line 4 EDITED"
        f.write_text("\n".join(text) + "\n")
        st = check_reference(repo, ref)
        assert st.state == "stale"


class TestCheckNoteMixed:
    def test_one_pinned_one_whole(self, repo: Path):
        f = repo / "src" / "a.py"
        f.parent.mkdir(parents=True)
        _multiline_file(f, 20)
        rel = f.relative_to(repo).as_posix()
        n = Note(
            id="0001",
            topic="t",
            title="T",
            references=[
                Reference(path=rel, sha=compute_range_sha(f, [3, 5]), lines=[3, 5]),
                Reference(path=rel, sha=compute_sha(f)),
            ],
        )
        path = write_note(repo, n, "body")
        # Edit line 18: pinned ref stays ok, whole-file ref goes stale.
        text = f.read_text().splitlines()
        text[17] = "line 18 EDITED"
        f.write_text("\n".join(text) + "\n")
        status = check_note(repo, n, path)
        states = [r.state for r in status.references]
        assert "ok" in states and "stale" in states
