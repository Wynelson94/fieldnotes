# Changelog

## 0.9.0 — 2026-06-11

Staleness you can trust and explain. Re-pinning a stale note fixes the SHA but not the claim — this release makes the gap between those two visible, and stops the tool from letting you do the wrong thing the easy way. Shaped by real usage: 76 notes across 7 repos, 47% stale, and the staleness almost perfectly predicted by whether the pre-commit gate was installed.

- **`fieldnotes diff <id-or-topic>`** — show what changed under a note's pins since they were pinned: per-reference git diff from the last commit before the pin time to the working tree (uncommitted drift included). Turns "stale" from a flag into something a reader can act on. New `Reference.pinned_at` field stamps the pin time (restamped only when a re-pin actually changes the SHA, preserved across rebases; older notes fall back to `written_at`).
- **`verify --update` is now safe by default.** Moved line-range pins rebase automatically — no `--rebase` flag needed (`--no-rebase` opts out). And when a re-pin covers content that *changed* rather than moved, the CLI prints a review block naming the notes whose prose needs a re-read. Previously `--update` silently re-pinned shifted content in place; the bug that motivated this bit the author mid-audit.
- **Advisory references.** `add --advisory-refs path` (or `advisory: true` on a draft ref) pins a file for context without its drift ever making the note stale: no gate block, no stale listing, no re-read nag. `verify --update` still refreshes the pin quietly. For volatile files — the motivating case was a pyproject.toml pin going stale on every version bump.
- **Gate-adoption nudge.** `verify` and `brief` print one dim tip when the repo is git but the pre-commit gate isn't installed. Never in `--check`/`--quiet`/`--json` paths, so hooks and CI stay silent. In the wild, gated repos hold <20% stale; ungated drift to 50–100%.
- 267 tests, ruff clean.

## 0.8.1 — 2026-06-11

Audit release: three silent-failure bugs found in a code audit, all fixed with tests.

- **`install-hooks` now shell-quotes the binary path it bakes into the Claude Code hook commands.** Previously the absolute path from `shutil.which` went in unquoted — a path containing a space produced `brief`/`touched` hooks that failed on every trigger, silently, behind the trailing `|| true`. Quoting a clean path is a no-op, so hooks already applied to `settings.json` still dedupe on re-apply.
- **The git pre-commit gate script quotes its binary path with `shlex.quote`** instead of hand-placed single quotes, which broke on a path containing a single quote. Re-running `install-git-hook` (or `init`) refreshes an existing gate in place.
- **`verify --rebase` now implies `--update`.** Alone it used to list stale notes and exit 0 without relocating anything — a silent no-op (the flag was only honored alongside `--update`). Relocating without re-pinning has no meaning, so the flag now does what it says on its own.
- Repo-wide `ruff format` pass; no behavior change.
- 237 tests, ruff clean.

## 0.8.0 — 2026-05-19

The git pre-commit gate. The Claude Code hooks (`brief`, `touched`) *notify* about drift — they never *enforce* it, so a note silently goes stale the moment a commit changes a file it pins without the note being updated. This release closes that hole: fieldnotes can now install a git `pre-commit` hook that turns drift into a hard stop at commit time.

- `fieldnotes install-git-hook`: installs a `pre-commit` hook into the repo's git hooks directory (honoring `core.hooksPath`). The hook runs `verify --check` and blocks the commit when any note is stale. Idempotent; never overwrites a pre-commit hook fieldnotes didn't write — it reports the foreign hook and prints the one line to add manually.
- `fieldnotes init` now installs the gate automatically, so every repo that adopts fieldnotes is protected from the first commit. `--no-git-hook` opts out; non-git targets are skipped silently.
- `verify --check`: exit non-zero when any note is stale — for git hooks and CI. `verify --quiet`: suppress the all-clear line while still reporting drift. The generated hook uses `verify --check --quiet`, so a clean commit is silent and a stale one shows exactly what drifted.
- `fieldnotes doctor` now reports whether the pre-commit gate is wired for the current repo, with a fix line.
- New module `fieldnotes/githook.py` — `effective_hooks_dir`, `build_hook_script`, `install_git_hook`, `git_hook_installed`. Used by the CLI and tests.
- The hook degrades safely: contributors and CI without fieldnotes installed are never blocked, and repos without `.fieldnotes/` are ignored.
- `__init__.py` version is back in sync (0.7.1 shipped with it still reading 0.7.0).
- 231 tests, ruff clean.

## 0.7.1 — 2026-04-30

Two pin-safety bugs surfaced when a Claude session used fieldnotes on a TypeScript-heavy repo. Both fixed; both have tests.

- **Symbol pin on a non-Python file no longer marks the ref perpetually stale.** v0.5 documented symbols as Python-only, but `add --refs path.ts:fnName` would warn ("could not resolve") then *persist* the symbol field anyway. Every subsequent `verify` would re-attempt resolution, fail, and flag the ref stale — so a fresh note was born stale and `verify --update` couldn't fix it. Now the symbol is dropped at write time when the target's suffix isn't `.py`; the ref pins to the whole file with a clear warning. Python symbol typos still persist (intentional — that's the staleness signal you want for typos).
- **Directory refs no longer persist a broken Reference.** Previously, `--refs supabase/migrations` would compute a null SHA, store it, and show "missing" on every verify forever. Now the CLI prints `is a directory; pin a specific file (skipped)` and drops the ref from the note. Other refs in the same `add` command continue normally.
- Both fixes apply to `--from draft.md` as well, not just `--refs` flags.
- 197 tests, ruff clean.

## 0.7.0 — 2026-04-25

Line-range pins now self-heal when code moves. The drift-recovery story for line-range pins (from v0.4) was: "you have to re-pin manually." That was a real friction point — when a refactor pushes a documented block down by N lines, plain `--update` would lock the original line range to a SHA of unrelated content. v0.7 fixes that.

- `verify --update --rebase`: stale line-range pins try to re-locate their original content elsewhere in the file by SHA. Match found → both `lines` and `sha` update (SHA stays identical, just lines shift). No match → falls back to in-place re-pin with a `warning:` line so you know content truly drifted.
- New `fieldnotes/verify.py:find_moved_range(path, target_sha, range_size)` — slides a windowed SHA over the file. Pure function, used by both the CLI and tests.
- New `RebaseResult` dataclass surfaces per-ref outcomes (`rebased` | `ambiguous` | `no_match`) so the CLI can report what happened.
- Symbol-pinned and whole-file pins are unaffected — they already self-heal or don't apply.
- PyPI distribution name is `claude-fieldnotes` (the unprefixed `fieldnotes` is taken). CLI binary and import path are unchanged.
- 192 tests, ruff clean.

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
