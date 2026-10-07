import "fake-indexeddb/auto";

import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import { createLocalDb, type LocalDb } from "./db";
import {
  createTrips,
  eventSince,
  mergeTrip,
  photoUrls,
  type LocalTrip,
  type TripHeader,
  type TripItemOut,
  type TripOut,
  type TripsOut,
  type TripsTransport,
} from "./trips";

const NOW = Date.parse("2026-10-06T18:00:00Z");
const HOUR = 60 * 60 * 1000;

function header(overrides: Partial<TripHeader> = {}): TripHeader {
  return {
    id: "trip-1",
    status: "active",
    version: 10,
    plan_id: null,
    store_name: "Sample Store",
    created_at: "2026-10-06T15:00:00Z",
    created_by: null,
    estimate_cents: 4200,
    savings_cents: 0,
    not_priced: 0,
    prices_as_of: null,
    actual_total_cents: null,
    finished_at: null,
    status_by: null,
    status_ts: 0,
    item_count: 2,
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
    name: "Sample Whole Milk",
    image_url: null,
    product_url: null,
    size_text: null,
    qty_text: "1 gallon",
    quantity: "1",
    unit: "package",
    unit_cents: 349,
    line_cents: 349,
    regular_cents: 349,
    on_sale: false,
    sale_ends: null,
    section_key: "cat:dairy",
    section_label: "Dairy",
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

const parent = { id: "member-1", name: "Sample Parent", marker_color: "basil" };

function tripOut(
  items: TripItemOut[],
  overrides: Partial<TripHeader> = {},
  complete = true,
): TripOut {
  return { ...header(overrides), members: [parent], items, complete };
}

function local(items: TripItemOut[], overrides: Partial<TripHeader> = {}): LocalTrip {
  const merged = mergeTrip(undefined, { header: header(overrides), items, complete: true }, NOW);
  if (!merged) throw new Error("no trip");
  return merged;
}

let count = 0;
function setup(transport: Partial<TripsTransport> = {}) {
  count += 1;
  const db = createLocalDb({ name: `trips-test-${String(count)}` });
  const released: { urls: string[]; keep: string[] }[] = [];
  const listTrips = vi.fn(
    transport.listTrips ??
      (() => Promise.resolve<TripsOut>({ active: [], finished: [], more: false })),
  );
  const getTrip = vi.fn(transport.getTrip ?? (() => Promise.reject(new Error("unexpected"))));
  const trips = createTrips({
    db,
    transport: { listTrips, getTrip },
    now: () => NOW,
    releasePhotos: (urls, keep) => released.push({ urls, keep }),
  });
  return { db, trips, listTrips, getTrip, released };
}

async function storedTrips(db: LocalDb) {
  return db.withDb((conn) => conn.getAll("trips"));
}

async function storedOps(db: LocalDb) {
  return db.withDb((conn) => conn.getAll("outbox"));
}

describe("mergeTrip", () => {
  it("starts a trip from a full download, complete up to its version", () => {
    const trip = local([item("a"), item("b")]);
    expect(Object.keys(trip.items)).toEqual(["a", "b"]);
    expect(trip.syncedVersion).toBe(10);
    expect(trip.savedAt).toBe(NOW);
    expect(mergeTrip(undefined, { items: [item("a")] })).toBeUndefined();
  });

  it("replaces the header only with one at least as new", () => {
    const trip = local([]);
    const older = mergeTrip(trip, { header: header({ version: 9, done_count: 5 }) });
    expect(older).toBe(trip);
    const same = mergeTrip(trip, { header: header({ version: 10, done_count: 1 }) });
    expect(same?.header.done_count).toBe(1);
    const newer = mergeTrip(trip, { header: header({ version: 11, status: "finished" }) });
    expect(newer?.header.status).toBe("finished");
  });

  it("replaces an item only with a newer version, and adds ones it hasn't seen", () => {
    const trip = local([item("a", { version: 5, state: "done" })]);
    const sameVersion = mergeTrip(trip, { items: [item("a", { version: 5, state: "missed" })] });
    expect(sameVersion).toBe(trip);
    const olderVersion = mergeTrip(trip, { items: [item("a", { version: 4, state: "todo" })] });
    expect(olderVersion).toBe(trip);
    const next = mergeTrip(trip, {
      items: [item("a", { version: 6, state: "missed" }), item("b", { version: 3 })],
    });
    expect(next?.items.a?.state).toBe("missed");
    expect(next?.items.b?.version).toBe(3);
    expect(trip.items.a?.state).toBe("done"); // the original is never changed
  });

  it("keeps items taken off the list, marked removed", () => {
    const trip = local([item("a", { version: 5 })]);
    const next = mergeTrip(trip, {
      header: header({ version: 11 }),
      items: [item("a", { version: 11, removed: true })],
      since: 10,
    });
    expect(next?.items.a?.removed).toBe(true);
  });

  it("treats items missing from a full snapshot as removed, unless they changed after it", () => {
    const trip = local(
      [item("kept", { version: 5 }), item("gone", { version: 3 }), item("newer", { version: 12 })],
      { version: 12 },
    );
    const next = mergeTrip(trip, {
      header: header({ version: 11 }),
      items: [item("kept", { version: 5 })],
      complete: true,
    });
    expect(next?.items.gone?.removed).toBe(true);
    expect(next?.items.newer?.removed).toBe(false);
    expect(next?.items.kept?.removed).toBe(false);
    expect(next?.header.version).toBe(12); // the older snapshot's header doesn't win
  });

  it("returns the very same trip when nothing is new", () => {
    const trip = local([item("a", { version: 5 })]);
    const again = mergeTrip(trip, {
      header: header(),
      members: [],
      items: [item("a", { version: 5 })],
      since: 10,
    });
    expect(again).toBe(trip);
  });

  it("moves its complete-up-to version only when nothing can be missing", () => {
    const trip = local([]);
    // A delta from where we were: complete again.
    expect(mergeTrip(trip, { header: header({ version: 14 }), since: 10 })?.syncedVersion).toBe(14);
    // News that starts after a gap: the header moves on, but we still ask from 10.
    const gap = mergeTrip(trip, {
      header: header({ version: 14 }),
      items: [item("a", { version: 14 })],
      since: 12,
    });
    expect(gap?.header.version).toBe(14);
    expect(gap?.syncedVersion).toBe(10);
    // A bare header (from the trips list) never claims completeness.
    expect(mergeTrip(trip, { header: header({ version: 11 }) })?.syncedVersion).toBe(10);
  });

  it("reads a live event as one whole write: from just before its oldest item", () => {
    const items = [item("a", { version: 13 }), item("b", { version: 12 })];
    expect(eventSince(header({ version: 14 }), items)).toBe(11);
    expect(eventSince(header({ version: 14 }), [])).toBe(13);
  });

  it("lists a trip's photos once each, in list order", () => {
    const trip = local([
      item("b", { position: 2, image_url: "https://www.kroger.com/product/images/medium/front/2" }),
      item("a", { position: 1, image_url: "https://www.kroger.com/product/images/medium/front/1" }),
      item("c", { position: 3, image_url: "https://www.kroger.com/product/images/medium/front/1" }),
      item("d", { position: 4, image_url: null }),
    ]);
    expect(photoUrls(trip)).toEqual([
      "https://www.kroger.com/product/images/medium/front/1",
      "https://www.kroger.com/product/images/medium/front/2",
    ]);
  });
});

describe("downloadTrip", () => {
  it("downloads the whole trip the first time, then only what changed", async () => {
    const { trips, getTrip, db } = setup({
      getTrip: (_id, since) =>
        Promise.resolve(
          since === undefined
            ? tripOut([item("a", { version: 4 }), item("b", { version: 9 })])
            : tripOut([item("a", { version: 12, state: "done" })], { version: 12 }, false),
        ),
    });
    const first = await trips.download("trip-1");
    expect(getTrip).toHaveBeenLastCalledWith("trip-1", undefined);
    expect(first?.syncedVersion).toBe(10);
    expect(first?.members).toEqual([parent]);

    const second = await trips.download("trip-1");
    expect(getTrip).toHaveBeenLastCalledWith("trip-1", 10);
    expect(second?.items.a?.state).toBe("done");
    expect(second?.items.b?.version).toBe(9); // a delta never drops what it doesn't mention
    expect(second?.syncedVersion).toBe(12);
    expect((await storedTrips(db))[0]?.header.version).toBe(12);
  });

  it("drops a trip the server no longer has, with its unsent ops", async () => {
    const { trips, db } = setup({
      getTrip: () => Promise.reject(new ApiError(404, "trip_not_found", "Not found")),
    });
    await trips.remember(tripOut([item("a")]));
    await db.withDb((conn) =>
      conn.put("outbox", {
        op_id: "op-1",
        trip_id: "trip-1",
        kind: "item.set_state",
        item_id: "a",
        state: "done",
        v: 1,
        client_ts: 1,
        client_seq: 1,
      }),
    );
    const dropped = vi.fn();
    trips.onDropped(dropped);

    expect(await trips.download("trip-1")).toBeUndefined();
    expect(trips.store.get("trip-1")).toBeUndefined();
    expect(await storedTrips(db)).toEqual([]);
    expect(await storedOps(db)).toEqual([]);
    expect(dropped).toHaveBeenCalledWith("trip-1");
  });

  it("keeps the trip when a 404 doesn't come from the server's trips", async () => {
    const { trips } = setup({
      getTrip: () => Promise.reject(new ApiError(404, "error", "Not Found")),
    });
    await trips.remember(tripOut([item("a")]));
    await expect(trips.download("trip-1")).rejects.toThrow("Not Found");
    expect(trips.store.get("trip-1")).toBeDefined();
  });
});

describe("rememberTrip", () => {
  it("keeps a trip a screen already has, without fetching it", async () => {
    const { trips, getTrip, db } = setup();
    await trips.remember(tripOut([item("a"), item("b")], { version: 20 }));
    expect(getTrip).not.toHaveBeenCalled();
    const kept = trips.store.get("trip-1");
    expect(kept?.syncedVersion).toBe(20);
    expect(Object.keys(kept?.items ?? {})).toEqual(["a", "b"]);
    expect(await storedTrips(db)).toHaveLength(1);
  });

  it("survives a restart: a new session starts from what's saved on this phone", async () => {
    const { trips, db } = setup();
    await trips.remember(tripOut([item("a")]));
    const restarted = createTrips({ db, now: () => NOW, releasePhotos: () => undefined });
    expect(restarted.store.get("trip-1")).toBeUndefined();
    await restarted.hydrate();
    expect(restarted.store.get("trip-1")?.header.version).toBe(10);
  });
});

describe("applyTripEvent", () => {
  it("merges trip events only into trips kept on this phone", async () => {
    const { trips, getTrip } = setup();
    await trips.applyEvent({
      type: "trip.items",
      trip_id: "trip-9",
      trip: header({ id: "trip-9", version: 3 }),
      items: [item("x", { version: 3 })],
    });
    expect(trips.store.get("trip-9")).toBeUndefined();
    expect(getTrip).not.toHaveBeenCalled();

    await trips.remember(tripOut([item("a", { version: 4 })]));
    await trips.applyEvent({
      type: "trip.items",
      trip_id: "trip-1",
      trip: header({ version: 11 }),
      items: [item("a", { version: 11, state: "done", state_by: "member-1" })],
    });
    const trip = trips.store.get("trip-1");
    expect(trip?.items.a?.state).toBe("done");
    expect(trip?.syncedVersion).toBe(11); // the event followed straight on from version 10

    await trips.applyEvent({
      type: "trip.state",
      trip_id: "trip-1",
      trip: header({ version: 12, status: "finished" }),
    });
    expect(trips.store.get("trip-1")?.header.status).toBe("finished");
  });

  it("downloads a trip created on another phone", async () => {
    const { trips, getTrip } = setup({ getTrip: () => Promise.resolve(tripOut([item("a")])) });
    await trips.applyEvent({ type: "trip.created", trip_id: "trip-1", trip: header() });
    expect(getTrip).toHaveBeenCalledWith("trip-1", undefined);
    expect(trips.store.get("trip-1")).toBeDefined();
  });

  it("lets go of a trip's photos when it's finished, keeping ones another trip shows", async () => {
    const { trips, released } = setup();
    const photo = (n: number) => `https://www.kroger.com/product/images/medium/front/${String(n)}`;
    await trips.remember(tripOut([item("a", { image_url: photo(1) })], { id: "trip-2" }));
    await trips.remember(
      tripOut([item("a", { image_url: photo(1) }), item("b", { image_url: photo(2) })]),
    );
    await trips.applyEvent({
      type: "trip.state",
      trip_id: "trip-1",
      trip: header({ version: 11, status: "finished" }),
    });
    expect(released).toEqual([{ urls: [photo(1), photo(2)], keep: [photo(1)] }]);
  });
});

describe("syncActiveTrips", () => {
  it("downloads every active trip and tidies away old or unlisted ones", async () => {
    const finishedLongAgo = new Date(NOW - 30 * HOUR).toISOString();
    const finishedRecently = new Date(NOW - 2 * HOUR).toISOString();
    const { trips, db } = setup({
      listTrips: () =>
        Promise.resolve({
          active: [header({ id: "trip-new" })],
          finished: [
            header({ id: "trip-old", status: "finished", finished_at: finishedLongAgo }),
            header({ id: "trip-recent", status: "finished", finished_at: finishedRecently }),
            header({ id: "trip-busy", status: "finished", finished_at: finishedLongAgo }),
          ],
          more: false,
        }),
      getTrip: (id) => Promise.resolve(tripOut([item("a")], { id })),
    });
    for (const id of ["trip-old", "trip-recent", "trip-gone", "trip-busy"]) {
      await trips.remember(tripOut([item("a")], { id, version: 5 }));
    }
    trips.keepWhile((id) => id === "trip-busy"); // it still has unsent ops

    expect(await trips.syncActive()).toBe(true);
    const kept = trips.store
      .list()
      .map((trip) => trip.header.id)
      .sort();
    expect(kept).toEqual(["trip-busy", "trip-new", "trip-recent"]);
    expect(trips.store.get("trip-recent")?.header.status).toBe("finished");
    expect((await storedTrips(db)).map((trip) => trip.header.id).sort()).toEqual(kept);
  });

  it("says so when the server can't be reached, and keeps everything", async () => {
    const { trips } = setup({
      listTrips: () => Promise.reject(new ApiError(0, "offline", "Offline")),
    });
    await trips.remember(tripOut([item("a")]));
    expect(await trips.syncActive()).toBe(false);
    expect(trips.store.get("trip-1")).toBeDefined();
  });
});
