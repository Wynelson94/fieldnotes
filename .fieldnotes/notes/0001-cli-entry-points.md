---
confidence: high
id: '0001'
references:
- advisory: false
  lines: null
  path: fieldnotes/cli.py
  pinned_at: '2026-06-11T18:24:25.854762Z'
  sha: aaf30f02d9a7873ef6a6c557cca72ccd1d51798daa2aff45a7de8858b56c1075
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
validations: []
written_at: '2026-04-25T03:51:37.089950Z'
written_by: claude-opus-4-7
---

The Typer 'app' is defined at fieldnotes/cli.py and exposed as a console script via [project.scripts] in pyproject.toml: fieldnotes = 'fieldnotes.cli:app'. All commands take an optional --repo flag; without it, _resolve_repo walks up from cwd looking for a .fieldnotes/ directory.
