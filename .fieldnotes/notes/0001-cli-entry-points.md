---
confidence: high
id: '0001'
references:
- advisory: false
  lines: null
  path: fieldnotes/cli.py
  pinned_at: '2026-06-11T18:27:33.999560Z'
  sha: eb1f86a0f243b481ddf621b8b32ae143f59e60e28caabed922f55b5eab24c5ff
  symbol: null
- advisory: true
  lines: null
  path: pyproject.toml
  pinned_at: '2026-06-11T18:29:40.415473Z'
  sha: 109e00b95ed89c636017ab4fd19ea50af2b963bb1ef5564b21c9fbb4c31bab07
  symbol: null
session_id: null
superseded_by: null
supersedes: null
tags:
- cli
- typer
title: How the fieldnotes CLI is wired
topic: cli-entry-points
validations:
- at: '2026-06-11T18:30:02.420910Z'
  by: claude-fable-5
written_at: '2026-04-25T03:51:37.089950Z'
written_by: claude-opus-4-7
---

The Typer 'app' is defined at fieldnotes/cli.py and exposed as a console script via [project.scripts] in pyproject.toml: fieldnotes = 'fieldnotes.cli:app'. All commands take an optional --repo flag; without it, _resolve_repo walks up from cwd looking for a .fieldnotes/ directory.
