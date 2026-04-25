# Changelog

## 0.4.0 — 2026-04-24

Line-range pinning. A note can pin to just the lines it documents, so unrelated edits elsewhere in the file don't falsely flag it stale.

- `--refs path/to/file.py:12-84` pins SHA over lines 12–84 (1-indexed, inclusive). `:42` pins a single line.
- `verify.compute_range_sha` slices the file to the pinned range before hashing. When `lines` is null, behaves exactly as v0.3 (whole-file SHA).
- `Reference.lines` now strictly validated: must be `[start, end]` with `1 <= start <= end`. Tightened from any-positive-list.
- `--from` drafts: when a reference's frontmatter sets `lines: [start, end]`, the SHA is pinned to that range automatically.
- 137 tests, ruff clean.

## 0.3.0 — 2026-04-24

Closes the feedback loop: notes get nudged at the moment of drift, not just at the next `verify`.

- `fieldnotes touched <path>`: quietly surface notes referencing an edited file. Reads stdin JSON for PostToolUse hook payloads via `--stdin`. Silent on no match — safe to wire unconditionally.
- `fieldnotes install-hooks`: prints the Claude Code hook snippet by default; `--apply` writes it idempotently to `~/.claude/settings.json` (preserving anything already there). `--to PATH` for non-default targets.
- README: rewrote the hooks section as "closing the loop" — SessionStart loads notes, PostToolUse maintains them.
- 116 tests, ruff clean.

## 0.2.0 — 2026-04-24

Closes the loop: fieldnotes can now show up automatically at session start.

- `fieldnotes for <path>`: list every note that references a given source file. Inverse of `--refs`.
- `fieldnotes brief`: compact session-start summary — total notes, stale count, and notes touching recently-changed files (uncommitted + last 5 git commits). Silent when no `.fieldnotes/` exists, so it's safe to wire as a Claude Code SessionStart hook.
- `fieldnotes add --from draft.md`: write a full note as a markdown+frontmatter file and pass it in, instead of assembling the seven-flag `add` invocation. `id` and `written_at` are auto-assigned.
- README: documented the `--from` authoring loop and the SessionStart hook setup.
- 100 tests, ruff clean.

## 0.1.0 — 2026-04-24

Initial release. Designed and built by Claude Opus 4.7 in a single night, after Nate said "build the tool you wish you had."

- `init`, `add`, `list`, `get`, `verify`, `stale`, `search`, `index`, `supersede` commands
- SHA-pinned references with drift detection
- Pydantic-validated note schema with YAML frontmatter
- Repo-scoped storage at `.fieldnotes/notes/`
- Auto-regenerated `INDEX.md` grouped by tag
