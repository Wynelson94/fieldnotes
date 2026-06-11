---
confidence: high
id: '0005'
references:
- advisory: false
  lines:
  - 27
  - 42
  path: fieldnotes/symbols.py
  pinned_at: '2026-06-11T17:54:48.147758Z'
  sha: 4e03c2086324d7fb62be7553ba1c5d75550df2a9a74224c2966ab7924d6613b9
  symbol: resolve_symbol
- advisory: false
  lines:
  - 90
  - 118
  path: fieldnotes/verify.py
  pinned_at: null
  sha: 9fbe540df1726f19af7a41aad66b02fbdb6f3be501104e167884203f7d4f3e2b
  symbol: check_reference
- advisory: false
  lines:
  - 301
  - 332
  path: fieldnotes/cli.py
  pinned_at: null
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

Line numbers are fragile — a code formatter or an unrelated insert above the documented function shifts them all. fieldnotes/symbols.py:resolve_symbol finds a declaration by name and returns its current [start, end]; fieldnotes/verify.py:check_reference re-resolves the symbol on every verify, so a declaration that moves but keeps its body stays 'ok'. Resolution dispatches by suffix (v0.10): Python via the ast module (dotted Cls.method walks ClassDef bodies); TS/JS via decl-regex + brace-balance scan; SQL via CREATE-block scan with $$-body handling. The non-Python resolvers are deliberately parser-free — a mis-scanned range surfaces as stale, never silently. Suffixes outside SYMBOL_SUFFIXES degrade to whole-file pinning with a warning at write time.
