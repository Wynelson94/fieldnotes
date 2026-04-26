---
confidence: high
id: '0003'
references:
- lines: null
  path: fieldnotes/brief.py
  sha: 5f62b9820cec3521eedb9cecc5345238b3098e60c19f881f5955b22c8bdcc7ea
  symbol: null
- lines: null
  path: fieldnotes/cli.py
  sha: 0e7c55aa043a733ba80fb04fce02b5c3c2ba2b800a430313ea1ea27d42946c8c
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
written_at: '2026-04-25T04:08:18.868077Z'
written_by: claude-opus-4-7
---

# How `brief` is meant to be wired

`fieldnotes brief` is designed to be run at the start of every Claude Code session. It walks up from cwd looking for `.fieldnotes/`. If nothing is found, it exits silently with code 0 — safe to wire in unconditionally.

When it does find a `.fieldnotes/`, it prints a compact summary: total note count, any stale notes, and notes that reference recently-changed files (uncommitted + last 5 commits, via `git status --porcelain` and `git log --name-only`).

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
