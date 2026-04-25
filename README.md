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
| `fieldnotes list [--tag T] [--confidence C] [--stale] [--json]` | List notes. |
| `fieldnotes get <id-or-topic>` | Print a single note. |
| `fieldnotes verify [--update] [--json]` | Recompute SHAs; report drift. `--update` re-pins. |
| `fieldnotes stale` | Shortcut: list only stale notes. |
| `fieldnotes search <query> [--json]` | Substring search over titles + bodies. |
| `fieldnotes index` | Regenerate `INDEX.md` from `notes/`. |
| `fieldnotes supersede <id> --title ... --body ...` | Replace an existing note; old one is marked `superseded_by`. |

All commands accept `--repo PATH`. Default: walk up from cwd until a `.fieldnotes/` is found.

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

## Wiring as a Claude Code SessionStart hook

`fieldnotes brief` exits silently when no `.fieldnotes/` directory is found, which makes it safe to wire as a global hook. Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "fieldnotes brief 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

When you start a session in a repo that has fieldnotes, you'll see a compact summary at the top: total note count, any stale notes, and notes touching recently-changed files (uncommitted + last 5 commits via git). When you start a session in a repo that doesn't, nothing happens.

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

**v0.2.0** — adds `for`, `brief`, and `add --from`. The format from v0.1 is unchanged. Multi-repo aggregation and semantic search are still parking-lotted.

v0.1.0 — initial release.

## Author

Designed and built by Claude Opus 4.7 on 2026-04-24, the night Nate Nelson said: *"build the tool you wish you had."* MIT licensed. Take it.
