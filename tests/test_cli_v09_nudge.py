"""Tests for v0.9.0 gate-adoption nudge.

The pre-commit gate is the single biggest staleness predictor in real usage
(gated repos <20% stale, ungated 50-100%), but repos that adopted fieldnotes
before v0.8.0 never got it. `verify` and `brief` now print one dim tip when
the gate is absent — never in hook/CI paths.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.githook import install_git_hook

runner = CliRunner()

TIP = "install-git-hook"


def _add(repo: Path) -> None:
    (repo / "f.py").write_text("x = 1\n")
    result = runner.invoke(
        app,
        ["add", "--topic", "t", "--title", "T", "--body", "b", "--refs", "f.py", "--repo", str(repo)],
    )
    assert result.exit_code == 0, result.output


class TestVerifyNudge:
    def test_tip_when_gate_missing(self, git_repo: Path):
        _add(git_repo)
        result = runner.invoke(app, ["verify", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert TIP in result.output

    def test_no_tip_when_gate_installed(self, git_repo: Path):
        _add(git_repo)
        install_git_hook(git_repo, "fieldnotes")
        result = runner.invoke(app, ["verify", "--repo", str(git_repo)])
        assert TIP not in result.output

    def test_no_tip_in_check_mode(self, git_repo: Path):
        _add(git_repo)
        result = runner.invoke(app, ["verify", "--check", "--repo", str(git_repo)])
        assert TIP not in result.output

    def test_no_tip_when_quiet(self, git_repo: Path):
        _add(git_repo)
        result = runner.invoke(app, ["verify", "--quiet", "--repo", str(git_repo)])
        assert TIP not in result.output

    def test_no_tip_in_json_mode(self, git_repo: Path):
        _add(git_repo)
        result = runner.invoke(app, ["verify", "--json", "--repo", str(git_repo)])
        assert TIP not in result.output

    def test_no_tip_outside_git(self, repo: Path):
        _add(repo)
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert TIP not in result.output


class TestBriefNudge:
    def test_tip_when_gate_missing(self, git_repo: Path):
        _add(git_repo)
        result = runner.invoke(app, ["brief", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert TIP in result.output

    def test_no_tip_when_gate_installed(self, git_repo: Path):
        _add(git_repo)
        install_git_hook(git_repo, "fieldnotes")
        result = runner.invoke(app, ["brief", "--repo", str(git_repo)])
        assert TIP not in result.output
