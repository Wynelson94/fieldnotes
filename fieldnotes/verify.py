"""SHA-based staleness checking for fieldnotes references."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fieldnotes.models import Note, Reference
from fieldnotes.symbols import resolve_symbol


@dataclass(frozen=True)
class ReferenceStatus:
    """Result of checking a single reference."""

    reference: Reference
    state: str  # "ok" | "stale" | "missing" | "unpinned"
    actual_sha: str | None  # sha at check time, None if file missing or unpinned
    actual_lines: list[int] | None = field(default=None)
    # ^ for symbol-pinned refs: lines where the symbol resolves *now*. May
    #   differ from ref.lines if the symbol moved within the file.

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
        return any(r.is_problem and not r.reference.advisory for r in self.references)

    @property
    def stale_count(self) -> int:
        return sum(1 for r in self.references if r.is_problem and not r.reference.advisory)

    @property
    def needs_repin(self) -> bool:
        """Any drifted ref at all, advisory included — what --update refreshes."""
        return any(r.is_problem for r in self.references)


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
    target = _resolve_ref_path(repo_root, ref)
    if not target.exists():
        return ReferenceStatus(reference=ref, state="missing", actual_sha=None)

    effective_lines = ref.lines
    actual_lines: list[int] | None = None
    if ref.symbol is not None:
        resolved = resolve_symbol(target, ref.symbol)
        if resolved is None:
            # Symbol gone (renamed, deleted, or unparseable) — count as stale.
            return ReferenceStatus(reference=ref, state="stale", actual_sha=None, actual_lines=None)
        effective_lines = list(resolved)
        actual_lines = effective_lines

    actual = compute_range_sha(target, effective_lines)
    if actual is None:
        return ReferenceStatus(reference=ref, state="missing", actual_sha=None)
    if ref.sha is None:
        return ReferenceStatus(
            reference=ref, state="unpinned", actual_sha=actual, actual_lines=actual_lines
        )
    if ref.sha == actual:
        return ReferenceStatus(
            reference=ref, state="ok", actual_sha=actual, actual_lines=actual_lines
        )
    return ReferenceStatus(
        reference=ref, state="stale", actual_sha=actual, actual_lines=actual_lines
    )


def check_note(repo_root: Path, note: Note, path: Path) -> NoteStatus:
    statuses = [check_reference(repo_root, r) for r in note.references]
    return NoteStatus(note=note, path=path, references=statuses)


def find_moved_range(path: Path, target_sha: str, range_size: int) -> list[tuple[int, int]]:
    """Find every 1-indexed [start, end] line range in `path` whose contents
    hash to `target_sha`. Used by --rebase to locate where a previously-pinned
    block of code ended up after a refactor moved it within the same file.

    Returns an empty list if the file is missing, the range size is invalid,
    or no window matches. Multiple matches are possible (rare; identical
    adjacent blocks); callers decide how to disambiguate.
    """
    if not path.exists() or not path.is_file():
        return []
    if range_size <= 0:
        return []
    raw = path.read_bytes()
    file_lines = raw.splitlines(keepends=True)
    n = len(file_lines)
    if range_size > n:
        return []
    matches: list[tuple[int, int]] = []
    for start_idx in range(n - range_size + 1):
        h = hashlib.sha256()
        for line in file_lines[start_idx : start_idx + range_size]:
            h.update(line)
        if h.hexdigest() == target_sha:
            matches.append((start_idx + 1, start_idx + range_size))
    return matches


@dataclass(frozen=True)
class RebaseResult:
    """Outcome of attempting to rebase one stale line-range pin to follow
    code that moved within the file. Surfaced by the CLI so users can see
    what the tool did on their behalf."""

    ref_path: str
    original_lines: list[int] | None
    new_lines: list[int] | None
    outcome: str  # "rebased" | "ambiguous" | "no_match"


def update_shas(
    note: Note,
    statuses: list[ReferenceStatus],
    repo_root: Path | None = None,
    rebase: bool = False,
    rebase_results: list[RebaseResult] | None = None,
) -> Note:
    """Return a copy of `note` with reference SHAs re-pinned to actual values.

    Missing files are left alone. Statuses must align positionally with note.references.

    When `rebase=True` and `repo_root` is provided, stale line-range pins (refs
    with `lines` set and no `symbol`) try to re-locate their original content
    elsewhere in the file by SHA. If found, both `lines` and `sha` are updated
    so the pin tracks the moved block; the SHA stays the same since the content
    is identical. If `rebase_results` is supplied, per-ref outcomes are appended.
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

        if (
            rebase
            and st.state == "stale"
            and ref.symbol is None
            and ref.lines is not None
            and ref.sha is not None
            and repo_root is not None
        ):
            target = _resolve_ref_path(repo_root, ref)
            range_size = ref.lines[1] - ref.lines[0] + 1
            matches = find_moved_range(target, ref.sha, range_size)
            if matches:
                if len(matches) == 1:
                    new_start, new_end = matches[0]
                    outcome = "rebased"
                else:
                    new_start, new_end = min(matches, key=lambda m: abs(m[0] - ref.lines[0]))
                    outcome = "ambiguous"
                if rebase_results is not None:
                    rebase_results.append(
                        RebaseResult(
                            ref_path=ref.path,
                            original_lines=list(ref.lines),
                            new_lines=[new_start, new_end],
                            outcome=outcome,
                        )
                    )
                new_refs.append(
                    Reference(
                        path=ref.path,
                        sha=ref.sha,
                        lines=[new_start, new_end],
                        symbol=None,
                        # Content is identical, only its location changed —
                        # the pin event is still the original one.
                        pinned_at=ref.pinned_at,
                        advisory=ref.advisory,
                    )
                )
                continue
            if rebase_results is not None:
                rebase_results.append(
                    RebaseResult(
                        ref_path=ref.path,
                        original_lines=list(ref.lines),
                        new_lines=None,
                        outcome="no_match",
                    )
                )
            # Fall through to in-place re-pin: locks SHA to whatever is at
            # the original line range now, even if it's unrelated content.

        # For symbol-pinned refs, prefer the re-resolved lines so the stored
        # range tracks the symbol's current location.
        new_lines = st.actual_lines if st.actual_lines is not None else ref.lines
        new_refs.append(
            Reference(
                path=ref.path,
                sha=st.actual_sha,
                lines=new_lines,
                symbol=ref.symbol,
                pinned_at=(
                    datetime.now(timezone.utc) if st.actual_sha != ref.sha else ref.pinned_at
                ),
                advisory=ref.advisory,
            )
        )
    return note.model_copy(update={"references": new_refs})
