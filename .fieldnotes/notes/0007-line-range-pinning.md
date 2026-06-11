---
confidence: high
id: '0007'
references:
- lines:
  - 277
  - 310
  path: fieldnotes/cli.py
  sha: 9d8fde0b8d94183e2994a4663718b6425991632414e36e04cb2c35be0e37c9df
  symbol: null
- lines:
  - 57
  - 76
  path: fieldnotes/verify.py
  sha: 05e5204641225a00be6f1f9daa7d3533c3741bc24a7a9939da2ea70e434eb352
  symbol: null
session_id: null
superseded_by: null
supersedes: '0006'
tags:
- lines
- pinning
- verify
- rebase
- precision
title: Why --refs supports path:N-M syntax
topic: line-range-pinning
written_at: '2026-04-26T00:43:31.923075Z'
written_by: claude-opus-4-7
---

When a fieldnote documents a single function or block, the right granularity is the lines it actually describes — not the whole file. `fieldnotes/cli.py:_parse_ref_spec` turns 'path:42' into [42,42] and 'path:12-84' into [12,84]; `compute_range_sha` in `verify.py` hashes only that slice. Edits outside the range don't invalidate; edits inside do.

This note is line-range-pinned to dogfood the feature it documents. Two escape hatches handle the brittleness:

1. **Symbol pinning (v0.5, see 0005)** — for code with resolvable symbols (Python functions/classes), prefer `--refs path:symbol`. The symbol is re-resolved on every verify, so the pin tracks code that moved.

2. **`verify --update --rebase` (v0.7, this note's vintage)** — for line-range pins that became stale because the documented block moved within the file, --rebase content-addresses the original block by SHA, finds its new location, and updates only the line range (the SHA stays identical because the content is identical). Falls back to in-place re-pin with a warning if the content actually changed. Use this when symbol pinning isn't an option (config sections, markdown, non-Python source).
