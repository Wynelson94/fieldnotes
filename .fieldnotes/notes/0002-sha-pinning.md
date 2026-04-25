---
confidence: high
id: '0002'
references:
- lines: null
  path: fieldnotes/verify.py
  sha: 43b465b92e80ddde3c2583cce254ce6f7e6a00a6f391418c325126e06f99236a
- lines: null
  path: fieldnotes/models.py
  sha: bbd0b7c54cb38f8cad6e663ec74affa5939408a38941b8d98eb621bfbdbf8749
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
