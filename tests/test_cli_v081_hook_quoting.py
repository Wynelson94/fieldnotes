"""Tests for v0.8.1: the Claude Code hook snippet must shell-quote the binary path.

`install-hooks` bakes the absolute path from `shutil.which` into the hook
command. Unquoted, a path with a space produces a hook that fails on every
trigger — silently, because the commands end in `|| true`.
"""

from __future__ import annotations

import shlex

from fieldnotes.cli import _build_hook_snippet


def _commands(snippet: dict) -> list[str]:
    return [
        hook["command"]
        for entries in snippet["hooks"].values()
        for entry in entries
        for hook in entry["hooks"]
    ]


class TestHookSnippetQuoting:
    def test_spaced_binary_stays_one_shell_word(self):
        snippet = _build_hook_snippet("/Users/some user/bin/fieldnotes")
        for cmd in _commands(snippet):
            assert shlex.split(cmd)[0] == "/Users/some user/bin/fieldnotes"

    def test_plain_binary_command_is_unchanged(self):
        # Quoting a clean path is a no-op, so hooks already applied to
        # settings.json still dedupe against a freshly built snippet.
        snippet = _build_hook_snippet("fieldnotes")
        cmds = _commands(snippet)
        assert "fieldnotes brief 2>/dev/null || true" in cmds
        assert "fieldnotes touched --stdin 2>/dev/null || true" in cmds

    def test_absolute_plain_binary_command_is_unchanged(self):
        snippet = _build_hook_snippet("/usr/local/bin/fieldnotes")
        cmds = _commands(snippet)
        assert "/usr/local/bin/fieldnotes brief 2>/dev/null || true" in cmds
