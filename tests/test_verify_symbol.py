"""Tests for symbol-pinned verification — the v0.5 magic."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from fieldnotes.models import Note, Reference
from fieldnotes.store import write_note
from fieldnotes.symbols import resolve_symbol
from fieldnotes.verify import check_note, check_reference, compute_range_sha, update_shas


def _src(repo: Path, body: str) -> Path:
    p = repo / "src" / "thing.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(body))
    return p


def _pin(repo: Path, src: Path, symbol: str) -> Reference:
    rel = src.relative_to(repo).as_posix()
    lines = list(resolve_symbol(src, symbol))
    sha = compute_range_sha(src, lines)
    return Reference(path=rel, sha=sha, lines=lines, symbol=symbol)


class TestSymbolStaysOk:
    def test_symbol_unchanged(self, repo: Path):
        src = _src(repo, """\
            def foo():
                return 1
            def bar():
                return 2
        """)
        ref = _pin(repo, src, "foo")
        st = check_reference(repo, ref)
        assert st.state == "ok"

    def test_symbol_moves_within_file_unchanged(self, repo: Path):
        src = _src(repo, """\
            def foo():
                return 1
            def bar():
                return 2
        """)
        ref = _pin(repo, src, "foo")
        # Reorder so foo is now below bar — symbol moved but body unchanged.
        src.write_text(dedent("""\
            def bar():
                return 2
            def foo():
                return 1
        """))
        st = check_reference(repo, ref)
        assert st.state == "ok", "moved-but-unchanged symbol must stay ok"
        # The actual_lines should reflect the new location.
        assert st.actual_lines is not None
        assert st.actual_lines != ref.lines

    def test_symbol_grows_outside_pinned_range_unchanged(self, repo: Path):
        # If a new function is added before our pinned function shifting its
        # lines, the symbol's *body* still hashes the same.
        src = _src(repo, """\
            def foo():
                return 1
        """)
        ref = _pin(repo, src, "foo")
        src.write_text(dedent("""\
            def newcomer():
                return 0

            def foo():
                return 1
        """))
        st = check_reference(repo, ref)
        assert st.state == "ok"


class TestSymbolStale:
    def test_symbol_body_edited(self, repo: Path):
        src = _src(repo, """\
            def foo():
                return 1
        """)
        ref = _pin(repo, src, "foo")
        src.write_text(dedent("""\
            def foo():
                return 99
        """))
        st = check_reference(repo, ref)
        assert st.state == "stale"

    def test_symbol_renamed(self, repo: Path):
        src = _src(repo, """\
            def foo():
                return 1
        """)
        ref = _pin(repo, src, "foo")
        src.write_text(dedent("""\
            def renamed():
                return 1
        """))
        st = check_reference(repo, ref)
        assert st.state == "stale"

    def test_file_deleted(self, repo: Path):
        src = _src(repo, """\
            def foo():
                return 1
        """)
        ref = _pin(repo, src, "foo")
        src.unlink()
        st = check_reference(repo, ref)
        assert st.state == "missing"


class TestUpdateShasReResolves:
    def test_repins_lines_when_symbol_moved(self, repo: Path):
        src = _src(repo, """\
            def foo():
                return 1
            def bar():
                return 2
        """)
        ref = _pin(repo, src, "foo")
        n = Note(id="0001", topic="t", title="T", references=[ref])
        path = write_note(repo, n, "body")
        # Move foo below bar without changing its body.
        src.write_text(dedent("""\
            def bar():
                return 2
            def foo():
                return 1
        """))
        status = check_note(repo, n, path)
        # All clean (sha matches because body unchanged).
        assert not status.is_stale
        # Even so, exercise update_shas to confirm it would re-pin lines if
        # they had drifted.
        new_n = update_shas(n, status.references)
        # The new lines should reflect foo's new location (3-4 in the rewritten
        # file).
        assert new_n.references[0].lines == [3, 4]
        assert new_n.references[0].symbol == "foo"
