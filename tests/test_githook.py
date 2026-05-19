"""Tests for fieldnotes.githook — the git pre-commit drift gate."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

from fieldnotes.githook import (
    HOOK_MARKER,
    build_hook_script,
    effective_hooks_dir,
    git_hook_installed,
    git_toplevel,
    hook_is_ours,
    install_git_hook,
)


class TestGitToplevel:
    def test_returns_root_for_git_repo(self, git_repo: Path):
        assert git_toplevel(git_repo) == git_repo.resolve()

    def test_none_for_non_git_dir(self, tmp_path: Path):
        assert git_toplevel(tmp_path) is None


class TestEffectiveHooksDir:
    def test_default_is_dot_git_hooks(self, git_repo: Path):
        d = effective_hooks_dir(git_repo)
        assert d.name == "hooks"
        assert d.parent.name == ".git"

    def test_honors_core_hookspath(self, git_repo: Path):
        subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=git_repo,
            check=True,
        )
        assert effective_hooks_dir(git_repo) == git_repo / ".githooks"


class TestBuildHookScript:
    def test_contains_marker_binary_and_check(self):
        script = build_hook_script("/abs/fieldnotes")
        assert script.startswith("#!")
        assert HOOK_MARKER in script
        assert "/abs/fieldnotes" in script
        assert "verify --check" in script


class TestHookIsOurs:
    def test_recognizes_our_hook(self, tmp_path: Path):
        ours = tmp_path / "ours"
        ours.write_text(build_hook_script("fieldnotes"))
        assert hook_is_ours(ours)

    def test_rejects_foreign_hook(self, tmp_path: Path):
        foreign = tmp_path / "foreign"
        foreign.write_text("#!/bin/sh\necho something else\n")
        assert not hook_is_ours(foreign)

    def test_false_for_missing_file(self, tmp_path: Path):
        assert not hook_is_ours(tmp_path / "nope")


class TestInstallGitHook:
    def test_fresh_install(self, git_repo: Path):
        result = install_git_hook(git_repo, "/abs/fieldnotes")
        assert result.status == "installed"
        assert result.hook_path is not None
        assert result.hook_path.exists()
        text = result.hook_path.read_text()
        assert HOOK_MARKER in text
        assert "/abs/fieldnotes" in text
        # Hook must be executable or git won't run it.
        assert result.hook_path.stat().st_mode & stat.S_IXUSR

    def test_idempotent_rerun_is_unchanged(self, git_repo: Path):
        install_git_hook(git_repo, "/abs/fieldnotes")
        result = install_git_hook(git_repo, "/abs/fieldnotes")
        assert result.status == "unchanged"

    def test_refreshes_when_binary_changes(self, git_repo: Path):
        install_git_hook(git_repo, "/old/fieldnotes")
        result = install_git_hook(git_repo, "/new/fieldnotes")
        assert result.status == "updated"
        assert "/new/fieldnotes" in result.hook_path.read_text()

    def test_foreign_hook_not_clobbered(self, git_repo: Path):
        hooks = git_repo / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        foreign = hooks / "pre-commit"
        foreign.write_text("#!/bin/sh\necho not ours\n")
        result = install_git_hook(git_repo, "/abs/fieldnotes")
        assert result.status == "foreign"
        # The foreign hook is left exactly as it was.
        assert foreign.read_text() == "#!/bin/sh\necho not ours\n"

    def test_not_a_git_repo(self, tmp_path: Path):
        result = install_git_hook(tmp_path, "/abs/fieldnotes")
        assert result.status == "not-a-git-repo"
        assert result.hook_path is None


class TestGitHookInstalled:
    def test_false_before_install(self, git_repo: Path):
        installed, hook_path = git_hook_installed(git_repo)
        assert installed is False
        assert hook_path is not None  # path is known even when absent

    def test_true_after_install(self, git_repo: Path):
        install_git_hook(git_repo, "/abs/fieldnotes")
        installed, hook_path = git_hook_installed(git_repo)
        assert installed is True
        assert hook_path is not None

    def test_false_for_non_git_repo(self, tmp_path: Path):
        installed, hook_path = git_hook_installed(tmp_path)
        assert installed is False
        assert hook_path is None
