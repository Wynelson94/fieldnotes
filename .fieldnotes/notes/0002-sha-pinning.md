---
confidence: high
id: '0002'
references:
- lines: null
  path: fieldnotes/verify.py
  sha: 4f6b6755e2ec3753cacf10bc170c6fde43af76f0e8a6918f3f6f37c58b16ffbc
- lines: null
  path: fieldnotes/models.py
  sha: 462aefd1ad660c5aec057da550126baa66309192bc2dce213f31fcdf3703e214
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
