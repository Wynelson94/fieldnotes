"""SHA-based staleness checking for fieldnotes references."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fieldnotes.models import Note, Reference


@dataclass(frozen=True)
class ReferenceStatus:
    """Result of checking a single reference."""

    reference: Reference
    state: str  # "ok" | "stale" | "missing" | "unpinned"
    actual_sha: str | None  # sha at check time, None if file missing or unpinned

    @property
    def is_problem(self) -> bool:
        return self.state != "ok"


@dataclass(frozen=True)
class NoteStatus:
    """Result of checking a whole note."""

    note: Note
    path: Path
    references: list[ReferenceStatus]

    @property
    def is_stale(self) -> bool:
        return any(r.is_problem for r in self.references)

    @property
    def stale_count(self) -> int:
        return sum(1 for r in self.references if r.is_problem)


def compute_sha(path: Path) -> str | None:
    """Return the sha256 hex digest of `path`, or None if it doesn't exist."""
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_range_sha(path: Path, lines: list[int] | None) -> str | None:
    """Return the sha256 of `path` over the given [start, end] line range (inclusive,
    1-indexed). Falls back to whole-file sha when `lines` is None/empty.
    Returns None if the file doesn't exist."""
    if not path.exists() or not path.is_file():
        return None
    if not lines:
        return compute_sha(path)
    start, end = lines[0], lines[1]
    raw = path.read_bytes()
    file_lines = raw.splitlines(keepends=True)
    if start > len(file_lines):
        return hashlib.sha256(b"").hexdigest()
    sliced = file_lines[start - 1 : end]
    h = hashlib.sha256()
    for line in sliced:
        h.update(line)
    return h.hexdigest()


def _resolve_ref_path(repo_root: Path, ref: Reference) -> Path:
    p = Path(ref.path)
    if not p.is_absolute():
        p = repo_root / p
    return p


def check_reference(repo_root: Path, ref: Reference) -> ReferenceStatus:
    actual = compute_range_sha(_resolve_ref_path(repo_root, ref), ref.lines)
    if actual is None:
        return ReferenceStatus(reference=ref, state="missing", actual_sha=None)
    if ref.sha is None:
        return ReferenceStatus(reference=ref, state="unpinned", actual_sha=actual)
    if ref.sha == actual:
        return ReferenceStatus(reference=ref, state="ok", actual_sha=actual)
    return ReferenceStatus(reference=ref, state="stale", actual_sha=actual)


def check_note(repo_root: Path, note: Note, path: Path) -> NoteStatus:
    statuses = [check_reference(repo_root, r) for r in note.references]
    return NoteStatus(note=note, path=path, references=statuses)


def update_shas(note: Note, statuses: list[ReferenceStatus]) -> Note:
    """Return a copy of `note` with reference SHAs re-pinned to actual values.

    Missing files are left alone. Statuses must align positionally with note.references.
    """
    if len(statuses) != len(note.references):
        raise ValueError("statuses must align with note.references")
    new_refs: list[Reference] = []
    for ref, st in zip(note.references, statuses, strict=True):
        if st.state == "missing":
            new_refs.append(ref)
            continue
        if st.actual_sha is None:
            new_refs.append(ref)
            continue
        new_refs.append(
            Reference(path=ref.path, sha=st.actual_sha, lines=ref.lines)
        )
    return note.model_copy(update={"references": new_refs})
