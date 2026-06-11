"""Tests for v0.10.0 TypeScript/JavaScript symbol resolution.

Regex + brace-balance based (no parser dependency). Top-level declarations
only; a wrong range surfaces as stale on the next verify, never silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fieldnotes.symbols import resolve_symbol

TS = """\
import { db } from "./db";

export async function createOrder(input: OrderInput): Promise<Order> {
  const order = await db.insert(input);
  if (!order) {
    throw new Error("insert failed");
  }
  return order;
}

export const useOrders = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  return { orders, setOrders };
};

export default function handler(req: Request) {
  return new Response("ok");
}

export class OrderService {
  private db: Db;

  async list(): Promise<Order[]> {
    return this.db.query("orders");
  }
}

export interface OrderInput {
  sku: string;
  qty: number;
}

export type OrderState = {
  status: "open" | "closed";
};

export const MAX_ORDERS = 100;
"""


@pytest.fixture()
def ts_file(tmp_path: Path) -> Path:
    p = tmp_path / "orders.ts"
    p.write_text(TS)
    return p


class TestTsResolution:
    def test_async_function(self, ts_file: Path):
        assert resolve_symbol(ts_file, "createOrder") == (3, 9)

    def test_arrow_const(self, ts_file: Path):
        assert resolve_symbol(ts_file, "useOrders") == (11, 14)

    def test_default_export_function(self, ts_file: Path):
        assert resolve_symbol(ts_file, "handler") == (16, 18)

    def test_class(self, ts_file: Path):
        assert resolve_symbol(ts_file, "OrderService") == (20, 26)

    def test_interface(self, ts_file: Path):
        assert resolve_symbol(ts_file, "OrderInput") == (28, 31)

    def test_type_alias(self, ts_file: Path):
        assert resolve_symbol(ts_file, "OrderState") == (33, 35)

    def test_single_line_const(self, ts_file: Path):
        assert resolve_symbol(ts_file, "MAX_ORDERS") == (37, 37)

    def test_not_found(self, ts_file: Path):
        assert resolve_symbol(ts_file, "nope") is None

    def test_tsx_jsx_mjs_suffixes(self, tmp_path: Path):
        for suffix in (".tsx", ".jsx", ".js", ".mjs"):
            p = tmp_path / f"c{suffix}"
            p.write_text("export function Widget() {\n  return null;\n}\n")
            assert resolve_symbol(p, "Widget") == (1, 3), suffix

    def test_name_must_match_exactly(self, tmp_path: Path):
        p = tmp_path / "f.ts"
        p.write_text("export function createOrderItem() {\n  return 1;\n}\n")
        assert resolve_symbol(p, "createOrder") is None
