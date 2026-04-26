---
confidence: high
id: '0001'
references:
- lines: null
  path: fieldnotes/cli.py
  sha: 0e7c55aa043a733ba80fb04fce02b5c3c2ba2b800a430313ea1ea27d42946c8c
  symbol: null
- lines: null
  path: pyproject.toml
  sha: eefa8217670313dae6f74655bfbca55dd4027eec699824e23bcc18025fbd805e
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
