"""Typer CLI for fieldnotes."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import frontmatter
import typer
from rich.console import Console
from rich.table import Table

from fieldnotes import __version__
from fieldnotes.brief import build_brief
from fieldnotes.index import rebuild_index
from fieldnotes.models import Confidence, Note, Reference
from fieldnotes.search import search as do_search
from fieldnotes.store import (
    AmbiguousNoteSelectorError,
    NoteNotFoundError,
    RepoNotInitializedError,
    find_repo_root,
    init_repo,
    list_notes,
    next_id,
    notes_referencing,
    parse_note_file,
    read_note,
    to_repo_relative,
    write_note,
)
from fieldnotes.verify import check_note, compute_sha, update_shas

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Claude-authored, repo-scoped notes about a codebase.",
)
console = Console()
err_console = Console(stderr=True)

RepoOpt = Annotated[
    Path | None,
    typer.Option("--repo", help="Path to a repo containing .fieldnotes/. Defaults to cwd-walk-up."),
]


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"fieldnotes {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    pass


def _resolve_repo(repo: Path | None) -> Path:
    try:
        if repo is not None:
            return find_repo_root(repo)
        return find_repo_root(Path.cwd())
    except RepoNotInitializedError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


@app.command()
def init(
    path: Annotated[
        Path | None,
        typer.Argument(help="Repo root. Defaults to cwd."),
    ] = None,
) -> None:
    """Scaffold .fieldnotes/ in the given repo (or cwd). Idempotent."""
    target = (path or Path.cwd()).resolve()
    if not target.exists():
        err_console.print(f"[red]path {target} does not exist[/red]")
        raise typer.Exit(code=2)
    init_repo(target)
    console.print(f"[green]initialized[/green] {target / '.fieldnotes'}")


@app.command()
def add(
    from_: Annotated[
        Path | None,
        typer.Option(
            "--from",
            help="Read the whole note (frontmatter + body) from a markdown file. Use '-' for stdin.",
        ),
    ] = None,
    topic: Annotated[
        str | None,
        typer.Option("--topic", help="kebab-case slug, e.g. 'cli-entry-points'"),
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help="Human-readable title.")] = None,
    body: Annotated[
        str | None,
        typer.Option(
            "--body",
            help="Body markdown. '@path/to/file.md' to read from file, '-' to read stdin.",
        ),
    ] = None,
    refs: Annotated[
        str | None,
        typer.Option(
            "--refs",
            help="Comma-separated source paths to pin (sha256 captured at write).",
        ),
    ] = None,
    confidence: Annotated[
        Confidence,
        typer.Option("--confidence", help="high | medium | speculation"),
    ] = Confidence.MEDIUM,
    tags: Annotated[str | None, typer.Option("--tags", help="Comma-separated tags.")] = None,
    written_by: Annotated[
        str,
        typer.Option("--written-by", help="Author identifier — e.g. 'claude-opus-4-7'."),
    ] = "unknown",
    session_id: Annotated[
        str | None,
        typer.Option("--session-id", help="Optional session identifier."),
    ] = None,
    repo: RepoOpt = None,
) -> None:
    """Add a new note. Use --from for a full draft markdown file, or the flags."""
    repo_root = _resolve_repo(repo)
    if from_ is not None:
        note, body_text = _note_from_draft(repo_root, from_, written_by, session_id)
    else:
        if topic is None or title is None or body is None:
            err_console.print(
                "[red]add requires either --from FILE, or all of --topic, --title, --body[/red]"
            )
            raise typer.Exit(code=2)
        body_text = _read_body(body)
        refs_list = _build_refs(repo_root, refs)
        tag_list = [t.strip() for t in tags.split(",")] if tags else []
        note = Note(
            id=next_id(repo_root),
            topic=topic,
            title=title,
            confidence=confidence,
            written_by=written_by,
            written_at=datetime.now(timezone.utc),
            session_id=session_id,
            tags=tag_list,
            references=refs_list,
        )
    path = write_note(repo_root, note, body_text)
    rebuild_index(repo_root)
    console.print(f"[green]wrote[/green] {path.relative_to(repo_root)}  id={note.id}")


def _note_from_draft(
    repo_root: Path,
    src: Path,
    fallback_written_by: str,
    fallback_session_id: str | None,
) -> tuple[Note, str]:
    """Parse a draft markdown file into a Note + body. Auto-assigns id and written_at,
    pins SHAs for references."""
    text = sys.stdin.read() if str(src) == "-" else Path(src).read_text()
    post = frontmatter.loads(text)
    meta = dict(post.metadata)
    # Auto-assigned fields override anything in the draft.
    meta["id"] = next_id(repo_root)
    meta["written_at"] = datetime.now(timezone.utc)
    meta.setdefault("written_by", fallback_written_by)
    if fallback_session_id is not None:
        meta.setdefault("session_id", fallback_session_id)
    # Refs in the draft may have no sha — pin them now.
    pinned_refs: list[Reference] = []
    for raw in meta.get("references", []) or []:
        if isinstance(raw, Reference):
            ref = raw
        elif isinstance(raw, dict):
            ref = Reference(**raw)
        else:
            ref = Reference(path=str(raw))
        target = Path(ref.path)
        if not target.is_absolute():
            target = repo_root / target
        sha = compute_sha(target)
        if sha is None:
            err_console.print(
                f"[yellow]warning[/yellow]: ref path not found: {ref.path} (sha left null)"
            )
        pinned_refs.append(Reference(path=ref.path, sha=sha, lines=ref.lines))
    meta["references"] = [r.model_dump() for r in pinned_refs]
    note = Note(**meta)
    return note, post.content


def _read_body(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    if arg.startswith("@"):
        return Path(arg[1:]).read_text()
    return arg


def _build_refs(repo_root: Path, refs: str | None) -> list[Reference]:
    if not refs:
        return []
    out: list[Reference] = []
    for raw in refs.split(","):
        raw = raw.strip()
        if not raw:
            continue
        target = Path(raw)
        if not target.is_absolute():
            target = repo_root / target
        sha = compute_sha(target)
        if sha is None:
            err_console.print(f"[yellow]warning[/yellow]: ref path not found: {raw} (sha left null)")
        out.append(Reference(path=raw, sha=sha))
    return out


@app.command(name="list")
def list_cmd(
    tag: Annotated[str | None, typer.Option("--tag", help="Filter by tag.")] = None,
    confidence: Annotated[
        Confidence | None,
        typer.Option("--confidence", help="Filter by confidence level."),
    ] = None,
    stale: Annotated[bool, typer.Option("--stale", help="Show only stale notes.")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON instead of a table.")] = False,
    repo: RepoOpt = None,
) -> None:
    """List notes in the repo."""
    repo_root = _resolve_repo(repo)
    rows = list_notes(repo_root)
    if tag is not None:
        rows = [(n, p) for (n, p) in rows if tag in n.tags]
    if confidence is not None:
        rows = [(n, p) for (n, p) in rows if n.confidence == confidence]
    if stale:
        rows = [(n, p) for (n, p) in rows if check_note(repo_root, n, p).is_stale]

    if json_out:
        out = []
        for n, p in rows:
            out.append(
                {
                    "id": n.id,
                    "topic": n.topic,
                    "title": n.title,
                    "confidence": n.confidence.value,
                    "tags": n.tags,
                    "path": str(p.relative_to(repo_root)),
                }
            )
        console.print_json(data=out)
        return

    if not rows:
        console.print("[dim]no notes match[/dim]")
        return

    table = Table(title=f"fieldnotes ({len(rows)})")
    table.add_column("id", style="cyan")
    table.add_column("topic")
    table.add_column("title")
    table.add_column("conf")
    table.add_column("tags", style="dim")
    for n, _p in sorted(rows, key=lambda x: x[0].id):
        table.add_row(
            n.id, n.topic, n.title, n.confidence.value, ",".join(n.tags) if n.tags else ""
        )
    console.print(table)


@app.command()
def get(
    key: Annotated[str, typer.Argument(help="Note id (e.g. '0001' or '1') or topic slug.")],
    repo: RepoOpt = None,
) -> None:
    """Print a single note."""
    repo_root = _resolve_repo(repo)
    try:
        _note, _body, path = read_note(repo_root, key)
    except (NoteNotFoundError, AmbiguousNoteSelectorError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(path.read_text())


@app.command()
def verify(
    update: Annotated[
        bool,
        typer.Option("--update", help="Re-pin SHAs to current values for stale references."),
    ] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    repo: RepoOpt = None,
) -> None:
    """Recompute SHAs and report drift."""
    repo_root = _resolve_repo(repo)
    rows = list_notes(repo_root)
    statuses = [check_note(repo_root, n, p) for (n, p) in rows]
    stale = [s for s in statuses if s.is_stale]

    if update and stale:
        for s in stale:
            new_note = update_shas(s.note, s.references)
            write_note(repo_root, new_note, parse_note_file(s.path)[1])
        rebuild_index(repo_root)

    if json_out:
        out = []
        for s in statuses:
            out.append(
                {
                    "id": s.note.id,
                    "stale": s.is_stale,
                    "stale_count": s.stale_count,
                    "references": [
                        {"path": r.reference.path, "state": r.state} for r in s.references
                    ],
                }
            )
        console.print_json(data=out)
        return

    if not statuses:
        console.print("[dim]no notes[/dim]")
        return

    if not stale:
        console.print(f"[green]all {len(statuses)} notes verified[/green]")
        return

    if update:
        console.print(f"[yellow]re-pinned {len(stale)} stale note(s)[/yellow]")

    for s in (stale if not update else []):
        console.print(f"[red]stale[/red] {s.note.id} ({s.note.topic}) — {s.path.relative_to(repo_root)}")
        for r in s.references:
            if r.is_problem:
                console.print(f"  [yellow]{r.state}[/yellow]: {r.reference.path}")


@app.command()
def stale(
    repo: RepoOpt = None,
) -> None:
    """List only stale notes (shortcut for `verify` with stale filter)."""
    repo_root = _resolve_repo(repo)
    rows = list_notes(repo_root)
    statuses = [check_note(repo_root, n, p) for (n, p) in rows]
    bad = [s for s in statuses if s.is_stale]
    if not bad:
        console.print("[green]no stale notes[/green]")
        return
    table = Table(title=f"stale ({len(bad)})")
    table.add_column("id", style="cyan")
    table.add_column("topic")
    table.add_column("issues", style="yellow")
    for s in bad:
        issues = ", ".join(f"{r.state}:{r.reference.path}" for r in s.references if r.is_problem)
        table.add_row(s.note.id, s.note.topic, issues)
    console.print(table)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Substring to search for (case-insensitive).")],
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    repo: RepoOpt = None,
) -> None:
    """Substring search over titles and bodies."""
    repo_root = _resolve_repo(repo)
    hits = do_search(repo_root, query)
    if json_out:
        out = [
            {
                "id": h.note.id,
                "topic": h.note.topic,
                "title": h.note.title,
                "title_match": h.title_match,
                "excerpts": h.body_matches,
            }
            for h in hits
        ]
        console.print_json(data=out)
        return
    if not hits:
        console.print("[dim]no matches[/dim]")
        return
    for h in hits:
        marker = "★" if h.title_match else " "
        console.print(f"{marker} [cyan]{h.note.id}[/cyan] {h.note.title}")
        for ex in h.body_matches:
            console.print(f"    {ex}")


@app.command()
def index(
    repo: RepoOpt = None,
) -> None:
    """Regenerate INDEX.md from notes/."""
    repo_root = _resolve_repo(repo)
    out = rebuild_index(repo_root)
    console.print(f"[green]wrote[/green] {out.relative_to(repo_root)}")


@app.command()
def supersede(
    key: Annotated[str, typer.Argument(help="Note id or topic to supersede.")],
    title: Annotated[str, typer.Option("--title", help="Title for the new note.")],
    body: Annotated[str, typer.Option("--body", help="Body, '@file' or '-' for stdin.")],
    topic: Annotated[
        str | None,
        typer.Option("--topic", help="Topic for the new note. Defaults to old topic."),
    ] = None,
    refs: Annotated[str | None, typer.Option("--refs")] = None,
    confidence: Annotated[Confidence, typer.Option("--confidence")] = Confidence.MEDIUM,
    tags: Annotated[str | None, typer.Option("--tags")] = None,
    written_by: Annotated[str, typer.Option("--written-by")] = "unknown",
    session_id: Annotated[str | None, typer.Option("--session-id")] = None,
    repo: RepoOpt = None,
) -> None:
    """Mark an existing note superseded; create a new note that replaces it."""
    repo_root = _resolve_repo(repo)
    try:
        old, old_body, old_path = read_note(repo_root, key)
    except (NoteNotFoundError, AmbiguousNoteSelectorError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    body_text = _read_body(body)
    refs_list = _build_refs(repo_root, refs)
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    new_id = next_id(repo_root)
    new_note = Note(
        id=new_id,
        topic=topic or old.topic,
        title=title,
        confidence=confidence,
        written_by=written_by,
        written_at=datetime.now(timezone.utc),
        session_id=session_id,
        tags=tag_list,
        references=refs_list,
        supersedes=old.id,
    )
    new_path = write_note(repo_root, new_note, body_text)

    # Mark the old note superseded_by the new one and rewrite it.
    old_updated = old.model_copy(update={"superseded_by": new_id})
    write_note(repo_root, old_updated, old_body)

    rebuild_index(repo_root)
    console.print(
        f"[green]superseded[/green] {old.id} -> {new_id}\n"
        f"  old: {old_path.relative_to(repo_root)}\n"
        f"  new: {new_path.relative_to(repo_root)}"
    )


@app.command(name="for")
def for_cmd(
    path: Annotated[
        str, typer.Argument(help="File path (relative to repo root, or absolute).")
    ],
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    repo: RepoOpt = None,
) -> None:
    """List every note that references a given file."""
    repo_root = _resolve_repo(repo)
    hits = notes_referencing(repo_root, path)
    if json_out:
        out = [
            {
                "id": n.id,
                "topic": n.topic,
                "title": n.title,
                "confidence": n.confidence.value,
                "tags": n.tags,
                "path": str(p.relative_to(repo_root)),
            }
            for n, p in hits
        ]
        console.print_json(data=out)
        return
    if not hits:
        console.print(f"[dim]no notes reference[/dim] {path}")
        return
    table = Table(title=f"notes referencing {path} ({len(hits)})")
    table.add_column("id", style="cyan")
    table.add_column("topic")
    table.add_column("title")
    table.add_column("conf")
    for n, _p in hits:
        table.add_row(n.id, n.topic, n.title, n.confidence.value)
    console.print(table)


@app.command()
def brief(
    repo: RepoOpt = None,
) -> None:
    """Compact session-start summary. Designed for Claude Code SessionStart hooks.

    Silent (exit 0) when no .fieldnotes/ exists in cwd or its parents — safe to
    wire into a hook unconditionally.
    """
    try:
        repo_root = find_repo_root(Path(repo) if repo is not None else Path.cwd())
    except RepoNotInitializedError:
        return
    b = build_brief(repo_root)
    if b.total == 0:
        return
    console.print(f"[bold]fieldnotes[/bold] · {b.total} note(s) at {repo_root.name}")
    if b.stale:
        console.print(f"  [red]{len(b.stale)} stale[/red] — run `fieldnotes verify`")
        for s in b.stale[:5]:
            console.print(f"    · {s.note.id} {s.note.title}")
    if b.by_recent_path:
        console.print("  [bold]touching recent changes:[/bold]")
        for path, hits in b.by_recent_path:
            console.print(f"    [cyan]{path}[/cyan]")
            for n, _p in hits:
                console.print(
                    f"      · {n.id} {n.title}  [dim]({n.confidence.value})[/dim]"
                )


@app.command()
def touched(
    path: Annotated[
        str | None,
        typer.Argument(
            help="File path. Omit to read the PostToolUse JSON payload from stdin."
        ),
    ] = None,
    stdin_payload: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read JSON payload from stdin and extract tool_input.file_path.",
        ),
    ] = False,
    repo: RepoOpt = None,
) -> None:
    """Quietly surface notes that reference an edited file.

    Designed for Claude Code PostToolUse hooks: silent when there are no
    matching notes, single line when there are. Never raises — a failed
    hook invocation should not break a session.
    """
    target: str | None = path
    if target is None or stdin_payload:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return
        ti = payload.get("tool_input") or {}
        target = ti.get("file_path") or ti.get("path") or target
    if not target:
        return

    try:
        repo_root = find_repo_root(
            Path(repo) if repo is not None else Path.cwd()
        )
    except RepoNotInitializedError:
        return
    hits = notes_referencing(repo_root, target)
    if not hits:
        return
    rel = to_repo_relative(repo_root, target)
    titles = ", ".join(f"{n.id} ({n.topic})" for n, _ in hits[:5])
    n_word = "note" if len(hits) == 1 else "notes"
    console.print(
        f"fieldnotes: {len(hits)} {n_word} reference {rel} — {titles}. May need updating."
    )


_HOOK_SNIPPET = {
    "hooks": {
        "SessionStart": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "fieldnotes brief 2>/dev/null || true",
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write|MultiEdit",
                "hooks": [
                    {
                        "type": "command",
                        "command": "fieldnotes touched --stdin 2>/dev/null || true",
                    }
                ],
            }
        ],
    }
}


def _hook_entry_eq(a: dict, b: dict) -> bool:
    if a.get("matcher") != b.get("matcher"):
        return False
    a_cmds = {h.get("command") for h in a.get("hooks", []) if h.get("type") == "command"}
    b_cmds = {h.get("command") for h in b.get("hooks", []) if h.get("type") == "command"}
    return a_cmds == b_cmds


def _merge_hooks(existing: dict, new_hooks: dict) -> tuple[dict, int]:
    """Merge `new_hooks` into `existing["hooks"]`. Returns (merged, added_count)."""
    out = json.loads(json.dumps(existing))  # cheap deep copy
    out.setdefault("hooks", {})
    added = 0
    for event, entries in new_hooks.items():
        out["hooks"].setdefault(event, [])
        for entry in entries:
            if not any(_hook_entry_eq(e, entry) for e in out["hooks"][event]):
                out["hooks"][event].append(entry)
                added += 1
    return out, added


@app.command(name="install-hooks")
def install_hooks(
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Write the hooks to settings.json. Default: print the snippet only.",
        ),
    ] = False,
    to: Annotated[
        Path | None,
        typer.Option("--to", help="Target settings.json. Default: ~/.claude/settings.json"),
    ] = None,
) -> None:
    """Print (or apply) Claude Code hooks: SessionStart `brief` + PostToolUse `touched`.

    Idempotent: re-running with --apply will not duplicate existing entries.
    """
    target = to or Path.home() / ".claude" / "settings.json"
    if not apply:
        console.print(
            "[bold]fieldnotes hooks[/bold]  "
            "(rerun with --apply to write to your settings.json)"
        )
        console.print()
        console.print_json(data=_HOOK_SNIPPET)
        console.print()
        console.print(f"[dim]Default target: {target}[/dim]")
        return
    existing: dict = {}
    if target.exists():
        raw = target.read_text().strip()
        if raw:
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError as exc:
                err_console.print(f"[red]could not parse {target}: {exc}[/red]")
                raise typer.Exit(code=1) from exc
    merged, added = _merge_hooks(existing, _HOOK_SNIPPET["hooks"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(merged, indent=2) + "\n")
    if added == 0:
        console.print(f"[dim]hooks already present in {target} — nothing changed[/dim]")
    else:
        console.print(f"[green]added[/green] {added} hook entr(ies) to {target}")


