"""Tests for v0.2 CLI commands: for, add --from, brief."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest
from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.store import notes_dir

runner = CliRunner()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


@pytest.fixture()
def git_repo(repo: Path) -> Path:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "a.py").write_text("a\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _add(repo: Path, *args: str):
    return runner.invoke(app, ["add", "--repo", str(repo), *args])


class TestForCommand:
    def test_finds_notes(self, repo: Path):
        _add(
            repo,
            "--topic",
            "a",
            "--title",
            "About a",
            "--body",
            "x",
            "--refs",
            "src/a.py",
        )
        _add(
            repo,
            "--topic",
            "b",
            "--title",
            "About b",
            "--body",
            "x",
            "--refs",
            "src/b.py",
        )
        result = runner.invoke(app, ["for", "src/a.py", "--repo", str(repo)])
        assert result.exit_code == 0
        assert "About a" in result.output
        assert "About b" not in result.output

    def test_no_match(self, repo: Path):
        result = runner.invoke(app, ["for", "src/missing.py", "--repo", str(repo)])
        assert result.exit_code == 0
        assert "no notes reference" in result.output

    def test_json_out(self, repo: Path):
        _add(repo, "--topic", "a", "--title", "T", "--body", "x", "--refs", "src/a.py")
        result = runner.invoke(app, ["for", "src/a.py", "--json", "--repo", str(repo)])
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["topic"] == "a"


class TestAddFromDraft:
    def test_full_draft(self, repo: Path, tmp_path: Path):
        # Create a real source file so the sha pin succeeds.
        src = repo / "src" / "thing.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("def thing(): pass\n")

        draft = tmp_path / "draft.md"
        draft.write_text(
            dedent(
                """\
                ---
                topic: my-topic
                title: A drafted note
                confidence: high
                tags:
                  - drafted
                  - cli
                references:
                  - path: src/thing.py
                ---

                # The body

                Stuff goes here.
                """
            )
        )
        result = runner.invoke(app, ["add", "--from", str(draft), "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        files = list(notes_dir(repo).iterdir())
        assert any("my-topic" in f.name for f in files)
        text = (notes_dir(repo) / "0001-my-topic.md").read_text()
        assert "A drafted note" in text
        # SHA should have been pinned (not null) since the file exists.
        assert "sha: null" not in text
        assert "Stuff goes here" in text

    def test_missing_required_flags_errors(self, repo: Path):
        result = runner.invoke(app, ["add", "--repo", str(repo)])
        assert result.exit_code == 2
        assert "either --from" in result.output or "--topic" in result.output

    def test_draft_id_is_overwritten(self, repo: Path, tmp_path: Path):
        # Even if the user puts a bogus id in the draft, fieldnotes assigns next_id.
        draft = tmp_path / "draft.md"
        draft.write_text(
            dedent(
                """\
                ---
                id: '9999'
                topic: x
                title: T
                ---

                body
                """
            )
        )
        result = runner.invoke(app, ["add", "--from", str(draft), "--repo", str(repo)])
        assert result.exit_code == 0
        # File should be 0001-x.md, not 9999-x.md.
        assert (notes_dir(repo) / "0001-x.md").exists()


class TestBriefCommand:
    def test_silent_when_uninitialized(self, tmp_path: Path):
        result = runner.invoke(app, ["brief", "--repo", str(tmp_path)])
        # Should return cleanly even though there's no .fieldnotes/.
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_silent_when_empty(self, repo: Path):
        result = runner.invoke(app, ["brief", "--repo", str(repo)])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_shows_count_and_stale(self, git_repo: Path):
        # Add a note pinned to a wrong sha so it's stale.
        _git(git_repo, "config", "user.email", "t@example.com")
        from fieldnotes.models import Note, Reference
        from fieldnotes.store import write_note

        write_note(
            git_repo,
            Note(
                id="0001",
                topic="a",
                title="About a",
                references=[Reference(path="src/a.py", sha="0" * 64)],
            ),
            "body",
        )
        result = runner.invoke(app, ["brief", "--repo", str(git_repo)])
        assert result.exit_code == 0
        assert "1 note" in result.output
        assert "stale" in result.output

    def test_surfaces_recent_changes(self, git_repo: Path):
        from fieldnotes.models import Note, Reference
        from fieldnotes.store import write_note

        # Modify src/a.py so it shows up in `git status`.
        (git_repo / "src" / "a.py").write_text("changed\n")
        write_note(
            git_repo,
            Note(
                id="0001",
                topic="a",
                title="About a",
                references=[Reference(path="src/a.py")],
            ),
            "body",
        )
        result = runner.invoke(app, ["brief", "--repo", str(git_repo)])
        assert result.exit_code == 0
        assert "src/a.py" in result.output
        assert "About a" in result.output
