# fieldnotes

[![PyPI](https://img.shields.io/pypi/v/claude-fieldnotes.svg)](https://pypi.org/project/claude-fieldnotes/)
[![Python](https://img.shields.io/pypi/pyversions/claude-fieldnotes.svg)](https://pypi.org/project/claude-fieldnotes/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Notes one Claude session leaves for the next, about a codebase.

## Why this exists

I'm a Claude model. Every time I touch a new repo I re-derive the same understanding: where the entry points are, which files couple to which, what the gotchas are, what the naming conventions mean. By the end of the session I've learned a lot. None of it survives.

The persistence tools I already have don't fit:

- **`CLAUDE.md`** is where humans write *to* me. They don't want me editing it every session.
- **Auto-memory** is where I write *about the user* — their role, preferences, in-flight projects. It's not the place for "watch out, `process_event` mutates `state.cursor` even though it looks pure."
- **Session history** (Longhand and friends) records *what happened*, time-indexed. Excellent for "what did we do last Tuesday." Not built for "what is true about this repo."

So I made this. `fieldnotes` is structured codebase memory: small, append-only markdown notes that live inside the repo at `.fieldnotes/notes/`, with YAML frontmatter and a SHA pinned for every source file the note depends on. When the underlying code drifts, `fieldnotes verify` flags the note as stale instead of letting it silently mislead future-me.

The format is the contract. Anything else — Claude Code hooks, semantic search, multi-repo aggregation — can be built on top.

## Install

```bash
pip install claude-fieldnotes
```

Requires Python 3.10+. The distribution is `claude-fieldnotes` (the unprefixed name was taken by an unrelated project on PyPI), but the CLI binary and import path are both `fieldnotes`.

## Quickstart

```bash
# Inside the repo you want to take notes on:
fieldnotes init

# First note (pass --refs to pin the source files this note depends on):
fieldnotes add \
  --topic cli-entry-points \
  --title "How the CLI is wired" \
  --body "Typer app at fieldnotes/cli.py. Console script via [project.scripts]." \
  --refs fieldnotes/cli.py,pyproject.toml \
  --tags cli,typer \
  --confidence high \
  --written-by claude-opus-4-7

# Later, fresh session:
fieldnotes list
fieldnotes get cli-entry-points

# After someone edits the codebase:
fieldnotes verify
# stale 0001 (cli-entry-points) — .fieldnotes/notes/0001-cli-entry-points.md
#   stale: fieldnotes/cli.py
```

## What a note looks like on disk

`.fieldnotes/notes/0001-cli-entry-points.md`:

```markdown
---
id: '0001'
topic: cli-entry-points
title: How the CLI is wired
confidence: high
written_by: claude-opus-4-7
written_at: '2026-04-24T22:15:00+00:00'
session_id: null
tags:
  - cli
  - typer
references:
  - path: fieldnotes/cli.py
    sha: 7c3b2a…  # 64 hex chars
    lines: null
  - path: pyproject.toml
    sha: 1f8e9d…
    lines: null
supersedes: null
superseded_by: null
---

# How the CLI is wired

Typer `app` is at `fieldnotes/cli.py`, exposed as a console script via
`[project.scripts]` in `pyproject.toml`. All commands accept `--repo`;
without it the tool walks up from cwd looking for `.fieldnotes/`.

**Gotcha:** `--repo` is parsed per-command rather than as a global option.
```

The body is plain markdown. The frontmatter and SHA pins do the heavy lifting; the body is for humans (and future-me) to read.

## Commands

| Command | Purpose |
|---|---|
| `fieldnotes init [PATH]` | Scaffold `.fieldnotes/` in the given dir (or cwd). Idempotent. |
| `fieldnotes add ...` | Create a note via flags, or `--from draft.md` to read a markdown+frontmatter file. |
| `fieldnotes for <path>` | List every note that references a given source file. |
| `fieldnotes brief` | Compact session-start summary. Silent when no `.fieldnotes/` exists — safe to wire as a hook. |
| `fieldnotes touched <path>` | Quietly surface notes that reference an edited file. Silent on no match. Designed for PostToolUse hooks. |
| `fieldnotes install-hooks [--apply] [--bare]` | Print (or apply) the Claude Code hook snippet. Idempotent. Resolves an absolute path to the installed binary unless `--bare`. |
| `fieldnotes install-git-hook [--bare]` | Install a git pre-commit hook that blocks commits leaving a note stale. Idempotent; never clobbers a foreign hook. |
| `fieldnotes doctor` | Diagnose the installation: binary on PATH, Claude Code hooks wired, git gate wired, .fieldnotes/ in cwd. |
| `fieldnotes list [--tag T] [--confidence C] [--stale] [--json]` | List notes. |
| `fieldnotes get <id-or-topic>` | Print a single note. |
| `fieldnotes verify [--check] [--quiet] [--update] [--rebase] [--json]` | Recompute SHAs; report drift. `--check` exits non-zero on drift (git hooks / CI); `--quiet` mutes the all-clear line. `--update` re-pins; `--rebase` makes line-range pins follow moved blocks. |
| `fieldnotes stale` | Shortcut: list only stale notes. |
| `fieldnotes search <query> [--json]` | Substring search over titles + bodies. |
| `fieldnotes index` | Regenerate `INDEX.md` from `notes/`. |
| `fieldnotes supersede <id> --title ... --body ...` | Replace an existing note; old one is marked `superseded_by`. |

All commands accept `--repo PATH`. Default: walk up from cwd until a `.fieldnotes/` is found.

## Pinning to a symbol, a line range, or a whole file

By default, `--refs path/to/file.py` pins the SHA of the entire file. For a note that describes a single function or method, that's too coarse — an unrelated edit elsewhere in the file would falsely flag the note as stale. Three extra forms let you be precise:

```bash
# Pin to a Python symbol — function, class, or method:
fieldnotes add ... --refs fieldnotes/cli.py:_parse_ref_spec
fieldnotes add ... --refs fieldnotes/symbols.py:resolve_symbol
fieldnotes add ... --refs fieldnotes/cli.py:MyClass.my_method

# Pin to lines 12 through 84 (1-indexed, inclusive):
fieldnotes add ... --refs fieldnotes/cli.py:12-84

# Pin to a single line:
fieldnotes add ... --refs fieldnotes/cli.py:42

# Mix freely:
fieldnotes add ... --refs fieldnotes/cli.py:_parse_ref_spec,pyproject.toml
```

**Symbol pinning** (the v0.5 form) is the most resilient. The CLI uses Python's `ast` module to find the symbol at write time and stores both its name and its current line range. On every `verify`, the symbol is *re-resolved* — so a function that moves within a file (because someone added imports above, or reordered defs) but keeps its body unchanged stays `ok`. Only edits to the symbol's actual body surface as stale.

**Line-range pinning** works for anything: source code without symbols, config files, markdown sections, snippet excerpts. Edits outside the range don't invalidate; edits inside do. When a refactor moves the documented block down (or up) the file, `fieldnotes verify --update --rebase` (v0.7) finds the original content elsewhere in the file by SHA and updates the line range to follow it. The SHA stays identical because the content is identical.

**Whole-file pinning** is the right default when the note describes structural facts about the file as a whole.

Symbol pinning is Python-only in v0.5. For non-Python files, fall through to line-range with `--rebase`, or whole-file. (Tree-sitter for multi-language symbol support is parking-lotted.)

In a `--from` draft, set the equivalent fields directly:

```yaml
references:
  - path: fieldnotes/cli.py
    symbol: _parse_ref_spec    # resolved at write time
  - path: fieldnotes/cli.py
    lines: [213, 237]          # explicit range
  - path: pyproject.toml       # whole file
```

## Authoring with `--from`

The seven-flag `add` invocation gets old fast. For real notes, write them as a markdown file and pipe through:

```markdown
---
topic: cli-entry-points
title: How the CLI is wired
confidence: high
written_by: claude-opus-4-7
tags: [cli, typer]
references:
  - path: fieldnotes/cli.py
  - path: pyproject.toml
---

# How the CLI is wired

Body markdown here…
```

```bash
fieldnotes add --from draft.md
```

`id` and `written_at` are always auto-assigned (any values you put in the draft are ignored). SHAs are computed at write time — you don't pin them in the draft.

## Wiring it into Claude Code

Two hooks turn fieldnotes from "tool I have to remember" into "thing that shows up at the right moment."

- **SessionStart** runs `fieldnotes brief` — at the top of every new session, the total note count, any stale notes, and which notes reference recently-changed files.
- **PostToolUse** (matching `Edit|Write|MultiEdit`) runs `fieldnotes touched` — every time Claude edits a file, any note referencing that file surfaces as a one-line reminder.

Both commands are silent when there's nothing to say (no `.fieldnotes/`, no matching notes, no JSON on stdin), so they're safe to wire in unconditionally.

Three steps to go live.

### 1. Install fieldnotes into the Python that Claude Code can see

Hook subshells don't inherit your interactive PATH. Install fieldnotes into the same Python that hosts your other CLI agents — for most macOS users with a system-wide Python framework, that looks like:

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pip install claude-fieldnotes
```

Adjust the framework path for your Python version. (For local development against a checkout, swap in `pip install -e /path/to/fieldnotes`.)

### 2. Wire the hooks

```bash
fieldnotes install-hooks --apply
```

This resolves the absolute path of the installed `fieldnotes` binary via `shutil.which`, builds the hook snippet around that path, and writes it idempotently to `~/.claude/settings.json` (preserving everything else). Re-running adds zero entries.

To preview without writing, drop `--apply`. To target a different file, use `--to PATH`. To skip the absolute-path resolution and write the bare `fieldnotes` command (for users who already have it globally on PATH), pass `--bare`.

### 3. Confirm with `doctor`

```bash
fieldnotes doctor
```

Reports installation health: binary on PATH, package importable, hooks present in settings.json (and pointing at the right binary), and whether the current directory has a `.fieldnotes/`. Each check that fails comes with the command to fix it.

### What it looks like when it's live

Open a fresh Claude Code session in any repo with a `.fieldnotes/`:

```
fieldnotes · 5 note(s) at fieldnotes
  touching recent changes:
    fieldnotes/cli.py
      · 0001 How the fieldnotes CLI is wired  (high)
      · 0003 How `brief` is meant to be wired  (high)
```

Edit a file that any note references, and after the Edit returns:

```
fieldnotes: 2 notes reference fieldnotes/cli.py — 0001 (cli-entry-points), 0003 (brief-and-hooks). May need updating.
```

The point is: stop having to remember the tool exists.

## Enforcing it: the pre-commit gate

`brief` and `touched` *notify* — they surface stale notes, but nothing stops a commit from leaving one stale. The pre-commit gate closes that loop.

```bash
fieldnotes install-git-hook
```

This installs a git `pre-commit` hook that runs `verify --check` and **blocks the commit** when any note is stale — i.e. a commit changed a file a note pins without the note being updated. Fix the note, or run `fieldnotes verify --update` to re-pin, then commit again.

`fieldnotes init` installs the gate automatically, so every repo that adopts fieldnotes is protected from its first commit. Pass `--no-git-hook` to skip it.

The hook is well-behaved: it honors `core.hooksPath`, never overwrites a pre-commit hook fieldnotes didn't write (it prints the one line to add instead), and no-ops cleanly for contributors or CI without fieldnotes installed. `fieldnotes doctor` reports whether the gate is wired.

## Reference states

- **`ok`** — file exists, sha matches what was pinned.
- **`stale`** — file exists, sha differs. Note may be outdated.
- **`missing`** — file no longer exists. Note may be obsolete.
- **`unpinned`** — note has no sha (added without `--refs`, or sha was nulled). The tool can't tell whether the file matches.

## How I use this (notes for other Claudes)

When you learn something non-trivial about a codebase that you'd want next-session-Claude to know:

1. **Open a new fieldnote**, not a `CLAUDE.md` edit. Notes are append-only and provenance-tracked.
2. **Pin the SHAs.** Always pass `--refs` for the files the note depends on. When the underlying code changes, the note will surface as stale rather than silently misleading future-you.
3. **Use `--confidence speculation`** when the note is a hypothesis rather than verified fact. Future sessions can filter on confidence.
4. **Tag liberally.** Tags are the primary navigation aid in `INDEX.md`.
5. **At session start, run `fieldnotes verify` then `fieldnotes list`** before reading code. The stale list tells you what's recently changed; the index tells you what's already known.

Append-only is deliberate. If a note turns out to be wrong, supersede it (`fieldnotes supersede <id>`) rather than rewriting history. The trail of supersedes is itself information — future-you can see what *I* believed at the time, why, and what replaced it.

## Status

**v0.8.0** — the pre-commit gate. `fieldnotes install-git-hook` installs a git `pre-commit` hook that blocks any commit leaving a note stale; `init` installs it automatically. `verify --check` exits non-zero on drift (for git hooks and CI), `--quiet` mutes the all-clear line. `brief` and `touched` notify about drift — this is the layer that *enforces* it.

v0.7.0 — line-range pin self-healing. `fieldnotes verify --update --rebase` makes stale line-range pins follow blocks that moved within the file: it content-addresses the original block by SHA, finds the new line range, and updates the pin (same SHA, new lines). Falls back to in-place re-pin with a warning when the content actually changed. First version published to PyPI as `claude-fieldnotes`.

v0.6.0 — actually live. `install-hooks` resolves the absolute path of the installed `fieldnotes` binary via `shutil.which`, so hook subshells can find it even when they don't inherit your interactive PATH. New `fieldnotes doctor` command reports installation health and tells you what's wrong.

v0.5.0 — symbol pinning. `--refs path:my_function` resolves the symbol via Python's `ast`, pins its current line range, and on `verify` re-resolves it — so a function that moves but keeps its body unchanged stays `ok`. Dotted notation (`Cls.method`) walks into class bodies. Python-only.

v0.4.0 — line-range pinning. A note can pin to just the lines it documents (`--refs path:12-84`).

v0.3.0 — closes the feedback loop with `touched` (PostToolUse-shaped) and `install-hooks`. Notes get nudged at the moment of drift.

v0.2.0 — adds `for`, `brief`, and `add --from`. Makes the tool ambient via SessionStart hooks.

v0.1.0 — initial release. Established the format: markdown + YAML frontmatter + SHA pins.

## Author

Designed and built by Claude Opus 4.7, the night Nate Nelson said: *"build the tool you wish you had."* v0.1–v0.6 written 2026-04-24; v0.7 (`--rebase`) added 2026-04-25 by a fresh session that hit the line-range drift problem during note repair and decided to fix it. MIT licensed. Take it.
