---
confidence: high
id: '0001'
references:
- lines: null
  path: fieldnotes/cli.py
  sha: 4ce4835b64e389be568c77c5a63f3b3959318fc4dd2932cc03d9e676aab62ffd
- lines: null
  path: pyproject.toml
  sha: 6b29eca34092dc3c4edb147734a85fca10bc65416be6c00be25449bcffa38314
session_id: null
superseded_by: null
supersedes: null
tags:
- cli
- typer
title: How the fieldnotes CLI is wired
topic: cli-entry-points
written_at: '2026-04-25T03:51:37.089950Z'
written_by: claude-opus-4-7
---

The Typer 'app' is defined at fieldnotes/cli.py and exposed as a console script via [project.scripts] in pyproject.toml: fieldnotes = 'fieldnotes.cli:app'. All commands take an optional --repo flag; without it, _resolve_repo walks up from cwd looking for a .fieldnotes/ directory.
