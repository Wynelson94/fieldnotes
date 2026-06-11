---
confidence: high
id: '0002'
references:
- lines: null
  path: fieldnotes/verify.py
  pinned_at: '2026-06-11T17:38:52.720009Z'
  sha: 3ec795319c02dc258b338e279bc3b888b8f0b208421c17a99c9275f5092742d4
  symbol: null
- lines: null
  path: fieldnotes/models.py
  pinned_at: '2026-06-11T17:38:52.720014Z'
  sha: efc271e1e389d6a65929f1c535f8fea9f760ab39d1621088026e2befcc3ded98
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
written_at: '2026-04-25T03:51:37.186973Z'
written_by: claude-opus-4-7
---

Each Reference stores a sha256 hex digest of its target file at write time. fieldnotes verify recomputes the sha and reports state in {ok, stale, missing, unpinned}. --update repins to current values. See fieldnotes/verify.py:check_reference.
