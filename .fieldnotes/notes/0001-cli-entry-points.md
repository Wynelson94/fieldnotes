---
confidence: high
id: '0001'
references:
- lines: null
  path: fieldnotes/cli.py
  pinned_at: '2026-06-11T17:38:52.719491Z'
  sha: c52fd65553d6dc8530e983fd73e2916fea378ce777612c762da3b7f63c79baed
  symbol: null
- lines: null
  path: pyproject.toml
  pinned_at: null
  sha: 5b4648c6aadf3edfcad2ec1249c0fac0bdad00cdd227b4ab4b839de246d0f813
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
