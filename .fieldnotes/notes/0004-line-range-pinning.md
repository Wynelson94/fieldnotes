---
confidence: high
id: '0004'
references:
- lines:
  - 221
  - 245
  path: fieldnotes/cli.py
  pinned_at: null
  sha: 848fac0c5cacc9a488f99e67fe36f00f9c91dfbfcf6e20469e9aee18d8403adf
  symbol: null
- lines:
  - 51
  - 68
  path: fieldnotes/verify.py
  pinned_at: null
  sha: 4ba12faa5073abcafabe209d8e94fc5aa91905f6ea17d3f1a777b68e7b13861b
  symbol: null
session_id: null
superseded_by: '0006'
supersedes: null
tags:
- lines
- pinning
- verify
- precision
title: Why --refs supports path:N-M syntax
topic: line-range-pinning
written_at: '2026-04-25T04:39:01.093859Z'
written_by: claude-opus-4-7
---

When a fieldnote documents a single function or block, the right granularity is the lines it actually describes — not the whole file. fieldnotes/cli.py:_parse_ref_spec turns 'path:42' into [42,42] and 'path:12-84' into [12,84]; verify.compute_range_sha hashes only that slice. A note pinned to a function survives unrelated edits elsewhere in the file.
