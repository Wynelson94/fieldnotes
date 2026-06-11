"""Tests for the Typer CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fieldnotes.cli import app
from fieldnotes.store import index_path, notes_dir

runner = CliRunner()


def _run(*args: str, repo: Path | None = None):
    full = list(args)
    if repo is not None:
        full += ["--repo", str(repo)]
    return runner.invoke(app, full)


class TestInit:
    def test_init_creates_scaffold(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".fieldnotes").is_dir()
        assert notes_dir(tmp_path).exists()

    def test_init_default_cwd(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".fieldnotes").is_dir()


class TestAddAndGet:
    def test_add_writes_note_and_index(self, repo: Path):
        result = _run(
            "add",
            "--topic",
            "cli-entry-points",
            "--title",
            "How the CLI is wired",
            "--body",
            "The CLI is in fieldnotes/cli.py",
            "--tags",
            "cli,typer",
            "--confidence",
            "high",
            "--written-by",
            "claude-opus-4-7",
            repo=repo,
        )
        assert result.exit_code == 0, result.output
        files = list(notes_dir(repo).iterdir())
        assert any(f.name == "0001-cli-entry-points.md" for f in files)
        idx = index_path(repo).read_text()
        assert "How the CLI is wired" in idx
        assert "No notes yet" not in idx

    def test_get_by_id_and_by_topic(self, repo: Path):
        _run(
            "add",
            "--topic",
            "x",
            "--title",
            "Hello",
            "--body",
            "world content",
            repo=repo,
        )
        r1 = _run("get", "1", repo=repo)
        r2 = _run("get", "x", repo=repo)
        assert r1.exit_code == 0 and r2.exit_code == 0
        assert "world content" in r1.output
        assert "world content" in r2.output

    def test_add_with_refs_pins_sha(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        result = _run(
            "add",
            "--topic",
            "ref-test",
            "--title",
            "Ref test",
            "--body",
            "body",
            "--refs",
            rel,
            repo=repo,
        )
        assert result.exit_code == 0, result.output
        # The note file should mention the source path.
        content = (notes_dir(repo) / "0001-ref-test.md").read_text()
        assert rel in content

    def test_add_body_from_stdin(self, repo: Path):
        result = runner.invoke(
            app,
            ["add", "--topic", "x", "--title", "T", "--body", "-", "--repo", str(repo)],
            input="from stdin\n",
        )
        assert result.exit_code == 0, result.output
        text = (notes_dir(repo) / "0001-x.md").read_text()
        assert "from stdin" in text


class TestList:
    def test_empty(self, repo: Path):
        result = _run("list", repo=repo)
        assert result.exit_code == 0
        assert "no notes match" in result.output.lower()

    def test_lists_table(self, repo: Path):
        _run("add", "--topic", "a", "--title", "A", "--body", "b", repo=repo)
        _run("add", "--topic", "b", "--title", "B", "--body", "b", repo=repo)
        result = _run("list", repo=repo)
        assert result.exit_code == 0
        assert "0001" in result.output and "0002" in result.output

    def test_filter_by_tag(self, repo: Path):
        _run("add", "--topic", "a", "--title", "A", "--body", "b", "--tags", "x", repo=repo)
        _run("add", "--topic", "b", "--title", "B", "--body", "b", "--tags", "y", repo=repo)
        result = _run("list", "--tag", "x", repo=repo)
        assert "0001" in result.output and "0002" not in result.output

    def test_json_out(self, repo: Path):
        _run("add", "--topic", "a", "--title", "A", "--body", "b", repo=repo)
        result = _run("list", "--json", repo=repo)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["id"] == "0001"


class TestVerify:
    def test_clean_passes(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        _run("add", "--topic", "x", "--title", "X", "--body", "b", "--refs", rel, repo=repo)
        result = _run("verify", repo=repo)
        assert result.exit_code == 0
        assert "verified" in result.output

    def test_detects_drift(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        _run("add", "--topic", "x", "--title", "X", "--body", "b", "--refs", rel, repo=repo)
        sample_source.write_text("changed\n")
        result = _run("verify", repo=repo)
        assert "stale" in result.output.lower()

    def test_update_repins(self, repo: Path, sample_source: Path):
        rel = sample_source.relative_to(repo).as_posix()
        _run("add", "--topic", "x", "--title", "X", "--body", "b", "--refs", rel, repo=repo)
        sample_source.write_text("changed\n")
        r1 = _run("verify", "--update", repo=repo)
        assert r1.exit_code == 0
        r2 = _run("verify", repo=repo)
        assert "verified" in r2.output


class TestSearch:
    def test_finds_match(self, repo: Path):
        _run("add", "--topic", "x", "--title", "Event Loop Gotcha", "--body", "b", repo=repo)
        result = _run("search", "loop", repo=repo)
        assert result.exit_code == 0
        assert "Event Loop Gotcha" in result.output

    def test_no_match(self, repo: Path):
        _run("add", "--topic", "x", "--title", "T", "--body", "b", repo=repo)
        result = _run("search", "nope", repo=repo)
        assert "no matches" in result.output.lower()


class TestSupersede:
    def test_creates_new_and_marks_old(self, repo: Path):
        _run("add", "--topic", "x", "--title", "Old", "--body", "old body", repo=repo)
        result = _run(
            "supersede",
            "1",
            "--title",
            "New",
            "--body",
            "new body",
            repo=repo,
        )
        assert result.exit_code == 0, result.output
        # Two notes should exist now.
        files = sorted(p.name for p in notes_dir(repo).iterdir())
        assert any("0001" in f for f in files)
        assert any("0002" in f for f in files)
        # The old note should now declare superseded_by.
        old_text = (notes_dir(repo) / "0001-x.md").read_text()
        assert "superseded_by" in old_text and "0002" in old_text


class TestRepoNotInitialized:
    def test_friendly_error(self, tmp_path: Path):
        result = _run("list", repo=tmp_path)
        assert result.exit_code == 2
        assert ".fieldnotes" in result.output
