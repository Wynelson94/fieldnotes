"""Tests for v0.8 — the git pre-commit drift gate at the CLI surface:
`verify --check/--quiet`, `install-git-hook`, and `init` auto-installing it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.githook import HOOK_MARKER

runner = CliRunner()


def _add_note_pinning(repo: Path, rel: str) -> None:
    """Add a note in `repo` that pins the existing file at `rel`."""
    result = runner.invoke(
        app,
        [
            "add",
            "--topic",
            "t",
            "--title",
            "T",
            "--body",
            "b",
            "--refs",
            rel,
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


class TestVerifyCheck:
    def test_check_passes_when_clean(self, repo: Path):
        (repo / "f.txt").write_text("hello\n")
        _add_note_pinning(repo, "f.txt")
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 0, result.output

    def test_check_fails_when_stale(self, repo: Path):
        (repo / "f.txt").write_text("hello\n")
        _add_note_pinning(repo, "f.txt")
        (repo / "f.txt").write_text("changed\n")
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 1, result.output

    def test_check_passes_with_no_notes(self, repo: Path):
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 0, result.output

    def test_plain_verify_never_exits_nonzero(self, repo: Path):
        (repo / "f.txt").write_text("hello\n")
        _add_note_pinning(repo, "f.txt")
        (repo / "f.txt").write_text("changed\n")
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert result.exit_code == 0, result.output

    def test_quiet_suppresses_all_clear(self, repo: Path):
        (repo / "f.txt").write_text("hello\n")
        _add_note_pinning(repo, "f.txt")
        result = runner.invoke(app, ["verify", "--check", "--quiet", "--repo", str(repo)])
        assert result.exit_code == 0
        assert "verified" not in result.output

    def test_quiet_still_reports_drift(self, repo: Path):
        (repo / "f.txt").write_text("hello\n")
        _add_note_pinning(repo, "f.txt")
        (repo / "f.txt").write_text("changed\n")
        result = runner.invoke(app, ["verify", "--check", "--quiet", "--repo", str(repo)])
        assert result.exit_code == 1
        assert "stale" in result.output

    def test_check_json_fails_when_stale(self, repo: Path):
        (repo / "f.txt").write_text("hello\n")
        _add_note_pinning(repo, "f.txt")
        (repo / "f.txt").write_text("changed\n")
        result = runner.invoke(app, ["verify", "--check", "--json", "--repo", str(repo)])
        assert result.exit_code == 1
        assert '"stale": true' in result.output


class TestInstallGitHookCommand:
    def test_installs_in_git_repo(self, git_repo: Path):
        result = runner.invoke(app, ["install-git-hook", "--bare", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        hook = git_repo / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert HOOK_MARKER in hook.read_text()

    def test_idempotent(self, git_repo: Path):
        runner.invoke(app, ["install-git-hook", "--bare", "--repo", str(git_repo)])
        result = runner.invoke(app, ["install-git-hook", "--bare", "--repo", str(git_repo)])
        assert result.exit_code == 0
        assert "already installed" in result.output

    def test_fails_in_non_git_repo(self, repo: Path):
        # `repo` has .fieldnotes/ but is not a git repo.
        result = runner.invoke(app, ["install-git-hook", "--bare", "--repo", str(repo)])
        assert result.exit_code == 1


class TestInitInstallsGate:
    def test_init_installs_hook_in_git_repo(self, tmp_path: Path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0, result.output
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert HOOK_MARKER in hook.read_text()

    def test_no_git_hook_flag_skips(self, tmp_path: Path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        result = runner.invoke(app, ["init", str(tmp_path), "--no-git-hook"])
        assert result.exit_code == 0
        assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()

    def test_init_non_git_dir_succeeds_without_hook(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".fieldnotes").is_dir()


class TestEndToEndCommitGate:
    def test_commit_blocked_when_a_note_is_stale(self, git_repo: Path):
        binary = shutil.which("fieldnotes")
        if binary is None:
            pytest.skip("fieldnotes not on PATH — skipping the real-commit test")

        (git_repo / "f.txt").write_text("hello\n")
        _add_note_pinning(git_repo, "f.txt")
        installed = runner.invoke(app, ["install-git-hook", "--repo", str(git_repo)])
        assert installed.exit_code == 0, installed.output

        # A clean commit (pinned file unchanged) passes the gate.
        subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)
        clean = subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert clean.returncode == 0, clean.stderr

        # Editing the pinned file stales the note — the next commit is blocked.
        (git_repo / "f.txt").write_text("changed\n")
        subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)
        blocked = subprocess.run(
            ["git", "commit", "-m", "should fail"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert blocked.returncode != 0, "commit should have been blocked by the gate"
