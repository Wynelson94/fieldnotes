---
confidence: high
id: '0004'
references:
- lines:
  - 213
  - 237
  path: fieldnotes/cli.py
  sha: 700fff8626be4498a3363d8d906cf7604c1a68a848c06546579621aae93ed848
- lines:
  - 50
  - 67
  path: fieldnotes/verify.py
  sha: b1c08ee54af1f763725e0f8ebff766cc713ef0c0f421f373b6cb46d959609c81
session_id: null
superseded_by: null
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
