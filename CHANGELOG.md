# Changelog

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
