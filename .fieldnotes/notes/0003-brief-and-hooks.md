---
confidence: high
id: '0003'
references:
- advisory: false
  lines: null
  path: fieldnotes/brief.py
  pinned_at: null
  sha: 5f62b9820cec3521eedb9cecc5345238b3098e60c19f881f5955b22c8bdcc7ea
  symbol: null
- advisory: false
  lines: null
  path: fieldnotes/cli.py
  pinned_at: '2026-06-11T18:27:34.000198Z'
  sha: eb1f86a0f243b481ddf621b8b32ae143f59e60e28caabed922f55b5eab24c5ff
  symbol: null
session_id: null
superseded_by: null
supersedes: null
tags:
- brief
- hooks
- claude-code
- session-start
title: How `brief` is meant to be wired (SessionStart hook)
topic: brief-and-hooks
validations:
- at: '2026-06-11T18:30:02.628664Z'
  by: claude-fable-5
written_at: '2026-04-25T04:08:18.868077Z'
written_by: claude-opus-4-7
---

# How `brief` is meant to be wired

`fieldnotes brief` is designed to be run at the start of every Claude Code session. It walks up from cwd looking for `.fieldnotes/`. If nothing is found, it exits silently with code 0 — safe to wire in unconditionally.

When it does find a `.fieldnotes/`, it prints a compact summary: total note count, any stale notes, notes that reference recently-changed files (uncommitted + last 5 commits, via `git status --porcelain` and `git log --name-only`), and — v0.11 — at most one coverage-gap line when a file has churned ≥5 commits with no notes.

v0.11 added a third sibling: `fieldnotes handoff` on the **Stop** hook closes the loop at session end (changed files vs notes, with an explicit record-or-decline ask). All three commands share the same contract: silent with exit 0 whenever there is nothing to say, so they are safe to wire unconditionally. `install-hooks --apply` writes all three; `doctor` checks all three.

To wire as a Claude Code SessionStart hook, add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "fieldnotes brief 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

The `2>/dev/null || true` belt-and-suspenders ensures the hook never fails the session start, even if `fieldnotes` isn't installed in the environment Claude Code spawns from.

**Implementation note:** the recent-paths logic uses `git log -N --name-only --pretty=format:` rather than `git diff HEAD~N..HEAD` — the diff form fails when there are fewer than N ancestors (one-commit repos), and `log -N` degrades gracefully. See `fieldnotes/brief.py:recent_git_paths`.
