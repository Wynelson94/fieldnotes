"""Explain a stale note: what changed under its pins since they were pinned.

`verify` says *that* a reference drifted; `fieldnotes diff` shows *what*
drifted. For each reference, find the last commit at or before the pin time
(`Reference.pinned_at`, falling back to the note's `written_at`) and diff
the path from that commit to the working tree — uncommitted drift included.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fieldnotes.models import Note, Reference

# git's well-known empty tree — diff base when no commit predates the pin,
# so the whole file shows as added rather than the diff silently vanishing.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _git(repo_root: Path, *args: str) -> tuple[int, str]:
    """Run `git ...` in `repo_root`. Returns (returncode, stdout)."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return 127, ""
    return out.returncode, out.stdout


def is_git_repo(repo_root: Path) -> bool:
    rc, _ = _git(repo_root, "rev-parse", "--show-toplevel")
    return rc == 0


def base_commit(repo_root: Path, when: datetime) -> str | None:
    """The last commit at or before `when`, or None if history starts later."""
    rc, out = _git(repo_root, "rev-list", "-1", f"--before={when.isoformat()}", "HEAD")
    if rc != 0:
        return None
    return out.strip() or None


@dataclass(frozen=True)
class RefDiff:
    """One reference's drift story, ready for the CLI to render."""

    reference: Reference
    base: str | None  # commit the diff starts from (None when not applicable)
    diff: str | None  # unified diff text (None when there's only a message)
    message: str | None  # why there's no diff, or "no textual change"


def pin_descriptor(ref: Reference) -> str:
    if ref.symbol is not None:
        return f"symbol {ref.symbol}"
    if ref.lines is not None:
        return f"lines {ref.lines[0]}-{ref.lines[1]}"
    return "whole file"


def diff_reference(repo_root: Path, ref: Reference, fallback_when: datetime) -> RefDiff:
    rc, _ = _git(repo_root, "ls-files", "--error-unmatch", ref.path)
    if rc != 0:
        return RefDiff(ref, None, None, "not tracked by git")
    when = ref.pinned_at or fallback_when
    base = base_commit(repo_root, when) or EMPTY_TREE
    rc, out = _git(repo_root, "diff", base, "--", ref.path)
    if rc != 0:
        return RefDiff(ref, base, None, "git diff failed")
    if not out.strip():
        return RefDiff(ref, base, None, f"no textual change since {base[:10]}")
    return RefDiff(ref, base, out, None)


def diff_note(repo_root: Path, note: Note) -> list[RefDiff]:
    return [diff_reference(repo_root, r, note.written_at) for r in note.references]
