---
confidence: high
id: '0001'
references:
- lines: null
  path: fieldnotes/cli.py
  sha: 25e65a09565383adc71c0bb8a81b7b7293f6d911aebb8706df6bb9feca4a39a7
- lines: null
  path: pyproject.toml
  sha: 35b91433aedd04dfd6ce8c7abb1c6b6c46f24b6f1b30b3fd56426b3f3e07b3f8
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
