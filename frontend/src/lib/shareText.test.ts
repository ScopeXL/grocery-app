import { describe, expect, it } from "vitest";

import type { components } from "../api/schema";
import { tripText } from "./shareText";

type TripItem = components["schemas"]["TripItemOut"];

function item(name: string, extra: Partial<TripItem> = {}): TripItem {
  return {
    id: name,
    line_key: name,
    item_id: name,
    name,
    image_url: null,
    product_url: null,
    size_text: null,
    qty_text: "1 package",
    quantity: "1",
    unit: "package",
    unit_cents: null,
    line_cents: null,
    regular_cents: null,
    on_sale: false,
    sale_ends: null,
    section_key: "cat:other",
    section_label: "Other",
    section_order: 9900,
    aisle_side: null,
    bay: 0,
    position: 0,
    used_by: [],
    warnings: [],
    state: "todo",
    state_ts: 0,
    state_by: null,
    note: null,
    note_ts: 0,
    note_by: null,
    version: 1,
    removed: false,
    ...extra,
  };
}

describe("share as text", () => {
  it("lists items by section in walking order, marking what's done", () => {
    const text = tripText("Shopping list, Tue Oct 6", [
      item("Sample Milk", { section_label: "Dairy", section_order: 9100, qty_text: "1 gal" }),
      item("Sample Onions", { section_label: "Produce", section_order: 100, state: "done" }),
      item("Sample Beans", { section_label: "Aisle 10", section_order: 1010, state: "missed" }),
      item("Gone", { removed: true }),
    ]);
    expect(text).toBe(
      [
        "Shopping list, Tue Oct 6",
        "",
        "Produce",
        "- ✓ Sample Onions: 1 package",
        "",
        "Aisle 10",
        "- ✗ Sample Beans: 1 package",
        "",
        "Dairy",
        "- Sample Milk: 1 gal",
      ].join("\n"),
    );
  });
});
