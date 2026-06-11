"""Tests for v0.3 CLI commands: touched, install-hooks."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fieldnotes.cli import _HOOK_SNIPPET, _merge_hooks, app
from fieldnotes.models import Note, Reference
from fieldnotes.store import write_note

runner = CliRunner()


class TestTouched:
    def test_with_path_arg(self, repo: Path):
        write_note(
            repo,
            Note(
                id="0001",
                topic="a",
                title="About a",
                references=[Reference(path="src/a.py")],
            ),
            "body",
        )
        result = runner.invoke(app, ["touched", "src/a.py", "--repo", str(repo)])
        assert result.exit_code == 0
        assert "0001" in result.output
        assert "About a" not in result.output  # we use topic, not title
        assert "(a)" in result.output

    def test_silent_on_no_match(self, repo: Path):
        result = runner.invoke(app, ["touched", "src/missing.py", "--repo", str(repo)])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_silent_when_uninitialized(self, tmp_path: Path):
        result = runner.invoke(app, ["touched", "src/x.py", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_stdin_payload(self, repo: Path):
        write_note(
            repo,
            Note(
                id="0001",
                topic="a",
                title="About a",
                references=[Reference(path="src/a.py")],
            ),
            "body",
        )
        payload = json.dumps({"tool_input": {"file_path": "src/a.py"}})
        result = runner.invoke(
            app,
            ["touched", "--stdin", "--repo", str(repo)],
            input=payload,
        )
        assert result.exit_code == 0
        assert "0001" in result.output

    def test_silent_on_bad_stdin(self, repo: Path):
        result = runner.invoke(
            app,
            ["touched", "--stdin", "--repo", str(repo)],
            input="not-json-at-all",
        )
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_silent_when_stdin_missing_file_path(self, repo: Path):
        result = runner.invoke(
            app,
            ["touched", "--stdin", "--repo", str(repo)],
            input=json.dumps({"tool_input": {}}),
        )
        assert result.exit_code == 0
        assert result.output.strip() == ""


class TestMergeHooks:
    def test_adds_to_empty(self):
        merged, added = _merge_hooks({}, _HOOK_SNIPPET["hooks"])
        assert added == 3
        assert "SessionStart" in merged["hooks"]
        assert "PostToolUse" in merged["hooks"]

    def test_idempotent(self):
        merged_once, added_once = _merge_hooks({}, _HOOK_SNIPPET["hooks"])
        merged_twice, added_twice = _merge_hooks(merged_once, _HOOK_SNIPPET["hooks"])
        assert added_twice == 0
        assert merged_once == merged_twice

    def test_preserves_existing_unrelated_hooks(self):
        existing = {
            "hooks": {
                "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo done"}]}]
            }
        }
        merged, added = _merge_hooks(existing, _HOOK_SNIPPET["hooks"])
        assert added == 3
        assert "Stop" in merged["hooks"]
        assert merged["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo done"

    def test_preserves_other_keys(self):
        existing = {"theme": "dark", "model": "claude-opus-4-7"}
        merged, _ = _merge_hooks(existing, _HOOK_SNIPPET["hooks"])
        assert merged["theme"] == "dark"
        assert merged["model"] == "claude-opus-4-7"


class TestInstallHooks:
    """Legacy tests use --bare to skip the absolute-path resolution.

    Tests for the v0.6 absolute-path resolver live in TestInstallHooksAbsolute.
    """

    def test_dry_run_prints_snippet(self):
        result = runner.invoke(app, ["install-hooks", "--bare"])
        assert result.exit_code == 0
        assert "fieldnotes hooks" in result.output
        assert "fieldnotes brief" in result.output
        assert "fieldnotes touched" in result.output

    def test_apply_creates_file(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        result = runner.invoke(app, ["install-hooks", "--bare", "--apply", "--to", str(target)])
        assert result.exit_code == 0
        assert target.exists()
        data = json.loads(target.read_text())
        assert "SessionStart" in data["hooks"]
        assert "PostToolUse" in data["hooks"]
        assert "added" in result.output

    def test_apply_is_idempotent(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        runner.invoke(app, ["install-hooks", "--bare", "--apply", "--to", str(target)])
        before = target.read_text()
        result = runner.invoke(app, ["install-hooks", "--bare", "--apply", "--to", str(target)])
        assert result.exit_code == 0
        assert "nothing changed" in result.output or "already present" in result.output
        assert target.read_text() == before

    def test_apply_preserves_existing_unrelated(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"theme": "dark", "hooks": {}}))
        result = runner.invoke(app, ["install-hooks", "--bare", "--apply", "--to", str(target)])
        assert result.exit_code == 0
        data = json.loads(target.read_text())
        assert data["theme"] == "dark"
        assert "SessionStart" in data["hooks"]

    def test_apply_handles_malformed_settings(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        target.write_text("{ this is not json")
        result = runner.invoke(app, ["install-hooks", "--bare", "--apply", "--to", str(target)])
        assert result.exit_code == 1
        assert "could not parse" in result.output

    def test_apply_creates_parent_dirs(self, tmp_path: Path):
        target = tmp_path / "deep" / "nested" / "settings.json"
        result = runner.invoke(app, ["install-hooks", "--bare", "--apply", "--to", str(target)])
        assert result.exit_code == 0
        assert target.exists()


class TestInstallHooksAbsolute:
    """v0.6 absolute-path behavior."""

    def test_uses_resolved_binary_path(self, tmp_path: Path, monkeypatch):
        fake_path = "/abs/path/to/fieldnotes"
        monkeypatch.setattr("fieldnotes.cli.shutil.which", lambda _: fake_path)
        target = tmp_path / "settings.json"
        result = runner.invoke(app, ["install-hooks", "--apply", "--to", str(target)])
        assert result.exit_code == 0, result.output
        data = json.loads(target.read_text())
        ss_cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        ptu_cmd = data["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        assert ss_cmd.startswith(fake_path + " brief")
        assert ptu_cmd.startswith(fake_path + " touched")

    def test_refuses_when_binary_not_on_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("fieldnotes.cli.shutil.which", lambda _: None)
        target = tmp_path / "settings.json"
        result = runner.invoke(app, ["install-hooks", "--apply", "--to", str(target)])
        assert result.exit_code == 1
        assert "not on PATH" in result.output
        assert not target.exists()

    def test_dry_run_shows_resolved_binary(self, monkeypatch):
        fake_path = "/abs/path/to/fieldnotes"
        monkeypatch.setattr("fieldnotes.cli.shutil.which", lambda _: fake_path)
        result = runner.invoke(app, ["install-hooks"])
        assert result.exit_code == 0
        assert fake_path in result.output

    def test_bare_flag_bypasses_resolution(self, tmp_path: Path, monkeypatch):
        # Even when which would fail, --bare succeeds.
        monkeypatch.setattr("fieldnotes.cli.shutil.which", lambda _: None)
        target = tmp_path / "settings.json"
        result = runner.invoke(app, ["install-hooks", "--bare", "--apply", "--to", str(target)])
        assert result.exit_code == 0
        data = json.loads(target.read_text())
        cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert cmd.startswith("fieldnotes brief")
