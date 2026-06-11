"""Tests for v0.11.0 validation ledger — `fieldnotes confirm`.

A re-pin fixes the SHA; only a reader can validate the claim. `confirm`
records that act so a note accrues visible verified-ness instead of the
re-read evaporating.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.models import Note, Validation

runner = CliRunner()


def _add(repo: Path, topic: str = "t") -> None:
    (repo / "f.py").write_text("x = 1\n")
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
            "f.py",
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


def _validations(repo: Path) -> list[dict]:
    note = next((repo / ".fieldnotes" / "notes").glob("0001-*.md"))
    return frontmatter.load(note).get("validations") or []


class TestValidationModel:
    def test_note_defaults_to_empty_ledger(self):
        n = Note(id="0001", topic="t", title="T")
        assert n.validations == []

    def test_round_trip(self):
        n = Note(
            id="0001",
            topic="t",
            title="T",
            validations=[{"at": "2026-06-11T00:00:00Z", "by": "claude-test"}],
        )
        assert isinstance(n.validations[0], Validation)
        assert n.validations[0].by == "claude-test"


class TestConfirmCommand:
    def test_confirm_appends_validation(self, repo: Path):
        _add(repo)
        result = runner.invoke(app, ["confirm", "0001", "--by", "claude-test", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        vals = _validations(repo)
        assert len(vals) == 1
        assert vals[0]["by"] == "claude-test"

    def test_confirm_accumulates(self, repo: Path):
        _add(repo)
        for _ in range(2):
            result = runner.invoke(app, ["confirm", "0001", "--repo", str(repo)])
            assert result.exit_code == 0, result.output
        assert len(_validations(repo)) == 2

    def test_confirm_refuses_stale_note(self, repo: Path):
        _add(repo)
        (repo / "f.py").write_text("x = 2\n")
        result = runner.invoke(app, ["confirm", "0001", "--repo", str(repo)])
        assert result.exit_code == 1
        assert "stale" in result.output
        assert _validations(repo) == []

    def test_confirm_by_topic(self, repo: Path):
        _add(repo, topic="my-claim")
        result = runner.invoke(app, ["confirm", "my-claim", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert len(_validations(repo)) == 1

    def test_unknown_note_exits_2(self, repo: Path):
        result = runner.invoke(app, ["confirm", "9999", "--repo", str(repo)])
        assert result.exit_code == 2


class TestLedgerDisplay:
    def test_get_shows_ledger(self, repo: Path):
        _add(repo)
        runner.invoke(app, ["confirm", "0001", "--by", "claude-test", "--repo", str(repo)])
        result = runner.invoke(app, ["get", "0001", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "validated 1×" in result.output
        assert "claude-test" in result.output

    def test_get_shows_never_revalidated(self, repo: Path):
        _add(repo)
        result = runner.invoke(app, ["get", "0001", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "never re-validated" in result.output

    def test_reread_block_mentions_confirm(self, repo: Path):
        _add(repo)
        (repo / "f.py").write_text("x = 2\n")
        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "fieldnotes confirm" in result.output
