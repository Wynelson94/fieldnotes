---
confidence: high
id: '0001'
references:
- advisory: false
  lines: null
  path: fieldnotes/cli.py
  pinned_at: '2026-06-11T17:54:48.146743Z'
  sha: 9795ceaa2f8725d2e43a17a9b6a2f0a4c7bf6aa85ee05aea3b6b6ad67a016b28
  symbol: null
- advisory: true
  lines: null
  path: pyproject.toml
  pinned_at: '2026-06-11T17:54:48.146905Z'
  sha: 22f857f72d55eb42572bafb48ecff0b4e8e831d59279fbf848db154ea9eed67a
  symbol: null
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
