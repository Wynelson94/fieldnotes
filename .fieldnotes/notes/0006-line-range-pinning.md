---
confidence: high
id: '0006'
references:
- advisory: false
  lines:
  - 319
  - 352
  path: fieldnotes/cli.py
  pinned_at: null
  sha: 9d8fde0b8d94183e2994a4663718b6425991632414e36e04cb2c35be0e37c9df
  symbol: null
- advisory: false
  lines:
  - 63
  - 82
  path: fieldnotes/verify.py
  pinned_at: null
  sha: 05e5204641225a00be6f1f9daa7d3533c3741bc24a7a9939da2ea70e434eb352
  symbol: null
session_id: null
superseded_by: '0007'
supersedes: '0004'
tags:
- lines
- pinning
- verify
- precision
title: Why --refs supports path:N-M syntax
topic: line-range-pinning
validations:
- at: '2026-06-11T18:30:02.945954Z'
  by: claude-fable-5
written_at: '2026-04-26T00:16:37.430108Z'
written_by: claude-opus-4-7
---

When a fieldnote documents a single function or block, the right granularity is the lines it actually describes — not the whole file. `fieldnotes/cli.py:_parse_ref_spec` turns 'path:42' into [42,42] and 'path:12-84' into [12,84]; `compute_range_sha` in `verify.py` hashes only that slice. Edits outside the range don't invalidate; edits inside do.

This note is line-range-pinned to dogfood the feature it documents. Caveat: line-range pins are brittle to refactors that move the documented block — the line numbers don't track the moved code. v0.5 added **symbol pinning** (see 0005) which re-resolves the symbol on each verify; that's the better default for any pin pointing at named code. Use line-range pinning for things without resolvable symbols (config sections, markdown, snippet excerpts, non-Python source).
