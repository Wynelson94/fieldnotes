"""Tests for v0.9.0 advisory references — pin for context, never block.

An advisory ref keeps a file attached to a note (and visible to `for`,
`diff`, etc.) but its drift never makes the note stale: no gate block, no
stale listing, no re-read nag. Motivating case: a whole-file pin on
pyproject.toml that goes stale on every version bump.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.models import Reference

runner = CliRunner()


def _add_mixed(repo: Path) -> None:
    """One note: f.py is load-bearing, meta.toml is advisory."""
    (repo / "f.py").write_text("x = 1\n")
    (repo / "meta.toml").write_text('version = "1.0"\n')
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
            "f.py",
            "--advisory-refs",
            "meta.toml",
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


def _refs(repo: Path) -> list[dict]:
    note = next((repo / ".fieldnotes" / "notes").glob("0001-*.md"))
    return frontmatter.load(note)["references"]


class TestAdvisoryModel:
    def test_defaults_to_false(self):
        assert Reference(path="f.py").advisory is False

    def test_add_persists_advisory_flag(self, repo: Path):
        _add_mixed(repo)
        by_path = {r["path"]: r for r in _refs(repo)}
        assert by_path["f.py"]["advisory"] is False
        assert by_path["meta.toml"]["advisory"] is True
        assert by_path["meta.toml"]["sha"] is not None  # still pinned


class TestAdvisoryDriftDoesNotGate:
    def test_check_passes_when_only_advisory_drifted(self, repo: Path):
        _add_mixed(repo)
        (repo / "meta.toml").write_text('version = "2.0"\n')
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 0, result.output

    def test_check_still_fails_on_load_bearing_drift(self, repo: Path):
        _add_mixed(repo)
        (repo / "f.py").write_text("x = 2\n")
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 1, result.output

    def test_stale_listing_excludes_advisory_only_notes(self, repo: Path):
        _add_mixed(repo)
        (repo / "meta.toml").write_text('version = "2.0"\n')
        result = runner.invoke(app, ["stale", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "0001" not in result.output

    def test_plain_verify_mentions_advisory_drift_dimly(self, repo: Path):
        _add_mixed(repo)
        (repo / "meta.toml").write_text('version = "2.0"\n')
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "advisory" in result.output
        assert "meta.toml" in result.output


class TestAdvisoryUpdate:
    def test_update_repins_advisory_without_reread_nag(self, repo: Path):
        _add_mixed(repo)
        (repo / "meta.toml").write_text('version = "2.0"\n')
        old_sha = {r["path"]: r["sha"] for r in _refs(repo)}["meta.toml"]

        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "re-read" not in result.output

        new_sha = {r["path"]: r["sha"] for r in _refs(repo)}["meta.toml"]
        assert new_sha != old_sha

        # And the repo is fully quiet afterwards.
        result = runner.invoke(app, ["verify", "--repo", str(repo)])
        assert "advisory" not in result.output
