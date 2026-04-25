"""Session-start brief: surface relevant notes when a session opens a repo."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from fieldnotes.models import Note
from fieldnotes.store import list_notes, notes_referencing
from fieldnotes.verify import NoteStatus, check_note


def recent_git_paths(repo_root: Path, *, depth: int = 5, limit: int = 50) -> list[str]:
    """Return repo-relative paths recently changed in git.

    Combines uncommitted (porcelain) + last `depth` commits. Returns [] if
    repo_root is not a git repo or git is unavailable.
    """
    paths: list[str] = []
    seen: set[str] = set()

    def _run(args: list[str]) -> list[str]:
        try:
            out = subprocess.run(
                args,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if out.returncode != 0:
            return []
        return [line.strip() for line in out.stdout.splitlines() if line.strip()]

    for line in _run(["git", "status", "--porcelain"]):
        # Format: "XY path" or "XY orig -> path" for renames.
        rest = line[3:] if len(line) > 3 else line
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        if rest and rest not in seen:
            seen.add(rest)
            paths.append(rest)

    for line in _run(["git", "log", f"-{depth}", "--name-only", "--pretty=format:"]):
        if line and line not in seen:
            seen.add(line)
            paths.append(line)

    return paths[:limit]


@dataclass
class Brief:
    total: int
    stale: list[NoteStatus]
    by_recent_path: list[tuple[str, list[tuple[Note, Path]]]]


def build_brief(repo_root: Path) -> Brief:
    rows = list_notes(repo_root)
    statuses = [check_note(repo_root, n, p) for (n, p) in rows]
    stale = [s for s in statuses if s.is_stale]

    paths = recent_git_paths(repo_root)
    by_recent: list[tuple[str, list[tuple[Note, Path]]]] = []
    for p in paths:
        hits = notes_referencing(repo_root, p)
        if hits:
            by_recent.append((p, hits))

    return Brief(total=len(rows), stale=stale, by_recent_path=by_recent)
