---
confidence: high
id: '0001'
references:
- lines: null
  path: fieldnotes/cli.py
  sha: 0aaa33bbc06b8c6d510e85d29b17eac6261e8add90f91ad29d227106caf935ac
  symbol: null
- lines: null
  path: pyproject.toml
  sha: 705101ed740471f9cc5291efe539014cd581416baf83043c8c283e680e100ea4
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
