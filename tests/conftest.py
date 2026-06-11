"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A scratch repo root with a .fieldnotes/ directory already initialized."""
    from fieldnotes.store import init_repo

    init_repo(tmp_path)
    return tmp_path


@pytest.fixture()
def sample_source(tmp_path: Path) -> Path:
    """A sample source file inside the repo for SHA-pinning tests."""
    p = tmp_path / "src" / "thing.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("def thing():\n    return 42\n")
    return p


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """A scratch repo: a real `git init` plus an initialized .fieldnotes/."""
    import subprocess

    from fieldnotes.store import init_repo

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    init_repo(tmp_path)
    return tmp_path
