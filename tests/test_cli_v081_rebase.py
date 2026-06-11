"""Tests for v0.8.1: `verify --rebase` implies `--update`.

Before this, `--rebase` was only honored alongside `--update`; alone it
listed stale notes and exited 0 without touching anything — a silent no-op.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
from typer.testing import CliRunner

from fieldnotes.cli import app

runner = CliRunner()


def _pinned_lines(repo: Path) -> list[int]:
    note = next((repo / ".fieldnotes" / "notes").glob("0001-*.md"))
    (ref,) = frontmatter.load(note)["references"]
    return ref["lines"]


class TestRebaseImpliesUpdate:
    def test_rebase_alone_relocates_and_repins(self, repo: Path):
        (repo / "f.py").write_text("# header\ndef f():\n    return 1\n")
        result = runner.invoke(
            app,
            [
                "add",
                "--topic", "t", "--title", "T", "--body", "b",
                "--refs", "f.py:2-3",
                "--repo", str(repo),
            ],
        )
        assert result.exit_code == 0, result.output

        # Shift the pinned block down without changing it.
        (repo / "f.py").write_text("# new line\n# header\ndef f():\n    return 1\n")

        result = runner.invoke(app, ["verify", "--rebase", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
        assert _pinned_lines(repo) == [3, 4]

        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 0, result.output
