"""Coverage gaps: cross git churn with note coverage.

The pre-commit gate catches a note going stale; nothing catches a note that
was never written. This module makes that absence a measurable — the
hottest-churning files with zero notes are exactly where undocumented
knowledge is accumulating.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

from fieldnotes.store import list_notes, to_repo_relative

# A file has to churn at least this much before brief mentions it ambiently.
# Quietness is the feature — one line, only on real signal.
BRIEF_GAP_THRESHOLD = 5


def _git_lines(repo_root: Path, *args: str) -> list[str] | None:
    """Run `git ...`; stripped stdout lines, or None when git/repo unavailable."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def churn_map(repo_root: Path, since: str = "90 days ago") -> dict[str, int] | None:
    """Commits-touching-path counts within the window. None when not a git repo.

    Excludes `.fieldnotes/` (note churn isn't code churn) and paths that no
    longer exist (a deleted file isn't a coverage gap).
    """
    lines = _git_lines(repo_root, "log", f"--since={since}", "--name-only", "--pretty=format:")
    if lines is None:
        return None
    counts: Counter[str] = Counter()
    for path in lines:
        if path.startswith(".fieldnotes/"):
            continue
        counts[path] += 1
    return {p: n for p, n in counts.items() if (repo_root / p).exists()}


def coverage_paths(repo_root: Path) -> set[str]:
    """Every repo-relative path any note references (advisory included)."""
    covered: set[str] = set()
    for note, _path in list_notes(repo_root):
        for ref in note.references:
            covered.add(to_repo_relative(repo_root, ref.path))
    return covered


def uncovered_by_churn(repo_root: Path, since: str = "90 days ago") -> list[tuple[str, int]] | None:
    """Uncovered files sorted hottest-first. None when not a git repo."""
    churn = churn_map(repo_root, since=since)
    if churn is None:
        return None
    covered = coverage_paths(repo_root)
    gaps = [(p, n) for p, n in churn.items() if p not in covered]
    return sorted(gaps, key=lambda item: (-item[1], item[0]))


def hottest_gap(repo_root: Path, since: str = "90 days ago") -> tuple[str, int] | None:
    """The single hottest uncovered file at/over the brief threshold, if any."""
    gaps = uncovered_by_churn(repo_root, since=since)
    if not gaps:
        return None
    path, n = gaps[0]
    return (path, n) if n >= BRIEF_GAP_THRESHOLD else None
