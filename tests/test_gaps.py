"""Tests for v0.11.0 `fieldnotes gaps` — absence becomes a measurable.

The gate catches a note going stale; nothing catches a note never written.
gaps crosses git churn with note coverage so the hottest undocumented files
are a number you can look at, not a feeling.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.gaps import churn_map, coverage_paths

runner = CliRunner()


def _commit(repo: Path, path: str, content: str, msg: str) -> None:
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", msg], cwd=repo, check=True)


def _seed_history(repo: Path) -> None:
    """hot.py churns 3×, cool.py once; hot.py has no note, cool.py does."""
    _commit(repo, "hot.py", "v1\n", "c1")
    _commit(repo, "cool.py", "x\n", "c2")
    _commit(repo, "hot.py", "v2\n", "c3")
    _commit(repo, "hot.py", "v3\n", "c4")
    result = runner.invoke(
        app,
        [
            "add",
            "--topic",
            "cool",
            "--title",
            "About cool",
            "--body",
            "b",
            "--refs",
            "cool.py",
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


class TestChurnAndCoverage:
    def test_churn_counts_commits_per_path(self, git_repo: Path):
        _seed_history(git_repo)
        churn = churn_map(git_repo, since="90 days ago")
        assert churn["hot.py"] == 3
        assert churn["cool.py"] == 1

    def test_churn_excludes_fieldnotes_dir(self, git_repo: Path):
        _seed_history(git_repo)
        _commit(git_repo, "z.py", "x\n", "note commit picks up .fieldnotes too")
        churn = churn_map(git_repo, since="90 days ago")
        assert not any(p.startswith(".fieldnotes") for p in churn)

    def test_churn_skips_deleted_files(self, git_repo: Path):
        _seed_history(git_repo)
        (git_repo / "hot.py").unlink()
        subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-qm", "rm"], cwd=git_repo, check=True)
        churn = churn_map(git_repo, since="90 days ago")
        assert "hot.py" not in churn

    def test_coverage_paths(self, git_repo: Path):
        _seed_history(git_repo)
        assert "cool.py" in coverage_paths(git_repo)
        assert "hot.py" not in coverage_paths(git_repo)


class TestGapsCommand:
    def test_ranks_uncovered_by_churn(self, git_repo: Path):
        _seed_history(git_repo)
        result = runner.invoke(app, ["gaps", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "hot.py" in result.output
        assert "cool.py" not in result.output  # covered — not a gap

    def test_json_output(self, git_repo: Path):
        _seed_history(git_repo)
        result = runner.invoke(app, ["gaps", "--json", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert '"hot.py"' in result.output

    def test_non_git_repo_is_graceful(self, repo: Path):
        result = runner.invoke(app, ["gaps", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "git" in result.output.lower()


class TestBriefCoverageLine:
    def test_brief_flags_hot_uncovered_file(self, git_repo: Path):
        _seed_history(git_repo)
        # Push hot.py past the >=5 commit threshold.
        _commit(git_repo, "hot.py", "v4\n", "c5")
        _commit(git_repo, "hot.py", "v5\n", "c6")
        result = runner.invoke(app, ["brief", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "coverage gap" in result.output
        assert "hot.py" in result.output

    def test_brief_silent_below_threshold(self, git_repo: Path):
        _seed_history(git_repo)  # hot.py at 3 commits — under threshold
        result = runner.invoke(app, ["brief", "--repo", str(git_repo)])
        assert result.exit_code == 0, result.output
        assert "coverage gap" not in result.output
