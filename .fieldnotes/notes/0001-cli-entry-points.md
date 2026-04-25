---
confidence: high
id: '0001'
references:
- lines: null
  path: fieldnotes/cli.py
  sha: 1bf46902ad10e611e3bfa14020268701017ff883ebcd5ad0f7886178492823d0
  symbol: null
- lines: null
  path: pyproject.toml
  sha: 10b90f2ad1997007003d5849dd681a021eca6f55bfda78c7e4157bd2c13aaf6a
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
