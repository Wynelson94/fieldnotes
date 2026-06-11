"""Filesystem operations for fieldnotes storage."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import frontmatter

from fieldnotes.models import ID_RE, SLUG_RE, Note

DOT_DIR = ".fieldnotes"
NOTES_DIR = "notes"
INDEX_FILE = "INDEX.md"
CONFIG_FILE = "config.toml"


class RepoNotInitializedError(Exception):
    """Raised when no `.fieldnotes/` directory is found."""


class NoteNotFoundError(Exception):
    """Raised when a note key resolves to nothing."""


class AmbiguousNoteSelectorError(Exception):
    """Raised when a note key matches more than one note."""


def fieldnotes_dir(repo_root: Path) -> Path:
    return repo_root / DOT_DIR


def notes_dir(repo_root: Path) -> Path:
    return fieldnotes_dir(repo_root) / NOTES_DIR


def index_path(repo_root: Path) -> Path:
    return fieldnotes_dir(repo_root) / INDEX_FILE


def config_path(repo_root: Path) -> Path:
    return fieldnotes_dir(repo_root) / CONFIG_FILE


def find_repo_root(start: Path) -> Path:
    """Walk upward from `start` until a `.fieldnotes/` directory is found."""
    cur = Path(start).resolve()
    while True:
        if (cur / DOT_DIR).is_dir():
            return cur
        if cur.parent == cur:
            raise RepoNotInitializedError(
                f"no {DOT_DIR}/ found in {start} or any parent. Run 'fieldnotes init'."
            )
        cur = cur.parent


def init_repo(repo_root: Path) -> Path:
    """Create the `.fieldnotes/` scaffold inside `repo_root`. Idempotent."""
    fn = fieldnotes_dir(repo_root)
    fn.mkdir(parents=True, exist_ok=True)
    notes_dir(repo_root).mkdir(exist_ok=True)
    if not config_path(repo_root).exists():
        config_path(repo_root).write_text('# fieldnotes config\nversion = "0.1"\n')
    if not index_path(repo_root).exists():
        index_path(repo_root).write_text(_empty_index_text())
    return fn


def _empty_index_text() -> str:
    return "# Fieldnotes index\n\n_No notes yet. Run `fieldnotes add` to create one._\n"


def iter_note_files(repo_root: Path) -> Iterator[Path]:
    d = notes_dir(repo_root)
    if not d.exists():
        return iter(())
    return iter(sorted(p for p in d.iterdir() if p.suffix == ".md"))


def parse_note_file(path: Path) -> tuple[Note, str]:
    """Parse a note file at `path` into (Note, body_markdown)."""
    text = path.read_text()
    post = frontmatter.loads(text)
    note = Note(**post.metadata)
    return note, post.content


def serialize_note(note: Note, body: str) -> str:
    """Render a Note + body to a frontmatter-formatted string."""
    post = frontmatter.Post(content=body)
    post.metadata = note.model_dump(mode="json")
    out = frontmatter.dumps(post)
    if not out.endswith("\n"):
        out += "\n"
    return out


def write_note(repo_root: Path, note: Note, body: str) -> Path:
    """Write a note to `notes/<id>-<topic>.md` and return its path."""
    notes_dir(repo_root).mkdir(parents=True, exist_ok=True)
    path = notes_dir(repo_root) / note.filename()
    path.write_text(serialize_note(note, body))
    return path


def next_id(repo_root: Path) -> str:
    """Return the next zero-padded id, scanning existing notes."""
    max_id = 0
    for p in iter_note_files(repo_root):
        prefix = p.name.split("-", 1)[0]
        if ID_RE.fullmatch(prefix):
            max_id = max(max_id, int(prefix))
    return f"{max_id + 1:04d}"


def resolve_note_path(repo_root: Path, key: str) -> Path:
    """Resolve `key` (id like '0001' or '1', or a topic slug) to a note path."""
    key = key.strip()
    if not key:
        raise NoteNotFoundError("empty key")
    files = list(iter_note_files(repo_root))
    if not files:
        raise NoteNotFoundError(f"no notes in {notes_dir(repo_root)}")
    if key.isdigit():
        padded = key.zfill(4)
        matches = [p for p in files if p.name.startswith(padded + "-")]
    else:
        if not SLUG_RE.fullmatch(key):
            raise NoteNotFoundError(f"key {key!r} is neither an id nor a topic slug")
        matches = [p for p in files if p.stem.endswith("-" + key)]
    if not matches:
        raise NoteNotFoundError(f"no note matching {key!r}")
    if len(matches) > 1:
        names = [p.name for p in matches]
        raise AmbiguousNoteSelectorError(f"multiple notes match {key!r}: {names}")
    return matches[0]


def read_note(repo_root: Path, key: str) -> tuple[Note, str, Path]:
    """Resolve `key` to a note and parse it. Returns (note, body, path)."""
    path = resolve_note_path(repo_root, key)
    note, body = parse_note_file(path)
    return note, body, path


def list_notes(repo_root: Path) -> list[tuple[Note, Path]]:
    """Parse every well-formed note in the repo. Skips malformed files silently."""
    out: list[tuple[Note, Path]] = []
    for p in iter_note_files(repo_root):
        try:
            note, _body = parse_note_file(p)
        except Exception:
            continue
        out.append((note, p))
    return out


def to_repo_relative(repo_root: Path, p: Path | str) -> str:
    """Normalize a path to a repo-relative posix string for matching."""
    pp = Path(p)
    if pp.is_absolute():
        try:
            return pp.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return pp.as_posix()
    s = pp.as_posix()
    while s.startswith("./"):
        s = s[2:]
    return s


def notes_referencing(repo_root: Path, target: Path | str) -> list[tuple[Note, Path]]:
    """Return notes whose references include `target`, repo-relative match."""
    rel = to_repo_relative(repo_root, target)
    out: list[tuple[Note, Path]] = []
    for note, path in list_notes(repo_root):
        for ref in note.references:
            if to_repo_relative(repo_root, ref.path) == rel:
                out.append((note, path))
                break
    return out
