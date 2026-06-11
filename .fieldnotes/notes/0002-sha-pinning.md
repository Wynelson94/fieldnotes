---
confidence: high
id: '0002'
references:
- lines: null
  path: fieldnotes/verify.py
  sha: 405b4ebee350bf7560e9c7cc048c9e981ceee1f9000912c91f4c8e7375c5c0c1
  symbol: null
- lines: null
  path: fieldnotes/models.py
  sha: 409bde879e741b510ea8082a3c76123b0a51828438bca76503a8ea143c765786
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
