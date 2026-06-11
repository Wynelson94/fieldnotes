"""Tests for v0.9.0 `fieldnotes diff` and the Reference.pinned_at field.

`diff <id-or-topic>` explains a stale note: for each pinned reference, show
the git diff of its path from the last commit before the pin to the working
tree. Turns "stale" from a flag into something a reader can act on.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import frontmatter
from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.models import Reference

runner = CliRunner()


def _add(repo: Path, refs: str, topic: str = "t") -> None:
    result = runner.invoke(
        app,
        [
            "add",
            "--topic",
            topic,
            "--title",
            "T",
            "--body",
            "b",
            "--refs",
            refs,
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


def _commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=repo, check=True)


def _first_ref(repo: Path) -> dict:
    note = next((repo / ".fieldnotes" / "notes").glob("0001-*.md"))
    return frontmatter.load(note)["references"][0]


class TestPinnedAt:
    def test_reference_defaults_to_none(self):
        assert Reference(path="f.py").pinned_at is None

    def test_add_stamps_pinned_at(self, repo: Path):
        (repo / "f.py").write_text("x = 1\n")
        _add(repo, "f.py")
        assert _first_ref(repo)["pinned_at"] is not None

    def test_update_restamps_only_changed_refs(self, repo: Path):
        (repo / "f.py").write_text("x = 1\n")
        _add(repo, "f.py")
        before = _first_ref(repo)["pinned_at"]
        (repo / "f.py").write_text("x = 2\n")
        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert _first_ref(repo)["pinned_at"] != before

    def test_rebase_preserves_pinned_at(self, repo: Path):
        (repo / "f.py").write_text("# header\ndef f():\n    return 1\n")
        _add(repo, "f.py:2-3")
        before = _first_ref(repo)["pinned_at"]
        (repo / "f.py").write_text("# new\n# header\ndef f():\n    return 1\n")
        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        ref = _first_ref(repo)
        assert ref["lines"] == [3, 4]
        # Content didn't change, only its location — the pin event is the same.
        assert ref["pinned_at"] == before


class TestDiffCommand:
    def test_shows_change_since_pin(self, git_repo: Path):
        (git_repo / "f.py").write_text("x = 1\n")
        _commit_all(git_repo, "v1")
        _add(git_repo, "f.py")
        (git_repo / "f.py").write_text("x = 2\n")

        result = runner.invoke(app, ["diff", "0001", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "-x = 1" in result.output
        assert "+x = 2" in result.output

    def test_resolves_by_topic(self, git_repo: Path):
        (git_repo / "f.py").write_text("x = 1\n")
        _commit_all(git_repo, "v1")
        _add(git_repo, "f.py", topic="my-topic")
        (git_repo / "f.py").write_text("x = 2\n")

        result = runner.invoke(app, ["diff", "my-topic", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "+x = 2" in result.output

    def test_clean_ref_reports_no_change(self, git_repo: Path):
        (git_repo / "f.py").write_text("x = 1\n")
        _commit_all(git_repo, "v1")
        _add(git_repo, "f.py")

        result = runner.invoke(app, ["diff", "0001", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "no textual change" in result.output

    def test_untracked_file_is_graceful(self, git_repo: Path):
        (git_repo / "f.py").write_text("x = 1\n")
        _add(git_repo, "f.py")  # never committed

        result = runner.invoke(app, ["diff", "0001", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "not tracked" in result.output

    def test_non_git_repo_is_graceful(self, repo: Path):
        (repo / "f.py").write_text("x = 1\n")
        _add(repo, "f.py")

        result = runner.invoke(app, ["diff", "0001", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "not a git repository" in result.output

    def test_unknown_note_exits_2(self, git_repo: Path):
        result = runner.invoke(app, ["diff", "9999", "--repo", str(git_repo)])
        assert result.exit_code == 2
