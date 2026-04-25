"""Tests for fieldnotes.brief."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from fieldnotes.brief import build_brief, recent_git_paths
from fieldnotes.models import Note, Reference
from fieldnotes.store import write_note


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


@pytest.fixture()
def git_repo(repo: Path) -> Path:
    """A repo fixture that's also a git repo with one commit."""
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "a.py").write_text("a")
    (repo / "src" / "b.py").write_text("b")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


class TestRecentGitPaths:
    def test_returns_uncommitted(self, git_repo: Path):
        (git_repo / "src" / "a.py").write_text("changed")
        paths = recent_git_paths(git_repo)
        assert "src/a.py" in paths

    def test_includes_committed(self, git_repo: Path):
        # The init commit added src/a.py and src/b.py.
        paths = recent_git_paths(git_repo)
        assert any(p in {"src/a.py", "src/b.py"} for p in paths)

    def test_returns_empty_when_not_git(self, tmp_path: Path):
        # tmp_path has no git repo.
        assert recent_git_paths(tmp_path) == []


class TestBuildBrief:
    def test_total_count(self, git_repo: Path):
        write_note(
            git_repo,
            Note(id="0001", topic="x", title="X"),
            "body",
        )
        b = build_brief(git_repo)
        assert b.total == 1

    def test_surfaces_notes_for_changed_files(self, git_repo: Path):
        # Make src/a.py "recent" by modifying it (uncommitted).
        (git_repo / "src" / "a.py").write_text("changed")
        write_note(
            git_repo,
            Note(
                id="0001",
                topic="a",
                title="About A",
                references=[Reference(path="src/a.py")],
            ),
            "body",
        )
        b = build_brief(git_repo)
        assert any(p == "src/a.py" for p, _ in b.by_recent_path)

    def test_stale_count(self, git_repo: Path):
        # Pin to a wrong sha so the note is stale.
        n = Note(
            id="0001",
            topic="a",
            title="About A",
            references=[Reference(path="src/a.py", sha="0" * 64)],
        )
        write_note(git_repo, n, "body")
        b = build_brief(git_repo)
        assert len(b.stale) == 1
