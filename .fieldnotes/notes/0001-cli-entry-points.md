---
confidence: high
id: '0001'
references:
- advisory: false
  lines: null
  path: fieldnotes/cli.py
  pinned_at: '2026-06-11T17:44:23.276362Z'
  sha: 3833f797e56b9c007da840367a5ae0514e8e384bdc5c16cc996354e692d3b42d
  symbol: null
- advisory: true
  lines: null
  path: pyproject.toml
  pinned_at: '2026-06-11T17:46:31.869480Z'
  sha: 201063e68c3f937d56b8349371712c12d4dcbd7473cf0afdb44459a3565f6d84
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
