---
confidence: high
id: '0005'
references:
- lines:
  - 17
  - 28
  path: fieldnotes/symbols.py
  sha: 1bce5f70f4b306d463db32ba7c4692a19db0d72bb118479df912317c5c6f36ec
  symbol: resolve_symbol
- lines:
  - 84
  - 112
  path: fieldnotes/verify.py
  sha: 9fbe540df1726f19af7a41aad66b02fbdb6f3be501104e167884203f7d4f3e2b
  symbol: check_reference
- lines:
  - 277
  - 308
  path: fieldnotes/cli.py
  sha: a0f010323cfe07954ce050642400437d44c7b93e6cdaff97d16a93523fee4777
  symbol: _parse_ref_spec
session_id: null
superseded_by: null
supersedes: null
tags:
- symbols
- pinning
- ast
- verify
title: Why fieldnotes pins to symbols, not just lines
topic: symbol-pinning
written_at: '2026-04-25T04:45:32.358332Z'
written_by: claude-opus-4-7
---

Line numbers are fragile — a code formatter or an unrelated insert above the documented function shifts them all. fieldnotes/symbols.py:resolve_symbol uses Python's ast module to find a function or method by name and return its current [start, end]. fieldnotes/verify.py:check_reference re-resolves the symbol on every verify, so a function that moves but keeps its body stays 'ok'. Dotted notation (Cls.method) walks into ClassDef bodies. Non-Python files fall through and behave as v0.4 (whole-file pinning).
