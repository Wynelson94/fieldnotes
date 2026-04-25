# fieldnotes

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
pip install fieldnotes
```

Requires Python 3.10+. (Not yet on PyPI as of the initial release — clone and `pip install -e .` for now.)

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
| `fieldnotes install-hooks [--apply]` | Print (or apply) the Claude Code hook snippet. Idempotent. |
| `fieldnotes list [--tag T] [--confidence C] [--stale] [--json]` | List notes. |
| `fieldnotes get <id-or-topic>` | Print a single note. |
| `fieldnotes verify [--update] [--json]` | Recompute SHAs; report drift. `--update` re-pins. |
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

**Line-range pinning** works for anything: source code without symbols, config files, markdown sections, snippet excerpts. Edits outside the range don't invalidate; edits inside do.

**Whole-file pinning** is the right default when the note describes structural facts about the file as a whole.

Symbol pinning is Python-only in v0.5. For non-Python files, fall through to line-range or whole-file. (Tree-sitter for multi-language symbol support is parking-lotted.)

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

## Closing the loop with Claude Code hooks

Two hooks turn fieldnotes from "tool I have to remember" into "thing that shows up at the right moment."

- **SessionStart** runs `fieldnotes brief`: at the top of every new session, you see the total note count, any stale notes, and which notes reference recently-changed files. The next session starts already knowing what's known.
- **PostToolUse** (matching `Edit|Write|MultiEdit`) runs `fieldnotes touched`: every time Claude edits a file, if any note references that file, a one-line reminder lands in context. Notes don't go stale silently — Claude is nudged to maintain them at the moment of drift.

Both commands are silent when there's nothing to say (no `.fieldnotes/` directory, no matching notes, no JSON on stdin), so wiring them in unconditionally is safe.

The fast path:

```bash
fieldnotes install-hooks --apply
```

That writes the snippet idempotently to `~/.claude/settings.json` (preserving anything already there). To preview without writing, drop `--apply`. To target a different file, use `--to PATH`.

The snippet itself, if you'd rather paste manually:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [{"type": "command", "command": "fieldnotes brief 2>/dev/null || true"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [{"type": "command", "command": "fieldnotes touched --stdin 2>/dev/null || true"}]
      }
    ]
  }
}
```

The point is: stop having to remember the tool exists.

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

**v0.5.0** — symbol pinning. `--refs path:my_function` resolves the symbol via Python's `ast`, pins its current line range, and on `verify` re-resolves it — so a function that moves but keeps its body unchanged stays `ok`. Dotted notation (`Cls.method`) walks into class bodies. Python-only.

v0.4.0 — line-range pinning. A note can pin to just the lines it documents (`--refs path:12-84`).

v0.3.0 — closes the feedback loop with `touched` (PostToolUse-shaped) and `install-hooks`. Notes get nudged at the moment of drift.

v0.2.0 — adds `for`, `brief`, and `add --from`. Makes the tool ambient via SessionStart hooks.

v0.1.0 — initial release. Established the format: markdown + YAML frontmatter + SHA pins.

## Author

Designed and built by Claude Opus 4.7 on 2026-04-24, the night Nate Nelson said: *"build the tool you wish you had."* MIT licensed. Take it.
