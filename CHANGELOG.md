# Changelog

## 0.6.0 — 2026-04-24

Make it actually live. The hook snippet was technically correct but practically broken: Claude Code hook subshells don't inherit your interactive PATH, so `fieldnotes brief` would silently fail unless you'd installed fieldnotes globally.

- `fieldnotes install-hooks --apply` now resolves the binary's absolute path via `shutil.which` and bakes it into the hook command. Same pattern Longhand uses. Refuses to apply if `fieldnotes` isn't on PATH from the resolving shell, with a clear message about installing into the framework Python.
- `--bare` flag on `install-hooks` opts back into the relative `fieldnotes` form for users who do have it globally.
- New `fieldnotes doctor` command. Reports: binary on PATH, package importable, hooks present (and pointing at the right binary), `.fieldnotes/` in cwd. Each failing check comes with a fix.
- README: rewrote the hooks section as a three-step "actually live" flow (install into framework Python → install-hooks → doctor) instead of a one-line `--apply`.
- 181 tests, ruff clean.

## 0.5.0 — 2026-04-24

Symbol pinning. `--refs path:symbol_name` is now the most resilient way to anchor a note to a function or method.

- `Reference.symbol`: optional new field. When set, `verify` re-resolves the symbol on each check via Python's `ast`, hashes its current body, and compares to the pinned sha. Functions that *move* but keep their body unchanged now stay `ok` — staleness reflects semantic change, not line-number drift.
- `--refs path/to/file.py:my_func`: top-level functions and classes. `path:Cls.method`: dotted notation walks into class bodies.
- `update_shas` re-pins both the sha *and* the lines for symbol-pinned refs, so the stored `lines` field tracks the symbol's current location.
- New module `fieldnotes/symbols.py` with `resolve_symbol(path, name)`. v0.5 is Python-only; non-Python files fall through to v0.4 line-range or v0.1 whole-file behavior.
- 165 tests, ruff clean.

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
