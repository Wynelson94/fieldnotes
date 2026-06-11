"""Tests for v0.9.0 safe `verify --update`.

- `--update` rebases moved line-range pins by default (`--no-rebase` opts out).
- Re-pinning content that *changed* (rather than moved) prints a review block
  telling the reader which notes to re-read — re-pinning fixes the SHA, not
  the claim.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
from typer.testing import CliRunner

from fieldnotes.cli import app

runner = CliRunner()


def _add(repo: Path, refs: str, topic: str = "t", title: str = "T") -> None:
    result = runner.invoke(
        app,
        [
            "add",
            "--topic",
            topic,
            "--title",
            title,
            "--body",
            "b",
            "--refs",
            refs,
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output


def _pinned_lines(repo: Path, glob: str = "0001-*.md") -> list[int]:
    note = next((repo / ".fieldnotes" / "notes").glob(glob))
    (ref,) = frontmatter.load(note)["references"]
    return ref["lines"]


class TestUpdateRebasesByDefault:
    def test_update_alone_relocates_moved_block(self, repo: Path):
        (repo / "f.py").write_text("# header\ndef f():\n    return 1\n")
        _add(repo, "f.py:2-3")
        (repo / "f.py").write_text("# new line\n# header\ndef f():\n    return 1\n")

        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert _pinned_lines(repo) == [3, 4]

    def test_no_rebase_repins_in_place(self, repo: Path):
        (repo / "f.py").write_text("# header\ndef f():\n    return 1\n")
        _add(repo, "f.py:2-3")
        (repo / "f.py").write_text("# new line\n# header\ndef f():\n    return 1\n")

        result = runner.invoke(app, ["verify", "--update", "--no-rebase", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert _pinned_lines(repo) == [2, 3]


class TestClaimCheckReport:
    def test_changed_whole_file_pin_asks_for_a_reread(self, repo: Path):
        (repo / "f.py").write_text("x = 1\n")
        _add(repo, "f.py", topic="claims", title="Claims about f")
        (repo / "f.py").write_text("x = 2\n")

        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "re-read" in result.output
        assert "claims" in result.output
        assert "f.py" in result.output

    def test_moved_block_does_not_ask_for_a_reread(self, repo: Path):
        (repo / "f.py").write_text("# header\ndef f():\n    return 1\n")
        _add(repo, "f.py:2-3")
        (repo / "f.py").write_text("# new line\n# header\ndef f():\n    return 1\n")

        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "re-read" not in result.output

    def test_clean_repo_prints_no_review_block(self, repo: Path):
        (repo / "f.py").write_text("x = 1\n")
        _add(repo, "f.py")
        result = runner.invoke(app, ["verify", "--update", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert "re-read" not in result.output
