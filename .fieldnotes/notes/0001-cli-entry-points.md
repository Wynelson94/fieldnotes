---
confidence: high
id: '0001'
references:
- lines: null
  path: fieldnotes/cli.py
  sha: c25dcd518de9fbadc4c8505ff9a0f4dad2bb69ab8624fbe684e31ebebe80bbc3
  symbol: null
- lines: null
  path: pyproject.toml
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
