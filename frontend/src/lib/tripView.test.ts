import { describe, expect, it } from "vitest";

import type { PendingOp } from "./outbox";
import { mergeTrip, type LocalTrip, type TripHeader, type TripItemOut } from "./trips";
import { deriveView, OTHER_MEAL, OTHER_SECTION } from "./tripView";

function header(overrides: Partial<TripHeader> = {}): TripHeader {
  return {
    id: "trip-1",
    status: "active",
    version: 10,
    plan_id: null,
    store_name: "Sample Store",
    created_at: "2026-10-06T15:00:00Z",
    created_by: null,
    estimate_cents: 14_200,
    savings_cents: 0,
    not_priced: 0,
    prices_as_of: null,
    actual_total_cents: null,
    finished_at: null,
    status_by: null,
    status_ts: 100,
    item_count: 0,
    done_count: 0,
    missed_count: 0,
    ...overrides,
  };
}

function item(id: string, overrides: Partial<TripItemOut> = {}): TripItemOut {
  return {
    id,
    line_key: id,
    item_id: null,
    name: id,
    image_url: null,
    product_url: null,
    size_text: null,
    qty_text: "1",
    quantity: "1",
    unit: "package",
    unit_cents: 100,
    line_cents: 100,
    regular_cents: 100,
    on_sale: false,
    sale_ends: null,
    section_key: "cat:produce",
    section_label: "Produce",
    section_order: 100,
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
    ...overrides,
  };
}

function trip(items: TripItemOut[], overrides: Partial<TripHeader> = {}): LocalTrip {
  const merged = mergeTrip(undefined, { header: header(overrides), items, complete: true }, 0);
  if (!merged) throw new Error("no trip");
  return merged;
}

let seq = 0;
function base(ts: number) {
  seq += 1;
  return { op_id: `op-${String(seq)}`, trip_id: "trip-1", v: 1, client_ts: ts, client_seq: seq };
}

function setState(itemId: string, state: TripItemOut["state"], ts: number): PendingOp {
  return { ...base(ts), kind: "item.set_state", item_id: itemId, state };
}

function setNote(itemId: string, note: string | null, ts: number): PendingOp {
  return { ...base(ts), kind: "item.set_note", item_id: itemId, note };
}

function finish(ts: number, total: number | null = null): PendingOp {
  return { ...base(ts), kind: "trip.finish", actual_total_cents: total };
}

function reopen(ts: number): PendingOp {
  return { ...base(ts), kind: "trip.reopen" };
}

const meal = (meal_id: string, name: string) => ({ meal_id, name });
const names = (items: { name: string }[]) => items.map((entry) => entry.name);

describe("deriveView: grouping", () => {
  const items = [
    item("Penne", {
      section_key: "aisle:12",
      section_label: "Aisle 12",
      section_order: 1012,
      bay: 4,
    }),
    item("Beans", { section_key: "aisle:9", section_label: "Aisle 9", section_order: 1009 }),
    item("Limes", { section_order: 100 }),
    item("Onions", { section_order: 100 }),
    item("Salsa", {
      section_key: "aisle:12",
      section_label: "Aisle 12",
      section_order: 1012,
      bay: 1,
    }),
    item("Candles", { section_key: null, section_label: null, section_order: 9900 }),
  ];

  it("walks the store: sections in walking order, then shelf, then name", () => {
    const view = deriveView(trip(items), [], "aisle");
    expect(view.groups.map((group) => [group.label, names(group.items)])).toEqual([
      ["Produce", ["Limes", "Onions"]],
      ["Aisle 9", ["Beans"]],
      ["Aisle 12", ["Salsa", "Penne"]],
      [OTHER_SECTION.label, ["Candles"]],
    ]);
    expect(view.groups.at(-1)?.key).toBe(OTHER_SECTION.key);
  });

  it("groups by each item's first meal, meals in the order they first appear down the list", () => {
    const view = deriveView(
      trip([
        item("Tortillas", { position: 0, used_by: [meal("tacos", "Tacos")] }),
        item("Beef", { position: 1, used_by: [meal("chili", "Chili"), meal("tacos", "Tacos")] }),
        item("Beans", { position: 2, used_by: [meal("chili", "Chili")] }),
        item("Milk", { position: 3, used_by: [] }),
        item("Cumin", { position: 4, used_by: [meal("soup", "Soup")], state: "done" }),
      ]),
      [],
      "meal",
    );
    expect(view.groups.map((group) => [group.label, names(group.items)])).toEqual([
      ["Tacos", ["Tortillas"]],
      ["Chili", ["Beans", "Beef"]],
      [OTHER_MEAL.label, ["Milk"]],
    ]);
  });

  it("leaves out items taken off the list, everywhere", () => {
    const view = deriveView(
      trip([
        item("Milk"),
        item("Eggs", { removed: true }),
        item("Bread", { removed: true, state: "done" }),
      ]),
      [],
      "aisle",
    );
    expect(view.groups.flatMap((group) => names(group.items))).toEqual(["Milk"]);
    expect(view.done).toEqual([]);
    expect(view.total).toBe(1);
  });
});

describe("deriveView: unsent ops on top", () => {
  it("lays ops over the server state in client_seq order, marking those items pending", () => {
    const view = deriveView(
      trip([item("Milk"), item("Eggs"), item("Bread")]),
      [
        setState("Milk", "done", 500),
        setState("Eggs", "done", 501),
        setState("Eggs", "todo", 502), // the Undo, not yet sent
        setNote("Bread", "Get the seeded one", 503),
      ],
      "aisle",
      { me: "member-1" },
    );
    expect(names(view.done)).toEqual(["Milk"]);
    expect(view.done[0]).toMatchObject({ state_by: "member-1", pending: true });
    const todo = view.groups.flatMap((group) => group.items);
    expect(todo.map((entry) => [entry.name, entry.pending, entry.note])).toEqual([
      ["Bread", true, "Get the seeded one"],
      ["Eggs", true, null],
    ]);
    expect(view.pendingCount).toBe(4);
  });

  it("doesn't show an op the server will supersede: someone changed it later", () => {
    const view = deriveView(
      trip([item("Milk", { state: "missed", state_ts: 900, state_by: "member-2" })]),
      [setState("Milk", "done", 800)],
      "aisle",
    );
    expect(names(view.missed)).toEqual(["Milk"]);
    expect(view.missed[0]?.pending).toBe(false);
    expect(view.pendingCount).toBe(1);
  });

  it("ignores ops for other trips and for items no longer on the list", () => {
    const other: PendingOp = { ...setState("Milk", "done", 500), trip_id: "trip-2" };
    const view = deriveView(
      trip([item("Milk"), item("Eggs", { removed: true })]),
      [other, setState("Eggs", "done", 501)],
      "aisle",
    );
    expect(view.done).toEqual([]);
    expect(view.pendingCount).toBe(1);
  });

  it("shows a finish waiting to be sent, and a reopen after it", () => {
    const finishing = deriveView(trip([item("Milk")]), [finish(500, 6_400)], "aisle");
    expect(finishing.status).toBe("finished");
    expect(finishing.statusPending).toBe(true);
    expect(finishing.header.actual_total_cents).toBe(6_400);
    expect(finishing.trip.header.status).toBe("active"); // the server's word is kept beside it

    const reopened = deriveView(trip([item("Milk")]), [finish(500), reopen(501)], "aisle");
    expect(reopened.status).toBe("active");

    const lateFinish = deriveView(
      trip([item("Milk")], { status: "finished", status_ts: 900, actual_total_cents: null }),
      [finish(800, 5_000)],
      "aisle",
    );
    expect(lateFinish.status).toBe("finished");
    expect(lateFinish.header.actual_total_cents).toBe(5_000); // it can still say what was paid

    const staleReopen = deriveView(
      trip([item("Milk")], { status: "finished", status_ts: 900 }),
      [reopen(800)],
      "aisle",
    );
    expect(staleReopen.status).toBe("finished");
    expect(staleReopen.statusPending).toBe(false);
  });
});

describe("deriveView: progress and money", () => {
  it("counts done of total, with couldn't-find as handled too", () => {
    const view = deriveView(
      trip([
        item("Milk", { state: "done" }),
        item("Eggs", { state: "done" }),
        item("Saffron", { state: "missed" }),
        item("Bread"),
        item("Gone", { removed: true, state: "done" }),
      ]),
      [setState("Bread", "done", 500)],
      "aisle",
    );
    expect(view).toMatchObject({ doneCount: 3, missedCount: 1, handledCount: 4, total: 4 });
  });

  it("adds up what's in the cart from the checked items, and keeps the estimate", () => {
    const view = deriveView(
      trip([
        item("Milk", { state: "done", line_cents: 349 }),
        item("Candles", { state: "done", line_cents: null }),
        item("Steak", { line_cents: 1_899 }),
        item("Saffron", { state: "missed", line_cents: 999 }),
      ]),
      [setState("Steak", "done", 500)],
      "aisle",
    );
    expect(view.inCartCents).toBe(349 + 1_899);
    expect(view.estimateCents).toBe(14_200);
  });

  it("lists the most recently checked first", () => {
    const view = deriveView(
      trip([
        item("Milk", { state: "done", state_ts: 300 }),
        item("Eggs", { state: "done", state_ts: 100 }),
        item("Bread"),
      ]),
      [setState("Bread", "done", 500)],
      "aisle",
    );
    expect(names(view.done)).toEqual(["Bread", "Milk", "Eggs"]);
  });
});

describe("deriveView: rows checked a moment ago", () => {
  const items = [
    item("Beef", {
      section_key: "aisle:0",
      section_label: "Meat",
      section_order: 500,
      state: "done",
      state_ts: 5,
    }),
    item("Beans", { section_key: "aisle:9", section_label: "Aisle 9", section_order: 1009 }),
  ];

  it("keep their place, even as their section's last row, and count as checked", () => {
    const view = deriveView(trip(items), [], "aisle", { lingering: new Set(["Beef"]) });
    expect(view.groups.map((group) => [group.label, names(group.items)])).toEqual([
      ["Meat", ["Beef"]],
      ["Aisle 9", ["Beans"]],
    ]);
    expect(view.done).toEqual([]);
    expect(view.doneCount).toBe(1);
    expect(view.inCartCents).toBe(100);
  });

  it("join Done once they've folded away", () => {
    const view = deriveView(trip(items), [], "aisle");
    expect(view.groups.map((group) => group.label)).toEqual(["Aisle 9"]);
    expect(names(view.done)).toEqual(["Beef"]);
  });
});
