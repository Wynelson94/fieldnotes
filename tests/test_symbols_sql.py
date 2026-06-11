"""Tests for v0.10.0 SQL symbol resolution.

CREATE-statement blocks: TABLE / POLICY / FUNCTION / TRIGGER / VIEW / INDEX.
A block runs to its terminating `;`, with `$$`-quoted function bodies
respected. Names match the last identifier component, unquoted,
case-insensitively — so `public.contacts` and `"contacts"` both resolve
via the symbol `contacts`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fieldnotes.symbols import resolve_symbol

SQL = """\
-- contacts schema
CREATE TABLE public.contacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES auth.users (id),
    prospect_id uuid REFERENCES prospects (id)
);

CREATE POLICY contacts_select ON public.contacts
    FOR SELECT
    USING (owner_id = auth.uid());

CREATE OR REPLACE FUNCTION handle_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER contacts_updated
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();

create index contacts_owner_idx on contacts (owner_id);
"""


@pytest.fixture()
def sql_file(tmp_path: Path) -> Path:
    p = tmp_path / "001_contacts.sql"
    p.write_text(SQL)
    return p


class TestSqlResolution:
    def test_table_with_schema_qualifier(self, sql_file: Path):
        assert resolve_symbol(sql_file, "contacts") == (2, 6)

    def test_policy(self, sql_file: Path):
        assert resolve_symbol(sql_file, "contacts_select") == (8, 10)

    def test_function_with_dollar_body(self, sql_file: Path):
        # The `;` lines inside $$...$$ must not end the block early.
        assert resolve_symbol(sql_file, "handle_updated_at") == (12, 18)

    def test_trigger(self, sql_file: Path):
        assert resolve_symbol(sql_file, "contacts_updated") == (20, 22)

    def test_lowercase_create(self, sql_file: Path):
        assert resolve_symbol(sql_file, "contacts_owner_idx") == (24, 24)

    def test_quoted_name(self, tmp_path: Path):
        p = tmp_path / "m.sql"
        p.write_text('CREATE POLICY "row_guard" ON t\n    USING (true);\n')
        assert resolve_symbol(p, "row_guard") == (1, 2)

    def test_not_found(self, sql_file: Path):
        assert resolve_symbol(sql_file, "missing_thing") is None
