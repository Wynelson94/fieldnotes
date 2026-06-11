"""Substring search over fieldnotes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fieldnotes.models import Note
from fieldnotes.store import iter_note_files, parse_note_file


@dataclass(frozen=True)
class SearchHit:
    note: Note
    path: Path
    title_match: bool
    body_matches: list[str]  # excerpt strings around the match


def search(repo_root: Path, query: str, *, context: int = 40) -> list[SearchHit]:
    """Case-insensitive substring search over titles, topics, tags, and bodies."""
    q = query.strip().lower()
    if not q:
        return []
    hits: list[SearchHit] = []
    for path in iter_note_files(repo_root):
        try:
            note, body = parse_note_file(path)
        except Exception:
            continue
        title_match = (
            q in note.title.lower()
            or q in note.topic.lower()
            or any(q in t.lower() for t in note.tags)
        )
        body_matches = _excerpts(body, q, context=context)
        if title_match or body_matches:
            hits.append(
                SearchHit(
                    note=note,
                    path=path,
                    title_match=title_match,
                    body_matches=body_matches,
                )
            )
    return hits


def _excerpts(text: str, q: str, *, context: int) -> list[str]:
    out: list[str] = []
    lower = text.lower()
    start = 0
    while True:
        i = lower.find(q, start)
        if i < 0:
            break
        a = max(0, i - context)
        b = min(len(text), i + len(q) + context)
        snippet = text[a:b].replace("\n", " ").strip()
        if a > 0:
            snippet = "…" + snippet
        if b < len(text):
            snippet = snippet + "…"
        out.append(snippet)
        start = i + len(q)
        if len(out) >= 5:  # cap excerpts per note
            break
    return out
