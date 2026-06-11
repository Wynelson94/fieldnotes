"""Typer CLI for fieldnotes."""

from __future__ import annotations

import json
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import frontmatter
import typer
from rich.console import Console
from rich.table import Table

from fieldnotes import __version__
from fieldnotes.brief import build_brief, recent_git_paths
from fieldnotes.diffcmd import diff_note, is_git_repo, pin_descriptor
from fieldnotes.doctor import run_diagnostics
from fieldnotes.gaps import churn_map, coverage_paths, hottest_gap, uncovered_by_churn
from fieldnotes.githook import git_hook_installed, git_toplevel, install_git_hook
from fieldnotes.index import rebuild_index
from fieldnotes.models import SYMBOL_RE, Confidence, Note, Reference, Validation
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
from fieldnotes.symbols import SYMBOL_SUFFIXES, resolve_symbol
from fieldnotes.verify import (
    NoteStatus,
    RebaseResult,
    check_note,
    compute_range_sha,
    update_shas,
)

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
    no_git_hook: Annotated[
        bool,
        typer.Option("--no-git-hook", help="Skip installing the pre-commit drift gate."),
    ] = False,
) -> None:
    """Scaffold .fieldnotes/ in the given repo (or cwd). Idempotent.

    Also installs a git pre-commit hook that blocks commits leaving a note
    stale — skipped with --no-git-hook or when the target isn't a git repo.
    """
    target = (path or Path.cwd()).resolve()
    if not target.exists():
        err_console.print(f"[red]path {target} does not exist[/red]")
        raise typer.Exit(code=2)
    init_repo(target)
    console.print(f"[green]initialized[/green] {target / '.fieldnotes'}")
    if not no_git_hook:
        _install_init_git_hook(target)


def _install_init_git_hook(target: Path) -> None:
    """Best-effort pre-commit gate install during `init`. Never fails init."""
    binary = _fieldnotes_binary(bare=False) or "fieldnotes"
    result = install_git_hook(target, binary)
    if result.status in ("installed", "updated"):
        console.print(
            f"[green]gate[/green] installed the pre-commit drift gate at {result.hook_path}"
        )
    elif result.status == "unchanged":
        console.print(f"[dim]pre-commit gate already present at {result.hook_path}[/dim]")
    elif result.status == "foreign":
        console.print(
            f"[yellow]pre-commit gate skipped[/yellow] — {result.detail}; "
            "run `fieldnotes install-git-hook` for guidance"
        )
    else:  # not-a-git-repo
        console.print("[dim]not a git repo — skipped the pre-commit gate[/dim]")


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
    advisory_refs: Annotated[
        str | None,
        typer.Option(
            "--advisory-refs",
            help="Like --refs, but drift never makes the note stale — context-only "
            "pins for volatile files (e.g. pyproject.toml).",
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
        refs_list = _build_refs(repo_root, refs) + _build_refs(
            repo_root, advisory_refs, advisory=True
        )
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
    _warn_duplicate_topic(repo_root, note)
    path = write_note(repo_root, note, body_text)
    rebuild_index(repo_root)
    console.print(f"[green]wrote[/green] {path.relative_to(repo_root)}  id={note.id}")


def _warn_duplicate_topic(repo_root: Path, note: Note) -> None:
    """Warn when another ACTIVE note already owns this topic.

    Sharing a slug with superseded ancestors is normal; two live notes on one
    slug makes topic lookup ambiguous and usually means the author wanted
    `supersede`. Warn, don't block — the gate blocks lies, not style.
    """
    for other, _p in list_notes(repo_root):
        if other.id != note.id and other.topic == note.topic and other.superseded_by is None:
            err_console.print(
                f"[yellow]warning[/yellow]: topic {note.topic!r} already exists as note "
                f"{other.id}; consider `fieldnotes supersede {other.id}` (created anyway)"
            )
            return


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
        # Reject directory refs — same rationale as in _build_refs above.
        if target.exists() and target.is_dir():
            err_console.print(
                f"[yellow]warning[/yellow]: {ref.path} is a directory; "
                f"pin a specific file (skipped)"
            )
            continue
        # If the draft set a symbol but no lines, resolve now.
        effective_lines = ref.lines
        effective_symbol = ref.symbol
        if effective_symbol is not None and effective_lines is None:
            # Unsupported file types drop the symbol so we don't persist a
            # pin that can never resolve.
            if target.suffix.lower() not in SYMBOL_SUFFIXES:
                err_console.print(
                    f"[yellow]warning[/yellow]: symbol pinning supports Python/TS/JS/SQL; "
                    f"pinning {ref.path} as whole file"
                )
                effective_symbol = None
            else:
                resolved = resolve_symbol(target, effective_symbol)
                if resolved is not None:
                    effective_lines = list(resolved)
                else:
                    err_console.print(
                        f"[yellow]warning[/yellow]: could not resolve symbol "
                        f"{effective_symbol!r} in {ref.path}"
                    )
        sha = compute_range_sha(target, effective_lines)
        if sha is None:
            err_console.print(
                f"[yellow]warning[/yellow]: ref path not found: {ref.path} (sha left null)"
            )
        pinned_refs.append(
            Reference(
                path=ref.path,
                sha=sha,
                lines=effective_lines,
                symbol=effective_symbol,
                pinned_at=datetime.now(timezone.utc) if sha else None,
                advisory=ref.advisory,
            )
        )
    meta["references"] = [r.model_dump() for r in pinned_refs]
    note = Note(**meta)
    return note, post.content


def _read_body(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    if arg.startswith("@"):
        return Path(arg[1:]).read_text()
    return arg


def _parse_ref_spec(spec: str) -> tuple[str, list[int] | None, str | None]:
    """Parse a ref spec into (path, lines_or_None, symbol_or_None).

    Forms:
      `path/to/file.py`              -> whole file
      `path/to/file.py:42`           -> single line, [42, 42]
      `path/to/file.py:12-84`        -> range [12, 84]
      `path/to/file.py:my_func`      -> symbol (resolved at write time, Python only)
      `path/to/file.py:Cls.method`   -> dotted symbol (method on a class)
    """
    if ":" not in spec:
        return spec, None, None
    path, _, suffix = spec.rpartition(":")
    if not suffix or not path:
        return spec, None, None
    # Range form: 12-84
    if "-" in suffix:
        a, b = suffix.split("-", 1)
        try:
            return path, [int(a), int(b)], None
        except ValueError:
            return spec, None, None
    # Single-line form: 42
    try:
        n = int(suffix)
        return path, [n, n], None
    except ValueError:
        pass
    # Symbol form: my_func or MyClass.method
    if SYMBOL_RE.fullmatch(suffix):
        return path, None, suffix
    return spec, None, None


def _build_refs(repo_root: Path, refs: str | None, advisory: bool = False) -> list[Reference]:
    if not refs:
        return []
    out: list[Reference] = []
    for raw in refs.split(","):
        raw = raw.strip()
        if not raw:
            continue
        ref_path, lines, symbol = _parse_ref_spec(raw)
        target = Path(ref_path)
        if not target.is_absolute():
            target = repo_root / target
        # Reject directory refs — would persist a broken Reference forever
        # (compute_range_sha returns None for directories, leaving a
        # perpetually "missing" ref). Tell the user, drop this ref.
        if target.exists() and target.is_dir():
            err_console.print(
                f"[yellow]warning[/yellow]: {ref_path} is a directory; "
                f"pin a specific file (skipped)"
            )
            continue
        if symbol is not None and lines is None:
            # Unsupported file types degrade to whole-file rather than
            # persisting a symbol that can never resolve (would mark stale
            # on every verify forever).
            if target.suffix.lower() not in SYMBOL_SUFFIXES:
                err_console.print(
                    f"[yellow]warning[/yellow]: symbol pinning supports Python/TS/JS/SQL; "
                    f"pinning {ref_path} as whole file"
                )
                symbol = None
            else:
                resolved = resolve_symbol(target, symbol)
                if resolved is None:
                    err_console.print(
                        f"[yellow]warning[/yellow]: could not resolve symbol "
                        f"{symbol!r} in {ref_path} (pinning whole file)"
                    )
                else:
                    lines = list(resolved)
        sha = compute_range_sha(target, lines)
        if sha is None:
            err_console.print(
                f"[yellow]warning[/yellow]: ref path not found: {ref_path} (sha left null)"
            )
        out.append(
            Reference(
                path=ref_path,
                sha=sha,
                lines=lines,
                symbol=symbol,
                pinned_at=datetime.now(timezone.utc) if sha else None,
                advisory=advisory,
            )
        )
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
        note, _body, path = read_note(repo_root, key)
    except (NoteNotFoundError, AmbiguousNoteSelectorError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(path.read_text())
    console.print(f"[dim]{_ledger_summary(note)}[/dim]")


def _ledger_summary(note: Note) -> str:
    """`confidence` is the author's prior; the ledger is accumulated evidence.

    Rendered together so both fields carry meaning: a `speculation` confirmed
    three times outranks a `high` that nobody ever re-read.
    """
    if not note.validations:
        return f"confidence {note.confidence.value} — never re-validated"
    last = max(note.validations, key=lambda v: v.at)
    return (
        f"confidence {note.confidence.value} — validated {len(note.validations)}× "
        f"(last {last.at.date().isoformat()} by {last.by})"
    )


@app.command()
def confirm(
    key: Annotated[str, typer.Argument(help="Note id (e.g. '0001' or '1') or topic slug.")],
    by: Annotated[
        str,
        typer.Option("--by", help="Who re-validated the claim — e.g. 'claude-fable-5'."),
    ] = "unknown",
    repo: RepoOpt = None,
) -> None:
    """Record that you re-read this note against current code and the claim holds.

    A re-pin fixes the SHA; only a reader can validate the prose. Refuses
    stale notes — confirm against current pins, not over drift (run
    `fieldnotes verify --update` first).
    """
    repo_root = _resolve_repo(repo)
    try:
        note, body, _path = read_note(repo_root, key)
    except (NoteNotFoundError, AmbiguousNoteSelectorError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    status = check_note(repo_root, note, _path)
    if status.is_stale:
        err_console.print(
            f"[red]note {note.id} is stale — confirm validates the claim against "
            "current pins.[/red] Heal first: fieldnotes verify --update, re-read, "
            "then confirm."
        )
        raise typer.Exit(code=1)
    note.validations.append(Validation(at=datetime.now(timezone.utc), by=by))
    write_note(repo_root, note, body)
    console.print(f"[green]confirmed[/green] {note.id} ({note.topic}) — {_ledger_summary(note)}")


def _print_gate_tip(repo_root: Path) -> None:
    """One dim line nudging gate adoption — only when it would actually help.

    Real-world correlation: gated repos stay <20% stale, ungated drift to
    50-100%. Callers gate on output mode (never in --check/--quiet/--json).
    """
    if git_toplevel(repo_root) is None:
        return
    installed, _ = git_hook_installed(repo_root)
    if not installed:
        console.print(
            "[dim]tip: `fieldnotes install-git-hook` blocks commits that leave a note stale[/dim]"
        )


def _changed_refs(status: NoteStatus, rebase_results: list[RebaseResult]) -> list[str]:
    """The note's stale refs whose pinned content *changed* rather than moved.

    A moved range (rebased/ambiguous) keeps its SHA — the claim is untouched.
    Everything else stale got re-pinned over different content, so the note's
    prose needs a human (or Claude) re-read before the re-pin can be trusted.
    """
    moved = {
        (r.ref_path, tuple(r.original_lines or []))
        for r in rebase_results
        if r.outcome in ("rebased", "ambiguous")
    }
    changed: list[str] = []
    for r in status.references:
        if r.state != "stale":
            continue
        if r.reference.advisory:
            continue
        if (r.reference.path, tuple(r.reference.lines or [])) in moved:
            continue
        if r.reference.symbol is not None and r.actual_sha is None:
            changed.append(
                f"{r.reference.path} (symbol '{r.reference.symbol}' no longer resolves — not re-pinned)"
            )
        else:
            changed.append(r.reference.path)
    return changed


@app.command()
def verify(
    update: Annotated[
        bool,
        typer.Option("--update", help="Re-pin SHAs to current values for stale references."),
    ] = False,
    rebase: Annotated[
        bool | None,
        typer.Option(
            "--rebase/--no-rebase",
            help="Relocate stale line-range pins by SHA before re-pinning, so pins follow "
            "code that moved within a file. On by default when updating; --rebase alone "
            "implies --update.",
        ),
    ] = None,
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Exit non-zero when any note is stale. For git hooks and CI.",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Suppress the all-clear line; still report drift."),
    ] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    repo: RepoOpt = None,
) -> None:
    """Recompute SHAs and report drift."""
    # --rebase alone used to be a silent no-op; relocating without re-pinning
    # has no meaning, so an explicit --rebase implies --update. When updating,
    # rebase is on unless --no-rebase opts out.
    update = update or rebase is True
    do_rebase = rebase if rebase is not None else True
    repo_root = _resolve_repo(repo)
    rows = list_notes(repo_root)
    statuses = [check_note(repo_root, n, p) for (n, p) in rows]
    stale = [s for s in statuses if s.is_stale]
    # --update also quietly refreshes advisory drift, which never counts as stale.
    needs_repin = [s for s in statuses if s.needs_repin]

    rebase_results: list[RebaseResult] = []
    review: list[tuple[NoteStatus, list[str]]] = []
    if update and needs_repin:
        for s in needs_repin:
            note_results: list[RebaseResult] = []
            new_note = update_shas(
                s.note,
                s.references,
                repo_root=repo_root if do_rebase else None,
                rebase=do_rebase,
                rebase_results=note_results if do_rebase else None,
            )
            write_note(repo_root, new_note, parse_note_file(s.path)[1])
            rebase_results.extend(note_results)
            changed = _changed_refs(s, note_results)
            if changed:
                review.append((s, changed))
        rebuild_index(repo_root)

    should_fail = check and bool(stale) and not update

    if json_out:
        out = []
        for s in statuses:
            out.append(
                {
                    "id": s.note.id,
                    "stale": s.is_stale,
                    "stale_count": s.stale_count,
                    "references": [
                        {
                            "path": r.reference.path,
                            "state": r.state,
                            "advisory": r.reference.advisory,
                        }
                        for r in s.references
                    ],
                }
            )
        console.print_json(data=out)
        if should_fail:
            raise typer.Exit(code=1)
        return

    if not statuses:
        if not quiet:
            console.print("[dim]no notes[/dim]")
        return

    if not update and not quiet:
        for s in statuses:
            for r in s.references:
                if r.is_problem and r.reference.advisory:
                    console.print(
                        f"[dim]drifted (advisory) {s.note.id} ({s.note.topic}): "
                        f"{r.reference.path}[/dim]"
                    )

    if not stale:
        if not quiet:
            console.print(f"[green]all {len(statuses)} notes verified[/green]")
            if not check and not json_out:
                _print_gate_tip(repo_root)
        return

    if update:
        console.print(f"[yellow]re-pinned {len(needs_repin)} stale note(s)[/yellow]")
        for r in rebase_results:
            if r.outcome == "rebased":
                console.print(
                    f"  [green]rebased[/green] {r.ref_path}: lines {r.original_lines} → {r.new_lines}"
                )
            elif r.outcome == "ambiguous":
                console.print(
                    f"  [yellow]rebased (ambiguous)[/yellow] {r.ref_path}: multiple matches; chose {r.new_lines} (closest to original {r.original_lines})"
                )
            elif r.outcome == "no_match":
                console.print(
                    f"  [yellow]warning[/yellow] {r.ref_path}: original content no longer present at any line range; pinned in place at {r.original_lines}"
                )
        if review:
            console.print(
                "[bold yellow]re-read these notes[/bold yellow] — pinned content changed "
                "(not just moved); confirm the claims still hold:"
            )
            for s, paths in review:
                console.print(f"  {s.note.id} ({s.note.topic}): {', '.join(paths)}")
            console.print(
                "  [dim]after re-reading, record that the claim holds: "
                "fieldnotes confirm <id>[/dim]"
            )

    for s in stale if not update else []:
        console.print(
            f"[red]stale[/red] {s.note.id} ({s.note.topic}) — {s.path.relative_to(repo_root)}"
        )
        for r in s.references:
            if r.is_problem:
                console.print(f"  [yellow]{r.state}[/yellow]: {r.reference.path}")

    if not quiet and not check and not json_out:
        _print_gate_tip(repo_root)

    if should_fail:
        raise typer.Exit(code=1)


@app.command()
def gaps(
    since: Annotated[
        str,
        typer.Option("--since", help="Git time window, e.g. '90 days ago' or '2026-01-01'."),
    ] = "90 days ago",
    limit: Annotated[int, typer.Option("--limit", help="Max files to list.")] = 10,
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    repo: RepoOpt = None,
) -> None:
    """The hottest-churning files with no notes — where undocumented knowledge piles up.

    The gate catches a note going stale; this catches the note that was never
    written. Data, not nagging: run it when you want the number.
    """
    repo_root = _resolve_repo(repo)
    ranked = uncovered_by_churn(repo_root, since=since)
    if ranked is None:
        console.print("[dim]not a git repository — gaps needs git history[/dim]")
        return
    churn = churn_map(repo_root, since=since) or {}
    covered = coverage_paths(repo_root)
    changed_covered = sum(1 for p in churn if p in covered)
    if json_out:
        console.print_json(
            data={
                "since": since,
                "changed_files": len(churn),
                "covered": changed_covered,
                "gaps": [{"path": p, "commits": n} for p, n in ranked[:limit]],
            }
        )
        return
    console.print(
        f"[bold]coverage[/bold] · {changed_covered} of {len(churn)} files changed "
        f"since {since!r} are covered by notes"
    )
    if not ranked:
        console.print("[green]no gaps — every changed file has a note[/green]")
        return
    for p, n in ranked[:limit]:
        console.print(f"  [cyan]{p}[/cyan]  {n} commit(s), no notes")
    if len(ranked) > limit:
        console.print(f"  [dim]… and {len(ranked) - limit} more (--limit to widen)[/dim]")


@app.command(name="diff")
def diff_cmd(
    key: Annotated[str, typer.Argument(help="Note id (e.g. 0007 or 7) or topic slug.")],
    repo: RepoOpt = None,
) -> None:
    """Show what changed under a note's pins since they were pinned.

    For each reference: git diff of its path from the last commit before the
    pin time to the working tree (uncommitted drift included). Pairs with
    `verify --update`'s re-read list — this is how you check whether the
    note's claim still holds.
    """
    repo_root = _resolve_repo(repo)
    try:
        note, _body, _path = read_note(repo_root, key)
    except (NoteNotFoundError, AmbiguousNoteSelectorError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    if not is_git_repo(repo_root):
        console.print("[dim]not a git repository — fieldnotes diff needs git history[/dim]")
        return
    if not note.references:
        console.print(f"[dim]note {note.id} has no references[/dim]")
        return
    console.print(f"[bold]{note.id} ({note.topic})[/bold] — {note.title}")
    for rd in diff_note(repo_root, note):
        base = f", base {rd.base[:10]}" if rd.base else ""
        console.print(f"[cyan]── {rd.reference.path}[/cyan] ({pin_descriptor(rd.reference)}{base})")
        if rd.message is not None:
            console.print(f"  [dim]{rd.message}[/dim]")
        if rd.diff is not None:
            console.print(rd.diff, markup=False, highlight=False)


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
    path: Annotated[str, typer.Argument(help="File path (relative to repo root, or absolute).")],
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
    table.add_column("pin")
    table.add_column("conf")
    for n, _p in hits:
        table.add_row(n.id, n.topic, n.title, _pins_for(repo_root, n, path), n.confidence.value)
    console.print(table)


def _pins_for(repo_root: Path, note: Note, target: str) -> str:
    """How this note pins `target` — 'lines 12-84', 'symbol foo', 'whole file'."""
    rel = to_repo_relative(repo_root, target)
    descs = [
        pin_descriptor(ref)
        for ref in note.references
        if to_repo_relative(repo_root, ref.path) == rel
    ]
    return ", ".join(descs)


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
                console.print(f"      · {n.id} {n.title}  [dim]({n.confidence.value})[/dim]")
    gap = hottest_gap(repo_root)
    if gap is not None:
        console.print(f"  [yellow]coverage gap:[/yellow] {gap[0]} ({gap[1]} commits, no notes)")
    _print_gate_tip(repo_root)


@app.command()
def handoff(
    repo: RepoOpt = None,
) -> None:
    """Session-end check: what changed vs what's documented. For the Stop hook.

    Shows which changed files are covered by notes (and by which claims),
    which aren't, and asks the closing session to record what it learned —
    or decline on purpose. Silent when there's nothing to say: no
    .fieldnotes/, no git, or no changes.
    """
    try:
        repo_root = find_repo_root(Path(repo) if repo is not None else Path.cwd())
    except RepoNotInitializedError:
        return
    if git_toplevel(repo_root) is None:
        return
    changed = [p for p in recent_git_paths(repo_root, depth=1) if not p.startswith(".fieldnotes/")]
    if not changed:
        return
    covered: list[tuple[str, list[tuple[Note, Path]]]] = []
    uncovered: list[str] = []
    for p in changed:
        hits = notes_referencing(repo_root, p)
        if hits:
            covered.append((p, hits))
        else:
            uncovered.append(p)
    if not covered and not uncovered:
        return
    console.print("[bold]fieldnotes handoff[/bold] · session changes vs notes")
    if covered:
        console.print("  [green]covered:[/green]")
        for p, hits in covered:
            for n, _np in hits:
                console.print(f"    {p} — {n.id} {n.title}")
    if uncovered:
        console.print(f"  [yellow]no notes:[/yellow] {', '.join(uncovered[:10])}")
        console.print(
            "  If this session learned something durable and non-obvious about these, "
            "record it:\n"
            "    fieldnotes add --topic <slug> --title ... --body ... --refs <path>  "
            "(or --from - for a draft)\n"
            "  [dim]Declining is fine — but decline on purpose.[/dim]"
        )


@app.command()
def touched(
    path: Annotated[
        str | None,
        typer.Argument(help="File path. Omit to read the PostToolUse JSON payload from stdin."),
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
        repo_root = find_repo_root(Path(repo) if repo is not None else Path.cwd())
    except RepoNotInitializedError:
        return
    hits = notes_referencing(repo_root, target)
    if not hits:
        return
    rel = to_repo_relative(repo_root, target)
    claims = "; ".join(f"{n.id} {n.title} ({_pins_for(repo_root, n, rel)})" for n, _ in hits[:5])
    n_word = "note" if len(hits) == 1 else "notes"
    console.print(
        f"fieldnotes: {len(hits)} {n_word} reference {rel} — {claims}. May need updating."
    )


def _build_hook_snippet(binary: str = "fieldnotes") -> dict:
    """Build the Claude Code hook snippet around a binary path.

    `binary` is the command (or absolute path) used to invoke fieldnotes.
    Shell-quoted on the way in: hook commands run through sh, and an unquoted
    path with a space fails silently behind the trailing `|| true`.
    """
    quoted = shlex.quote(binary)
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{quoted} brief 2>/dev/null || true",
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
                            "command": f"{quoted} touched --stdin 2>/dev/null || true",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{quoted} handoff 2>/dev/null || true",
                        }
                    ],
                }
            ],
        }
    }


# Kept for backwards compat with tests / other callers — relative form.
_HOOK_SNIPPET = _build_hook_snippet("fieldnotes")


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
    bare: Annotated[
        bool,
        typer.Option(
            "--bare",
            help="Use the relative `fieldnotes` command instead of an absolute path. "
            "Only works if fieldnotes is on the PATH that hook subshells inherit.",
        ),
    ] = False,
) -> None:
    """Print (or apply) Claude Code hooks: SessionStart `brief` + PostToolUse `touched`.

    Idempotent: re-running with --apply will not duplicate existing entries.

    Resolves the `fieldnotes` binary via shutil.which and writes its absolute
    path into the hook command — Claude Code hook subshells often don't inherit
    the interactive PATH, so the absolute form is the reliable default. Pass
    --bare to use the relative form anyway.
    """
    target = to or Path.home() / ".claude" / "settings.json"

    binary = "fieldnotes"
    if not bare:
        resolved = shutil.which("fieldnotes")
        if resolved is None:
            err_console.print(
                "[red]fieldnotes is not on PATH from this shell.[/red]\n"
                "Install it into the Python that hosts your other CLI agents, e.g.:\n"
                "  /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 "
                "-m pip install -e <repo>\n"
                "Or pass --bare to write `fieldnotes` and resolve PATH yourself."
            )
            raise typer.Exit(code=1)
        binary = resolved

    snippet = _build_hook_snippet(binary)

    if not apply:
        console.print(
            "[bold]fieldnotes hooks[/bold]  (rerun with --apply to write to your settings.json)"
        )
        console.print()
        console.print_json(data=snippet)
        console.print()
        console.print(f"[dim]Binary: {binary}[/dim]")
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
    merged, added = _merge_hooks(existing, snippet["hooks"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(merged, indent=2) + "\n")
    if added == 0:
        console.print(f"[dim]hooks already present in {target} — nothing changed[/dim]")
    else:
        console.print(f"[green]added[/green] {added} hook entr(ies) to {target}")
    console.print(f"[dim]binary: {binary}[/dim]")


def _fieldnotes_binary(bare: bool) -> str | None:
    """Resolve the fieldnotes command to bake into a generated hook.

    Absolute path by default (hook subshells don't inherit an interactive PATH);
    the bare `fieldnotes` when `bare` is set. None when non-bare and not on PATH.
    """
    if bare:
        return "fieldnotes"
    return shutil.which("fieldnotes")


@app.command(name="install-git-hook")
def install_git_hook_cmd(
    bare: Annotated[
        bool,
        typer.Option(
            "--bare",
            help="Bake the relative `fieldnotes` command into the hook instead of an "
            "absolute path. Only works if fieldnotes is on the PATH commit hooks inherit.",
        ),
    ] = False,
    repo: RepoOpt = None,
) -> None:
    """Install a git pre-commit hook that blocks commits leaving a note stale.

    Idempotent. Never overwrites a pre-commit hook fieldnotes didn't write.
    """
    repo_root = _resolve_repo(repo)
    binary = _fieldnotes_binary(bare)
    if binary is None:
        err_console.print(
            "[red]fieldnotes is not on PATH from this shell.[/red]\n"
            "Install it into the Python that hosts your CLI agents, or pass --bare."
        )
        raise typer.Exit(code=1)

    result = install_git_hook(repo_root, binary)
    if result.status == "not-a-git-repo":
        err_console.print(f"[red]{result.detail}[/red]")
        raise typer.Exit(code=1)
    if result.status == "foreign":
        err_console.print(
            f"[yellow]not overwriting[/yellow] {result.hook_path}\n"
            f"  {result.detail}\n"
            "  To gate fieldnotes drift, add this line to that hook:\n"
            f"    {binary} verify --check --quiet || exit 1"
        )
        raise typer.Exit(code=1)
    if result.status == "unchanged":
        console.print(f"[dim]gate already installed at {result.hook_path} — nothing changed[/dim]")
        return
    verb = "installed" if result.status == "installed" else "refreshed"
    console.print(f"[green]{verb}[/green] the fieldnotes pre-commit gate at {result.hook_path}")
    console.print(f"[dim]binary: {binary}[/dim]")


@app.command()
def doctor(
    settings: Annotated[
        Path | None,
        typer.Option(
            "--settings",
            help="Settings.json to check. Default: ~/.claude/settings.json",
        ),
    ] = None,
) -> None:
    """Diagnose the fieldnotes installation: binary on PATH, hooks wired, .fieldnotes/ in cwd."""
    report = run_diagnostics(settings_path=settings, cwd=Path.cwd())
    table = Table(title="fieldnotes doctor", show_header=False, box=None, pad_edge=False)
    table.add_column("status", width=2)
    table.add_column("name")
    table.add_column("detail", overflow="fold")
    for c in report.checks:
        marker = "[green]✓[/green]" if c.ok else "[red]✗[/red]"
        table.add_row(marker, c.name, c.detail)
    console.print(table)
    fixes = [c for c in report.checks if not c.ok and c.fix]
    if fixes:
        console.print()
        console.print("[bold]How to fix[/bold]")
        for c in fixes:
            console.print(f"  [yellow]{c.name}[/yellow]: {c.fix}")
    if not report.all_ok:
        raise typer.Exit(code=1)
