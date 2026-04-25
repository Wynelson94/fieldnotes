---
confidence: high
id: '0002'
references:
- lines: null
  path: fieldnotes/verify.py
  sha: e840761f68642a1c137aabae3bf3ac576bd8a6b074238dba6424fb27734c431a
  symbol: null
- lines: null
  path: fieldnotes/models.py
  sha: 94b9ffbd89d7bacab4926b4602ecccc6c5277e844a1267586366b8a7d43ff2d8
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
