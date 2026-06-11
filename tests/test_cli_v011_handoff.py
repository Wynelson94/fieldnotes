"""Tests for v0.11.0 `fieldnotes handoff` — the session-end moment.

Designed for the Claude Code Stop hook: compare what the session changed
against what's documented, and ask the closing Claude to record what it
learned — or decline on purpose. Silent whenever there's nothing to say.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from fieldnotes.cli import _build_hook_snippet, app

runner = CliRunner()


def _commit_all(repo: Path, msg: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=repo, check=True)


def _add_note(repo: Path, refs: str) -> None:
    result = runner.invoke(
        app,
        [
            "add",
            "--topic",
            "t",
            "--title",
            "Covered claim",
            "--body",
            "b",
            "--refs",
            refs,
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


class TestHandoffCommand:
    def test_uncovered_changes_prompt_a_note(self, git_repo: Path):
        (git_repo / "base.py").write_text("x\n")
        _commit_all(git_repo, "base")
        (git_repo / "new_thing.py").write_text("y\n")  # uncommitted, uncovered
        result = runner.invoke(app, ["handoff", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "new_thing.py" in result.output
        assert "fieldnotes add" in result.output

    def test_covered_changes_show_their_notes(self, git_repo: Path):
        (git_repo / "core.py").write_text("x\n")
        _commit_all(git_repo, "base")
        _add_note(git_repo, "core.py")
        (git_repo / "core.py").write_text("x = 2\n")
        result = runner.invoke(app, ["handoff", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "0001" in result.output
        assert "Covered claim" in result.output

    def test_silent_when_nothing_changed(self, git_repo: Path):
        (git_repo / "core.py").write_text("x\n")
        _add_note(git_repo, "core.py")
        _commit_all(git_repo, "all committed")
        # The only "recent" paths are the freshly committed note + core.py
        # which is covered → covered-only output is fine, but a repo with
        # NO uncovered changes must not demand a note.
        result = runner.invoke(app, ["handoff", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "fieldnotes add" not in result.output

    def test_silent_outside_fieldnotes_repo(self, tmp_path: Path):
        result = runner.invoke(app, ["handoff", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_silent_outside_git(self, repo: Path):
        (repo / "f.py").write_text("x\n")
        result = runner.invoke(app, ["handoff", "--repo", str(repo)])
        assert result.exit_code == 0
        assert result.output.strip() == ""


class TestStopHookWiring:
    def test_snippet_contains_stop_handoff(self):
        snippet = _build_hook_snippet("fieldnotes")
        stop = snippet["hooks"]["Stop"]
        commands = [h["command"] for entry in stop for h in entry["hooks"]]
        assert "fieldnotes handoff 2>/dev/null || true" in commands

    def test_stop_command_is_shell_quoted(self):
        snippet = _build_hook_snippet("/Users/some user/bin/fieldnotes")
        stop = snippet["hooks"]["Stop"]
        cmd = stop[0]["hooks"][0]["command"]
        assert cmd.startswith("'/Users/some user/bin/fieldnotes' ")
