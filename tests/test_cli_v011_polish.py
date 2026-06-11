"""Tests for v0.11.0 polish: topic hygiene, claim-attached surfacing, search reach.

- duplicate active topics warn at add time; lookup prefers the active note
  when duplicates exist and all but one are superseded
- `touched` and `for` show the claim (title + pin descriptor), not just ids
- `search` reaches topic and tags, not only title + body
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fieldnotes.cli import app

runner = CliRunner()


def _add(repo: Path, topic: str, title: str = "T", refs: str = "f.py", tags: str | None = None):
    args = [
        "add",
        "--topic",
        topic,
        "--title",
        title,
        "--body",
        "body text",
        "--refs",
        refs,
        "--repo",
        str(repo),
    ]
    if tags:
        args += ["--tags", tags]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return result


class TestTopicHygiene:
    def test_duplicate_active_topic_warns(self, repo: Path):
        (repo / "f.py").write_text("x\n")
        _add(repo, "auth-flow")
        result = _add(repo, "auth-flow")
        assert "already exists" in result.output
        assert "0001" in result.output

    def test_fresh_topic_does_not_warn(self, repo: Path):
        (repo / "f.py").write_text("x\n")
        result = _add(repo, "auth-flow")
        assert "already exists" not in result.output

    def test_lookup_prefers_active_over_superseded(self, repo: Path):
        (repo / "f.py").write_text("x\n")
        _add(repo, "auth-flow", title="Old claim")
        result = runner.invoke(
            app,
            [
                "supersede",
                "0001",
                "--title",
                "New claim",
                "--body",
                "b",
                "--repo",
                str(repo),
            ],
        )
        assert result.exit_code == 0, result.output
        # Both 0001 (superseded) and 0002 (active) carry topic auth-flow.
        result = runner.invoke(app, ["get", "auth-flow", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "New claim" in result.output


class TestClaimAttachedSurfacing:
    def test_touched_shows_title_and_descriptor(self, repo: Path):
        (repo / "f.py").write_text("def fn():\n    return 1\n")
        _add(repo, "claim", title="The function returns one", refs="f.py:1-2")
        result = runner.invoke(app, ["touched", "f.py", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "The function returns one" in result.output
        assert "lines 1-2" in result.output

    def test_for_shows_pin_descriptor(self, repo: Path):
        (repo / "f.py").write_text("def fn():\n    return 1\n")
        _add(repo, "claim", title="The function returns one", refs="f.py:1-2")
        result = runner.invoke(app, ["for", "f.py", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "lines 1-2" in result.output


class TestSearchReach:
    def test_search_matches_topic(self, repo: Path):
        (repo / "f.py").write_text("x\n")
        _add(repo, "rls-canary", title="Unrelated words")
        result = runner.invoke(app, ["search", "canary", "--json", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)

    def test_search_matches_tag(self, repo: Path):
        (repo / "f.py").write_text("x\n")
        _add(repo, "plain-topic", title="Unrelated words", tags="supabase,gotcha")
        result = runner.invoke(app, ["search", "gotcha", "--json", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)
