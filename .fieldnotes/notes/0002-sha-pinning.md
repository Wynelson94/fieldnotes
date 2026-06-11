---
confidence: high
id: '0002'
references:
- advisory: false
  lines: null
  path: fieldnotes/verify.py
  pinned_at: '2026-06-11T17:42:30.697414Z'
  sha: 24d3000d45232b7c543d16b5295129f578b45c6c84dc4d729a69312a9045f5d9
  symbol: null
- advisory: false
  lines: null
  path: fieldnotes/models.py
  pinned_at: '2026-06-11T18:19:09.248850Z'
  sha: 38bd65981174336b1bfc886ab80f9f54518f986dfaf6b3ce68abe41cc3c3c986
  symbol: null
session_id: null
superseded_by: null
supersedes: null
tags:
- verify
- sha
- drift
title: How drift detection works
topic: sha-pinning
validations: []
written_at: '2026-04-25T03:51:37.186973Z'
written_by: claude-opus-4-7
---

Each Reference stores a sha256 hex digest of its target file at write time. fieldnotes verify recomputes the sha and reports state in {ok, stale, missing, unpinned}. --update repins to current values. See fieldnotes/verify.py:check_reference.
