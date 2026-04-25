"""Generate a human-readable INDEX.md from the notes/ directory."""

from __future__ import annotations

from pathlib import Path

from fieldnotes.models import Note
from fieldnotes.store import index_path, list_notes


def render_index(notes: list[tuple[Note, Path]]) -> str:
    """Render INDEX.md content from a list of (note, path)."""
    if not notes:
        return "# Fieldnotes index\n\n_No notes yet. Run `fieldnotes add` to create one._\n"

    by_tag: dict[str, list[tuple[Note, Path]]] = {}
    untagged: list[tuple[Note, Path]] = []
    for n, p in notes:
        if not n.tags:
            untagged.append((n, p))
            continue
        for t in n.tags:
            by_tag.setdefault(t, []).append((n, p))

    lines: list[str] = ["# Fieldnotes index", ""]
    lines.append(f"{len(notes)} note{'s' if len(notes) != 1 else ''}.")
    lines.append("")

    # All notes, in id order.
    lines.append("## All notes")
    lines.append("")
    for n, p in sorted(notes, key=lambda x: x[0].id):
        lines.append(_index_line(n, p))
    lines.append("")

    if by_tag:
        lines.append("## By tag")
        lines.append("")
        for tag in sorted(by_tag):
            lines.append(f"### {tag}")
            lines.append("")
            for n, p in sorted(by_tag[tag], key=lambda x: x[0].id):
                lines.append(_index_line(n, p))
            lines.append("")

    if untagged:
        lines.append("## Untagged")
        lines.append("")
        for n, p in sorted(untagged, key=lambda x: x[0].id):
            lines.append(_index_line(n, p))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _index_line(note: Note, path: Path) -> str:
    sup = ""
    if note.superseded_by:
        sup = f" _(superseded by {note.superseded_by})_"
    rel = f"notes/{path.name}"
    return f"- **{note.id}** [{note.title}]({rel}) — *{note.confidence.value}*{sup}"


def rebuild_index(repo_root: Path) -> Path:
    """Regenerate INDEX.md from the current notes/ directory. Returns path."""
    notes = list_notes(repo_root)
    out = index_path(repo_root)
    out.write_text(render_index(notes))
    return out
