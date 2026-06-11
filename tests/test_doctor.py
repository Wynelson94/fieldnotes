"""Tests for fieldnotes.doctor."""

from __future__ import annotations

import json
from pathlib import Path

from fieldnotes.doctor import (
    check_binary,
    check_cwd_repo,
    check_git_hook,
    check_hooks,
    check_package,
    run_diagnostics,
)
from fieldnotes.githook import install_git_hook


class TestBinaryCheck:
    def test_found(self, monkeypatch):
        monkeypatch.setattr("fieldnotes.doctor.shutil.which", lambda _: "/abs/fieldnotes")
        result, resolved = check_binary()
        assert result.ok
        assert resolved == "/abs/fieldnotes"
        assert "/abs/fieldnotes" in result.detail

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr("fieldnotes.doctor.shutil.which", lambda _: None)
        result, resolved = check_binary()
        assert not result.ok
        assert resolved is None
        assert result.fix is not None


class TestPackageCheck:
    def test_reports_version(self):
        result = check_package()
        assert result.ok
        assert "fieldnotes" in result.detail


class TestHooksCheck:
    def test_settings_missing(self, tmp_path: Path):
        results = check_hooks(tmp_path / "missing.json", "/abs/fieldnotes")
        assert len(results) == 1
        assert not results[0].ok
        assert "does not exist" in results[0].detail

    def test_settings_malformed(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        target.write_text("{ not json")
        results = check_hooks(target, "/abs/fieldnotes")
        assert len(results) == 1
        assert not results[0].ok
        assert "could not parse" in results[0].detail

    def test_no_fieldnotes_hooks(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        target.write_text(json.dumps({"hooks": {"SessionEnd": []}}))
        results = check_hooks(target, "/abs/fieldnotes")
        assert all(not r.ok for r in results)
        names = [r.name for r in results]
        assert "SessionStart hook" in names
        assert "PostToolUse hook" in names

    def test_correctly_wired(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        target.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "/abs/fieldnotes brief 2>/dev/null || true",
                                    }
                                ],
                            }
                        ],
                        "PostToolUse": [
                            {
                                "matcher": "Edit|Write|MultiEdit",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "/abs/fieldnotes touched --stdin 2>/dev/null || true",
                                    }
                                ],
                            }
                        ],
                    }
                }
            )
        )
        results = check_hooks(target, "/abs/fieldnotes")
        assert all(r.ok for r in results), [(r.name, r.detail) for r in results]

    def test_wrong_binary_path(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        target.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "/old/path/fieldnotes brief 2>/dev/null || true",
                                    }
                                ],
                            }
                        ],
                        "PostToolUse": [
                            {
                                "matcher": "Edit|Write|MultiEdit",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "/old/path/fieldnotes touched --stdin 2>/dev/null || true",
                                    }
                                ],
                            }
                        ],
                    }
                }
            )
        )
        results = check_hooks(target, "/new/path/fieldnotes")
        assert all(not r.ok for r in results)
        assert any("expected" in r.detail for r in results)

    def test_relative_binary_accepted_when_no_expected(self, tmp_path: Path):
        target = tmp_path / "settings.json"
        target.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "fieldnotes brief 2>/dev/null || true",
                                    }
                                ],
                            }
                        ],
                        "PostToolUse": [
                            {
                                "matcher": "Edit|Write|MultiEdit",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "fieldnotes touched --stdin 2>/dev/null || true",
                                    }
                                ],
                            }
                        ],
                    }
                }
            )
        )
        # When binary is not on PATH, we have no expected — accept either form.
        results = check_hooks(target, None)
        assert all(r.ok for r in results)


class TestCwdRepoCheck:
    def test_no_repo(self, tmp_path: Path):
        result = check_cwd_repo(tmp_path)
        assert not result.ok

    def test_with_repo(self, repo: Path):
        result = check_cwd_repo(repo)
        assert result.ok
        assert "0 notes" in result.detail or "0 note" in result.detail


class TestRunDiagnostics:
    def test_returns_report(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("fieldnotes.doctor.shutil.which", lambda _: "/abs/fieldnotes")
        report = run_diagnostics(
            settings_path=tmp_path / "missing.json",
            cwd=tmp_path,
        )
        # Several checks should run.
        assert len(report.checks) >= 4
        # Without settings + without .fieldnotes/, all_ok is False.
        assert not report.all_ok


class TestGitHookCheck:
    def test_none_when_not_a_fieldnotes_repo(self, tmp_path: Path):
        assert check_git_hook(tmp_path) is None

    def test_none_when_repo_is_not_a_git_repo(self, repo: Path):
        # `repo` has .fieldnotes/ but no git — the gate doesn't apply.
        assert check_git_hook(repo) is None

    def test_not_ok_when_hook_missing(self, git_repo: Path):
        result = check_git_hook(git_repo)
        assert result is not None
        assert not result.ok
        assert result.fix is not None

    def test_ok_when_hook_installed(self, git_repo: Path):
        install_git_hook(git_repo, "/abs/fieldnotes")
        result = check_git_hook(git_repo)
        assert result is not None
        assert result.ok
