import "fake-indexeddb/auto";

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import { createLocalDb, type LocalDb } from "./db";
import {
  BACKOFF_MS,
  FLUSH_DEBOUNCE_MS,
  FLUSH_EVERY_MS,
  MAX_BATCH_BYTES,
  MAX_OPS_PER_BATCH,
  createOutbox,
  type OpsIn,
  type OpsOut,
  type OpsTransport,
  type PendingOp,
  type Timers,
} from "./outbox";
import { createTrips, type TripHeader, type TripItemOut } from "./trips";

type Handle = ReturnType<typeof setTimeout>;
type Handler = (tripId: string, body: OpsIn, call: number) => Promise<OpsOut>;

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
    item_count: 1,
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

/** The server accepting every op in the batch. */
function answer(
  tripId: string,
  body: OpsIn,
  status: "applied" | "superseded" | "duplicate" | "rejected" = "applied",
): OpsOut {
  const version = body.known_version + body.ops.length;
  return {
    trip_id: tripId,
    trip_version: version,
    trip_status: "active",
    server_time: 0,
    results: body.ops.map((op) => ({ op_id: op.op_id, status })),
    items: [],
    trip: header({ id: tripId, version }),
  };
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (error: unknown) => void = () => undefined;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

/** Timers that only run when a test says so. */
function manualTimers() {
  let next = 1;
  const scheduled = new Map<number, { callback: () => void; ms: number; repeat: boolean }>();
  const add = (callback: () => void, ms: number, repeat: boolean): Handle => {
    const id = next++;
    scheduled.set(id, { callback, ms, repeat });
    return id;
  };
  const cancel = (handle: Handle | undefined): void => {
    if (handle !== undefined) scheduled.delete(handle);
  };
  const timers: Timers = {
    setTimeout: (callback, ms) => add(callback, ms, false),
    clearTimeout: cancel,
    setInterval: (callback, ms) => add(callback, ms, true),
    clearInterval: cancel,
  };
  return {
    timers,
    delays: () => [...scheduled.values()].filter((t) => !t.repeat).map((t) => t.ms),
    /** Run every timer scheduled for exactly `ms`. */
    fire: (ms: number): void => {
      for (const [id, timer] of [...scheduled]) {
        if (timer.ms !== ms) continue;
        if (!timer.repeat) scheduled.delete(id);
        timer.callback();
      }
    },
  };
}

function fakePage() {
  const listeners = new Map<string, Set<() => void>>();
  return {
    visibilityState: "visible" as DocumentVisibilityState,
    addEventListener: (type: string, listener: () => void) => {
      const set = listeners.get(type) ?? new Set();
      set.add(listener);
      listeners.set(type, set);
    },
    removeEventListener: (type: string, listener: () => void) => {
      listeners.get(type)?.delete(listener);
    },
    fire: (type: string) => {
      for (const listener of listeners.get(type) ?? []) listener();
    },
  };
}

async function until(check: () => boolean): Promise<void> {
  for (let tries = 0; tries < 200; tries += 1) {
    if (check()) return;
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error("Gave up waiting");
}

let count = 0;
function newDbName(): string {
  count += 1;
  return `outbox-test-${String(count)}`;
}

function setup(
  handler: Handler = (tripId, body) => Promise.resolve(answer(tripId, body)),
  options: { dbName?: string; browserTimers?: boolean } = {},
) {
  const db = createLocalDb({ name: options.dbName ?? newDbName(), randomId: () => "client-1" });
  const trips = createTrips({
    db,
    transport: {
      listTrips: () => Promise.reject(new Error("not used")),
      getTrip: () => Promise.reject(new Error("not used")),
    },
    releasePhotos: () => undefined,
  });
  const calls: { tripId: string; body: OpsIn; keepalive: boolean }[] = [];
  const transport: OpsTransport = {
    postOps: (tripId, body, { keepalive }) => {
      calls.push({ tripId, body, keepalive });
      return handler(tripId, body, calls.length);
    },
  };
  const manual = manualTimers();
  const page = fakePage();
  const win = fakePage();
  let opNumber = 0;
  let clock = 1_000;
  const outbox = createOutbox({
    db,
    trips,
    transport,
    ...(options.browserTimers ? {} : { timers: manual.timers }),
    random: () => 0.5,
    now: () => 5_000,
    timestamp: () => (clock += 1),
    randomId: () => `op-${String((opNumber += 1)).padStart(5, "0")}`,
    document: page,
    window: win,
  });
  return { outbox, trips, db, calls, manual, page, win };
}

function states(ops: readonly PendingOp[]): (string | null)[] {
  return ops.map((op) => (op.kind === "item.set_state" ? op.state : null));
}

async function storedOps(db: LocalDb): Promise<PendingOp[]> {
  return db.withDb((conn) => conn.getAll("outbox"));
}

afterEach(() => {
  vi.useRealTimers();
});

describe("outbox: adding ops", () => {
  it("an Undo before sending leaves one op, and only that op is sent", async () => {
    const { outbox, calls, db } = setup();
    await outbox.setState("trip-1", "item-1", "done");
    await outbox.setState("trip-1", "item-1", "todo");
    expect(states(outbox.pending("trip-1"))).toEqual(["todo"]);
    expect(states(await storedOps(db))).toEqual(["todo"]);

    await outbox.flush();
    expect(calls).toHaveLength(1);
    expect(calls[0]?.body.ops).toMatchObject([{ kind: "item.set_state", state: "todo" }]);
    expect(outbox.pending()).toEqual([]);
  });

  it("never replaces an op that's on its way to the server", async () => {
    const gate = deferred<OpsOut>();
    const { outbox, calls, db } = setup((tripId, body, call) =>
      call === 1 ? gate.promise : Promise.resolve(answer(tripId, body)),
    );
    await outbox.setState("trip-1", "item-1", "done");
    const flushing = outbox.flush();
    await until(() => calls.length === 1);

    await outbox.setState("trip-1", "item-1", "todo"); // the Undo, while the check-off is out
    expect(states(outbox.pending())).toEqual(["done", "todo"]);
    expect(states(await storedOps(db))).toEqual(["done", "todo"]);

    const first = calls[0];
    if (!first) throw new Error("no request");
    gate.resolve(answer("trip-1", first.body));
    await flushing;
    await outbox.idle();
    expect(calls.map((call) => states(call.body.ops as PendingOp[]))).toEqual([["done"], ["todo"]]);
    expect(outbox.pending()).toEqual([]);
    expect(await storedOps(db)).toEqual([]);
  });

  it("drops an op made pointless by a newer one once its send has failed", async () => {
    const gate = deferred<OpsOut>();
    const { outbox, calls } = setup((tripId, body, call) =>
      call === 1 ? gate.promise : Promise.resolve(answer(tripId, body)),
    );
    await outbox.setState("trip-1", "item-1", "done");
    const flushing = outbox.flush();
    await until(() => calls.length === 1);
    await outbox.setState("trip-1", "item-1", "missed");
    gate.reject(new ApiError(0, "offline", "Offline"));
    await flushing;
    expect(states(outbox.pending())).toEqual(["missed"]);
  });

  it("keeps state, note and status apart, and a note as the server will keep it", async () => {
    const { outbox } = setup();
    await outbox.setState("trip-1", "item-1", "missed");
    await outbox.setNote("trip-1", "item-1", "  Ask at the deli  ");
    await outbox.setNote("trip-1", "item-2", "x".repeat(250));
    await outbox.setNote("trip-1", "item-3", "   ");
    await outbox.finish("trip-1", 6400);
    await outbox.reopen("trip-1"); // replaces the finish: one status op at a time
    expect(outbox.pending().map((op) => op.kind)).toEqual([
      "item.set_state",
      "item.set_note",
      "item.set_note",
      "item.set_note",
      "trip.reopen",
    ]);
    const notes = outbox.pending().map((op) => (op.kind === "item.set_note" ? op.note : undefined));
    expect(notes[1]).toBe("Ask at the deli");
    expect(notes[2]).toHaveLength(200);
    expect(notes[3]).toBeNull();
    await expect(outbox.finish("trip-1", 12.5)).rejects.toThrow(RangeError);
  });

  it("gives every op a larger client_seq, even after a restart", async () => {
    const dbName = newDbName();
    const first = setup(undefined, { dbName });
    await first.outbox.setState("trip-1", "item-1", "done");
    await first.outbox.setState("trip-1", "item-2", "done");
    await first.outbox.setState("trip-1", "item-1", "todo"); // replaces the first op
    const before = first.outbox.pending().map((op) => op.client_seq);
    expect(before).toEqual([2, 3]);

    const restarted = setup(undefined, { dbName });
    await restarted.outbox.setState("trip-1", "item-3", "done");
    expect(restarted.outbox.pending().map((op) => op.client_seq)).toEqual([2, 3, 4]);
    const stamps = restarted.outbox.pending().map((op) => op.client_ts);
    expect(new Set(stamps).size).toBe(stamps.length);
  });

  it("waits 300 ms after the last tap before flushing", async () => {
    const { outbox, calls, manual } = setup();
    await outbox.setState("trip-1", "item-1", "done");
    await outbox.setState("trip-1", "item-2", "done");
    expect(manual.delays()).toEqual([FLUSH_DEBOUNCE_MS]); // one timer, restarted by each tap
    manual.fire(FLUSH_DEBOUNCE_MS);
    await outbox.idle();
    expect(calls).toHaveLength(1);
    expect(calls[0]?.body.ops).toHaveLength(2);
  });
});

describe("outbox: batches", () => {
  it("sends one trip at a time, oldest first, at most 100 ops a batch", async () => {
    const { outbox, calls } = setup();
    await outbox.setState("trip-1", "item-a", "done");
    await outbox.setState("trip-2", "item-b", "done");
    for (let n = 0; n < 150; n += 1) await outbox.setState("trip-1", `item-${String(n)}`, "done");
    await outbox.flush();
    // After the first batch, trip-2's op is the oldest still waiting, so it goes next.
    expect(calls.map((call) => [call.tripId, call.body.ops.length])).toEqual([
      ["trip-1", MAX_OPS_PER_BATCH],
      ["trip-2", 1],
      ["trip-1", 51],
    ]);
    for (const call of calls) {
      const seqs = call.body.ops.map((op) => op.client_seq);
      expect(seqs).toEqual([...seqs].sort((a, b) => a - b));
    }
    expect(new Set(calls.flatMap((call) => call.body.ops.map((op) => op.op_id))).size).toBe(152);
  });

  it("keeps each batch under about 60 KB", async () => {
    const { outbox, calls } = setup();
    for (let n = 0; n < 100; n += 1) {
      await outbox.setNote("trip-1", `item-${String(n)}`, "🥛".repeat(200));
    }
    await outbox.flush();
    expect(calls.length).toBeGreaterThan(1);
    for (const call of calls) {
      expect(new TextEncoder().encode(JSON.stringify(call.body)).length).toBeLessThanOrEqual(
        MAX_BATCH_BYTES,
      );
    }
    expect(calls.reduce((sum, call) => sum + call.body.ops.length, 0)).toBe(100);
  });

  it("splits a batch in half when the server says it's too large (413)", async () => {
    const { outbox, calls } = setup((tripId, body) =>
      body.ops.length > 25
        ? Promise.reject(new ApiError(413, "too_many_changes", "Too many changes at once."))
        : Promise.resolve(answer(tripId, body)),
    );
    for (let n = 0; n < 100; n += 1) await outbox.setState("trip-1", `item-${String(n)}`, "done");
    await outbox.flush();
    expect(calls.map((call) => call.body.ops.length)).toEqual([100, 50, 25, 25, 50, 25, 25]);
    expect(outbox.pending()).toEqual([]);
  });
});

describe("outbox: replies", () => {
  it("removes every op the server answered for: applied, superseded, duplicate, rejected", async () => {
    const statuses = ["applied", "superseded", "duplicate", "rejected"] as const;
    const { outbox } = setup((tripId, body) => {
      const reply = answer(tripId, body);
      reply.results = body.ops.map((op, n) => ({
        op_id: op.op_id,
        status: statuses[n] ?? "applied",
        ...(statuses[n] === "rejected" ? { reason: "trip_closed" } : {}),
      }));
      return Promise.resolve(reply);
    });
    for (let n = 0; n < 4; n += 1) await outbox.setState("trip-1", `item-${String(n)}`, "done");
    await outbox.flush();
    expect(outbox.pending()).toEqual([]);
  });

  it("merges the reply into the trip, asking from where this phone's copy is complete", async () => {
    const { outbox, trips, calls } = setup((tripId, body) =>
      Promise.resolve({
        ...answer(tripId, body),
        items: [item("item-1", { version: 11, state: "done", state_by: "member-1" })],
        trip: header({ version: 11, done_count: 1 }),
      }),
    );
    await trips.merge("trip-1", { header: header(), items: [item("item-1")], complete: true });
    await outbox.setState("trip-1", "item-1", "done");
    await outbox.flush();
    expect(calls[0]?.body.known_version).toBe(10);
    expect(calls[0]?.body.client_id).toBe("client-1");
    const trip = trips.store.get("trip-1");
    expect(trip?.items["item-1"]?.state).toBe("done");
    expect(trip?.syncedVersion).toBe(11);
  });

  it("keeps the ops on 401 and sends nothing more until resume()", async () => {
    let signedIn = false;
    const { outbox, calls } = setup((tripId, body) =>
      signedIn
        ? Promise.resolve(answer(tripId, body))
        : Promise.reject(new ApiError(401, "signed_out", "Sign in again.")),
    );
    await outbox.setState("trip-1", "item-1", "done");
    await outbox.flush();
    expect(outbox.status.get()).toMatchObject({ signedOut: true, pending: 1, sending: false });
    await outbox.flush();
    expect(calls).toHaveLength(1);

    signedIn = true;
    await outbox.resume();
    expect(calls).toHaveLength(2);
    expect(outbox.status.get()).toMatchObject({ signedOut: false, pending: 0 });
  });

  it("drops the trip and its ops when the server no longer has the trip (404)", async () => {
    const { outbox, trips, calls, db } = setup((tripId, body) =>
      tripId === "trip-1"
        ? Promise.reject(new ApiError(404, "trip_not_found", "That saved list couldn't be found."))
        : Promise.resolve(answer(tripId, body)),
    );
    await trips.merge("trip-1", { header: header(), items: [item("item-1")], complete: true });
    await outbox.setState("trip-1", "item-1", "done");
    await outbox.setNote("trip-1", "item-1", "Gone soon");
    await outbox.setState("trip-2", "item-9", "done");
    await outbox.flush();
    await outbox.idle();
    expect(calls.map((call) => call.tripId)).toEqual(["trip-1", "trip-2"]);
    expect(trips.store.get("trip-1")).toBeUndefined();
    expect(outbox.pending()).toEqual([]);
    expect(await storedOps(db)).toEqual([]);
  });

  it("moves a malformed batch (422) to the dead-letter store and carries on", async () => {
    const { outbox, calls } = setup((tripId, body) =>
      tripId === "trip-1"
        ? Promise.reject(new ApiError(422, "invalid", "Something went wrong. Try again."))
        : Promise.resolve(answer(tripId, body)),
    );
    await outbox.setState("trip-1", "item-1", "done");
    await outbox.setState("trip-2", "item-9", "done");
    await outbox.flush();
    expect(calls.map((call) => call.tripId)).toEqual(["trip-1", "trip-2"]);
    expect(outbox.pending()).toEqual([]);
    const dead = await outbox.deadLetters();
    expect(dead).toMatchObject([
      { trip_id: "trip-1", item_id: "item-1", reason: "malformed", dead_at: 5_000 },
    ]);
  });

  it("keeps the ops through network and server errors, backing off 1, 2, 5, 10, then 30 s", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
    let failure: ApiError | null = new ApiError(0, "offline", "You're offline.");
    const { outbox, calls } = setup(
      (tripId, body) => (failure ? Promise.reject(failure) : Promise.resolve(answer(tripId, body))),
      { browserTimers: true },
    );
    await outbox.setState("trip-1", "item-1", "done");
    await vi.advanceTimersByTimeAsync(FLUSH_DEBOUNCE_MS);
    await outbox.idle();
    expect(calls).toHaveLength(1);

    // Full jitter: with random() at 0.5, each wait is half the step.
    const steps = [...BACKOFF_MS, 30_000];
    for (const [n, step] of steps.entries()) {
      if (n === 2) failure = new ApiError(503, "error", "Something went wrong. Try again.");
      await vi.advanceTimersByTimeAsync(step / 2 - 1);
      await outbox.idle();
      expect(calls).toHaveLength(n + 1);
      await vi.advanceTimersByTimeAsync(1);
      await outbox.idle();
      expect(calls).toHaveLength(n + 2);
      expect(outbox.pending()).toHaveLength(1);
    }

    failure = null;
    await vi.advanceTimersByTimeAsync(15_000);
    await outbox.idle();
    expect(outbox.pending()).toEqual([]);

    // A success starts the schedule again from 1 s.
    failure = new ApiError(0, "offline", "You're offline.");
    const sent = calls.length;
    await outbox.setState("trip-1", "item-2", "done");
    await vi.advanceTimersByTimeAsync(FLUSH_DEBOUNCE_MS);
    await outbox.idle();
    await vi.advanceTimersByTimeAsync(BACKOFF_MS[0] / 2);
    await outbox.idle();
    expect(calls.length).toBe(sent + 2);
  });

  it("loses nothing if the app dies mid-send: the next start sends the ops again", async () => {
    const dbName = newDbName();
    const first = setup(() => new Promise<OpsOut>(() => undefined), { dbName });
    await first.outbox.setState("trip-1", "item-1", "done");
    void first.outbox.flush();
    await until(() => first.calls.length === 1);

    const restarted = setup((tripId, body) => Promise.resolve(answer(tripId, body, "duplicate")), {
      dbName,
    });
    await restarted.outbox.flush();
    expect(restarted.calls[0]?.body.ops.map((op) => op.op_id)).toEqual(
      first.calls[0]?.body.ops.map((op) => op.op_id),
    );
    expect(restarted.outbox.pending()).toEqual([]);
  });
});

describe("outbox: when it flushes", () => {
  it("flushes at start, back online, back visible, on pageshow, and every 15 s with ops waiting", async () => {
    const dbName = newDbName();
    const earlier = setup(undefined, { dbName });
    await earlier.outbox.setState("trip-1", "item-1", "done");

    const { outbox, calls, manual, page, win } = setup(undefined, { dbName });
    const stop = outbox.start();
    await until(() => calls.length === 1); // app start
    await outbox.idle();

    const sendsAfter = async (trigger: () => void, n: number) => {
      await outbox.setState("trip-1", `item-${String(n)}`, "done");
      trigger();
      await until(() => calls.length === n);
      await outbox.idle();
    };
    await sendsAfter(() => {
      win.fire("online");
    }, 2);
    await sendsAfter(() => {
      page.fire("visibilitychange");
    }, 3);
    await sendsAfter(() => {
      win.fire("pageshow");
    }, 4);
    await sendsAfter(() => {
      manual.fire(FLUSH_EVERY_MS);
    }, 5);

    // With nothing waiting, the 15-second tick sends nothing.
    manual.fire(FLUSH_EVERY_MS);
    await outbox.idle();
    expect(calls).toHaveLength(5);

    stop();
    await outbox.setState("trip-1", "item-6", "done");
    win.fire("online");
    await outbox.idle();
    expect(calls).toHaveLength(5);
  });

  it("sends a keepalive copy when the page is hidden or closing", async () => {
    let online = false;
    const { outbox, calls, page, win } = setup((tripId, body) =>
      online
        ? Promise.resolve(answer(tripId, body))
        : Promise.reject(new ApiError(0, "offline", "You're offline.")),
    );
    await outbox.setState("trip-1", "item-1", "done");
    outbox.start();
    await until(() => calls.length === 1);
    await outbox.idle();
    expect(outbox.pending()).toHaveLength(1);

    online = true;
    page.visibilityState = "hidden";
    page.fire("visibilitychange");
    win.fire("pagehide"); // iOS fires both; one copy is enough
    await until(() => outbox.pending().length === 0);
    expect(calls.slice(1).map((call) => call.keepalive)).toEqual([true]);
  });
});
