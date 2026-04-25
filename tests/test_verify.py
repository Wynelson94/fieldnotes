"""Tests for fieldnotes.verify."""

from __future__ import annotations

from pathlib import Path

from fieldnotes.models import Note, Reference
from fieldnotes.store import write_note
from fieldnotes.verify import (
    check_note,
    check_reference,
    compute_sha,
    update_shas,
)


def _note_with_refs(*refs: Reference, id_: str = "0001") -> Note:
    return Note(id=id_, topic="t", title="t", references=list(refs))


class TestComputeSha:
    def test_returns_64_hex_chars(self, sample_source: Path):
        sha = compute_sha(sample_source)
        assert sha is not None
        assert len(sha) == 64

    def test_returns_none_for_missing(self, tmp_path: Path):
        assert compute_sha(tmp_path / "nope.py") is None

    def test_changes_when_content_changes(self, sample_source: Path):
        before = compute_sha(sample_source)
        sample_source.write_text("def thing():\n    return 99\n")
        after = compute_sha(sample_source)
        assert before != after


class TestCheckReference:
    def test_ok_when_sha_matches(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        sha = compute_sha(sample_source)
        ref = Reference(path=rel, sha=sha)
        st = check_reference(repo, ref)
        assert st.state == "ok"
        assert st.is_problem is False

    def test_stale_when_file_changes(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        ref = Reference(path=rel, sha=compute_sha(sample_source))
        sample_source.write_text("changed\n")
        st = check_reference(repo, ref)
        assert st.state == "stale"
        assert st.is_problem is True
        assert st.actual_sha != ref.sha

    def test_missing_when_file_gone(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        ref = Reference(path=rel, sha=compute_sha(sample_source))
        sample_source.unlink()
        st = check_reference(repo, ref)
        assert st.state == "missing"
        assert st.actual_sha is None

    def test_unpinned_when_no_sha(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        ref = Reference(path=rel, sha=None)
        st = check_reference(repo, ref)
        assert st.state == "unpinned"
        assert st.actual_sha is not None


class TestCheckNote:
    def test_clean_note(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        ref = Reference(path=rel, sha=compute_sha(sample_source))
        n = _note_with_refs(ref)
        path = write_note(repo, n, "body")
        status = check_note(repo, n, path)
        assert status.is_stale is False
        assert status.stale_count == 0

    def test_stale_count(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        ref_ok = Reference(path=rel, sha=compute_sha(sample_source))
        ref_missing = Reference(path="nope.py", sha="b" * 64)
        n = _note_with_refs(ref_ok, ref_missing)
        path = write_note(repo, n, "body")
        status = check_note(repo, n, path)
        assert status.is_stale is True
        assert status.stale_count == 1


class TestUpdateShas:
    def test_repins_to_current_sha(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        # Pin to a wrong sha so the note appears stale.
        n = _note_with_refs(Reference(path=rel, sha="0" * 64))
        statuses = [check_reference(repo, r) for r in n.references]
        assert statuses[0].state == "stale"
        new_n = update_shas(n, statuses)
        assert new_n.references[0].sha == compute_sha(sample_source)

    def test_leaves_missing_alone(self, repo: Path):
        n = _note_with_refs(Reference(path="nope.py", sha="b" * 64))
        statuses = [check_reference(repo, r) for r in n.references]
        new_n = update_shas(n, statuses)
        assert new_n.references[0].sha == "b" * 64
