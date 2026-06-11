"""Tests for v0.10.0 symbol pinning at the CLI surface for TS and SQL.

The v0.7.1 write-time gate dropped symbols on non-Python files; it now
admits TS/JS/SQL. A symbol pin re-resolves on every verify, so a function
that moves within its file (content unchanged) stays `ok`.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
from typer.testing import CliRunner

from fieldnotes.cli import app

runner = CliRunner()

TS = """\
export function helper() {
  return 1;
}

export async function createOrder(input: OrderInput) {
  return db.insert(input);
}
"""

SQL = """\
CREATE TABLE contacts (
    id uuid PRIMARY KEY
);

CREATE POLICY contacts_select ON contacts
    USING (owner_id = auth.uid());
"""


def _add(repo: Path, refs: str) -> str:
    result = runner.invoke(
        app,
        [
            "add",
            "--topic",
            "t",
            "--title",
            "T",
            "--body",
            "b",
            "--refs",
            refs,
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def _first_ref(repo: Path) -> dict:
    note = next((repo / ".fieldnotes" / "notes").glob("0001-*.md"))
    return frontmatter.load(note)["references"][0]


class TestTsSymbolPinning:
    def test_add_persists_ts_symbol(self, repo: Path):
        (repo / "orders.ts").write_text(TS)
        _add(repo, "orders.ts:createOrder")
        ref = _first_ref(repo)
        assert ref["symbol"] == "createOrder"
        assert ref["lines"] == [5, 7]
        assert ref["sha"] is not None

    def test_moved_function_stays_ok(self, repo: Path):
        (repo / "orders.ts").write_text(TS)
        _add(repo, "orders.ts:createOrder")
        # Push the function down; its own content is untouched.
        (repo / "orders.ts").write_text("// prelude\n\n" + TS)
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 0, result.output

    def test_edited_function_goes_stale(self, repo: Path):
        (repo / "orders.ts").write_text(TS)
        _add(repo, "orders.ts:createOrder")
        (repo / "orders.ts").write_text(
            TS.replace("return db.insert(input);", "return db.upsert(input);")
        )
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 1, result.output


class TestSqlSymbolPinning:
    def test_add_persists_sql_symbol(self, repo: Path):
        (repo / "001.sql").write_text(SQL)
        _add(repo, "001.sql:contacts_select")
        ref = _first_ref(repo)
        assert ref["symbol"] == "contacts_select"
        assert ref["lines"] == [5, 6]

    def test_unrelated_edit_stays_ok(self, repo: Path):
        (repo / "001.sql").write_text(SQL)
        _add(repo, "001.sql:contacts_select")
        (repo / "001.sql").write_text(SQL.replace("id uuid", "id uuid NOT NULL"))
        result = runner.invoke(app, ["verify", "--check", "--repo", str(repo)])
        assert result.exit_code == 0, result.output


class TestUnsupportedStillDegrades:
    def test_go_symbol_degrades_to_whole_file(self, repo: Path):
        (repo / "main.go").write_text("func thing() {}\n")
        _add(repo, "main.go:thing")
        ref = _first_ref(repo)
        assert ref["symbol"] is None
        assert ref["sha"] is not None  # whole-file pin
