/**
 * The outbox (docs/PLAN.md §9.2 and §9.4, docs/adr/0015): shopping actions wait here, on the
 * phone, until the server has them, so a check-off in an aisle with no signal is never lost.
 *
 * * Ops carry absolute values (never toggles), a unique op_id, a corrected, always-increasing
 *   client_ts and a per-device client_seq, so resending or reordering them is harmless.
 * * Adding an op replaces any unsent op for the same thing (an Undo before sending leaves only
 *   the final intent), but never one that's on its way to the server.
 * * Flushing sends one trip at a time, oldest first, at most 100 ops and about 60 KB a batch.
 *   Every op the server answers for leaves the outbox, whatever the answer was.
 * * No signal or a server error keeps the ops and backs off 1, 2, 5, 10, then 30 s, with full
 *   jitter. A 401 keeps them until sign-in. A malformed batch (422) goes to the dead-letter
 *   store, so one bad op can't block everything behind it.
 * * Screens show server state with these ops laid on top (tripView.ts). When an op leaves the
 *   outbox its overlay goes with it, so rollback needs no code.
 *
 * Memory holds the working copy, so a tap shows at once; IndexedDB mirrors it, one write at a
 * time, so the ops survive the app being closed. Which ops are being sent is tracked in memory
 * only: after a crash they're sent again, and the server answers "duplicate".
 */
import { useSyncExternalStore } from "react";

import { api, ApiError, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { nextTimestamp } from "./clock";
import { localDb, type LocalDatabase, type LocalDb } from "./db";
import { createStore, useStore, type Store } from "./store";
import {
  isTripGone,
  syncRequest,
  trips as defaultTrips,
  type ItemState,
  type Trips,
} from "./trips";

export type OpIn = components["schemas"]["OpIn"];
export type OpsIn = components["schemas"]["OpsIn"];
export type OpsOut = components["schemas"]["OpsOut"];

export const OP_VERSION = 1;
export const MAX_OPS_PER_BATCH = 100;
/** The server takes 64 KB; staying under 60 KB leaves room for a keepalive request too. */
export const MAX_BATCH_BYTES = 60_000;
export const NOTE_MAX = 200;
export const MAX_TOTAL_CENTS = 10_000_000;
export const FLUSH_DEBOUNCE_MS = 300;
export const FLUSH_EVERY_MS = 15_000;
export const BACKOFF_MS = [1_000, 2_000, 5_000, 10_000, 30_000] as const;
const SEQ_KEY = "client_seq";
const ENVELOPE_BYTES = 200; // client_id, known_version and the brackets around the ops

interface OpBase {
  op_id: string;
  trip_id: string;
  v: number;
  client_ts: number;
  client_seq: number;
}

export type PendingOp =
  | (OpBase & { kind: "item.set_state"; item_id: string; state: ItemState })
  | (OpBase & { kind: "item.set_note"; item_id: string; note: string | null })
  | (OpBase & { kind: "trip.finish"; actual_total_cents: number | null })
  | (OpBase & { kind: "trip.reopen" });

export type OpKind = PendingOp["kind"];

/** An op the server refused as malformed: kept for diagnosis, never sent again. */
export type DeadOp = PendingOp & { dead_at: number; reason: string };

type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;
type Draft = DistributiveOmit<PendingOp, "op_id" | "v" | "client_ts" | "client_seq">;

export interface OutboxStatus {
  /** Ops waiting on this phone. */
  pending: number;
  /** A batch is on its way. */
  sending: boolean;
  /** The server said 401: ops wait until resume() after signing in again. */
  signedOut: boolean;
}

export interface OpsTransport {
  /** POST a batch. Throws ApiError: status 0 for no reply (or one we can't read). */
  postOps: (tripId: string, body: OpsIn, options: { keepalive: boolean }) => Promise<OpsOut>;
}

export interface Timers {
  setTimeout: (callback: () => void, ms: number) => ReturnType<typeof setTimeout>;
  clearTimeout: (handle: ReturnType<typeof setTimeout> | undefined) => void;
  setInterval: (callback: () => void, ms: number) => ReturnType<typeof setInterval>;
  clearInterval: (handle: ReturnType<typeof setInterval> | undefined) => void;
}

export interface PageEvents {
  addEventListener: (type: string, listener: () => void) => void;
  removeEventListener: (type: string, listener: () => void) => void;
}

export interface VisiblePage extends PageEvents {
  readonly visibilityState: DocumentVisibilityState;
}

export interface OutboxDeps {
  db?: LocalDb;
  trips?: Pick<Trips, "store" | "merge" | "drop" | "onDropped" | "keepWhile">;
  transport?: OpsTransport;
  timers?: Timers;
  /** For the backoff's jitter. */
  random?: () => number;
  /** Plain time in ms, for dead-letter records. */
  now?: () => number;
  /** Corrected, always-increasing time for client_ts. */
  timestamp?: () => number;
  randomId?: () => string;
  document?: VisiblePage;
  window?: PageEvents;
}

export interface Outbox {
  setState: (tripId: string, itemId: string, state: ItemState) => Promise<void>;
  setNote: (tripId: string, itemId: string, note: string | null) => Promise<void>;
  finish: (tripId: string, actualTotalCents?: number | null) => Promise<void>;
  reopen: (tripId: string) => Promise<void>;
  /** Unsent ops, oldest first: all of them, or one trip's. The same array until they change. */
  pending: (tripId?: string) => readonly PendingOp[];
  subscribe: (listener: () => void) => () => void;
  status: Store<OutboxStatus>;
  /** Send what's waiting now. Resolves when there's nothing more to send, or no way to. */
  flush: () => Promise<void>;
  /** After signing in again: send what waited. */
  resume: () => Promise<void>;
  /** Install the flush triggers (app start). Returns a function that removes them. */
  start: () => () => void;
  deadLetters: () => Promise<DeadOp[]>;
  /** Resolves once nothing is being sent or saved (before an app update; tests). */
  idle: () => Promise<void>;
}

export const apiOpsTransport: OpsTransport = {
  postOps: (tripId, body, { keepalive }) =>
    syncRequest(async (signal) => {
      const reply = unwrap(
        await api.POST("/api/trips/{trip_id}/ops", {
          params: { path: { trip_id: tripId } },
          body,
          keepalive,
          signal,
        }),
      );
      if (!isOpsReply(reply)) throw new TypeError("The server's reply wasn't a batch result.");
      return reply;
    }),
};

function isOpsReply(value: unknown): value is OpsOut {
  if (typeof value !== "object" || value === null) return false;
  const reply = value as Partial<Record<keyof OpsOut, unknown>>;
  return (
    Array.isArray(reply.results) &&
    Array.isArray(reply.items) &&
    typeof reply.trip === "object" &&
    reply.trip !== null
  );
}

const browserTimers: Timers = {
  setTimeout: (callback, ms) => setTimeout(callback, ms),
  clearTimeout: (handle) => {
    clearTimeout(handle);
  },
  setInterval: (callback, ms) => setInterval(callback, ms),
  clearInterval: (handle) => {
    clearInterval(handle);
  },
};

/** Ops for the same thing replace each other: an item's state, an item's note, a trip's status. */
export function compactionKey(op: PendingOp): string {
  switch (op.kind) {
    case "item.set_state":
    case "item.set_note":
      return `${op.trip_id}|${op.item_id}|${op.kind}`;
    case "trip.finish":
    case "trip.reopen":
      return `${op.trip_id}|status`;
  }
}

/** The op as the API takes it. */
export function toOpIn(op: PendingOp): OpIn {
  const base = {
    op_id: op.op_id,
    v: op.v,
    kind: op.kind,
    client_ts: op.client_ts,
    client_seq: op.client_seq,
  };
  switch (op.kind) {
    case "item.set_state":
      return { ...base, item_id: op.item_id, state: op.state };
    case "item.set_note":
      return { ...base, item_id: op.item_id, note: op.note };
    case "trip.finish":
      return op.actual_total_cents === null
        ? base
        : { ...base, actual_total_cents: op.actual_total_cents };
    case "trip.reopen":
      return base;
  }
}

/** A note as the server will keep it: trimmed, at most 200 characters, empty means none. */
export function cleanNote(note: string | null): string | null {
  const trimmed = (note ?? "").trim();
  if (trimmed === "") return null;
  return Array.from(trimmed).slice(0, NOTE_MAX).join("").trim();
}

const encoder = new TextEncoder();

/** The next batch: the oldest op not being sent, and its trip's other ops, within the limits. */
export function nextBatch(
  ops: readonly PendingOp[],
  busy: ReadonlySet<string>,
): { tripId: string; ops: PendingOp[] } | undefined {
  const first = ops.find((op) => !busy.has(op.op_id));
  if (!first) return undefined;
  const batch: PendingOp[] = [];
  let bytes = ENVELOPE_BYTES;
  for (const op of ops) {
    if (op.trip_id !== first.trip_id || busy.has(op.op_id)) continue;
    const size = encoder.encode(JSON.stringify(toOpIn(op))).length + 1;
    if (batch.length === MAX_OPS_PER_BATCH) break;
    if (batch.length > 0 && bytes + size > MAX_BATCH_BYTES) break;
    batch.push(op);
    bytes += size;
  }
  return { tripId: first.trip_id, ops: batch };
}

const EMPTY: readonly PendingOp[] = Object.freeze([]);

export function createOutbox(deps: OutboxDeps = {}): Outbox {
  const db = deps.db ?? localDb;
  const trips = deps.trips ?? defaultTrips;
  const transport = deps.transport ?? apiOpsTransport;
  const timers = deps.timers ?? browserTimers;
  const random = deps.random ?? Math.random;
  const now = deps.now ?? Date.now;
  const stamp = deps.timestamp ?? (() => nextTimestamp());
  const randomId = deps.randomId ?? (() => crypto.randomUUID());
  const page: VisiblePage = deps.document ?? document;
  const win: PageEvents = deps.window ?? window;

  const status = createStore<OutboxStatus>({ pending: 0, sending: false, signedOut: false });
  const listeners = new Set<() => void>();
  const inFlight = new Set<string>();
  const byTrip = new Map<string, readonly PendingOp[]>();
  let ops: readonly PendingOp[] = EMPTY;
  let lastSeq = 0;
  let clientId: string | undefined;
  let loading: Promise<void> | undefined;
  let saving: Promise<void> = Promise.resolve();
  let flushing: Promise<void> | undefined;
  let flushRequests = 0; // flush() calls that arrived while a flush was running
  let attempt = 0;
  let debounceTimer: ReturnType<typeof setTimeout> | undefined;
  let backoffTimer: ReturnType<typeof setTimeout> | undefined;
  let keepaliveOut = false;
  let stop: (() => void) | undefined;

  const setOps = (next: readonly PendingOp[]): void => {
    ops = next.length === 0 ? EMPTY : next;
    byTrip.clear();
    status.set((s) => (s.pending === ops.length ? s : { ...s, pending: ops.length }));
    for (const listener of listeners) listener();
  };

  /** IndexedDB writes go one at a time, in order. Memory is updated first, so taps show at once. */
  const save = (work: (conn: LocalDatabase) => Promise<unknown>): Promise<void> => {
    const run = async (): Promise<void> => {
      try {
        await db.withDb(work);
      } catch {
        // No storage: the ops still live in memory and are still sent this session.
      }
    };
    saving = saving.then(run);
    return saving;
  };

  const load = (): Promise<void> => {
    loading ??= (async () => {
      try {
        const [stored, seq] = await db.withDb(async (conn) => {
          const tx = conn.transaction(["outbox", "meta"]);
          const [all, last] = await Promise.all([
            tx.objectStore("outbox").getAll(),
            tx.objectStore("meta").get(SEQ_KEY),
            tx.done,
          ]);
          return [all, last] as const;
        });
        for (const op of stored) lastSeq = Math.max(lastSeq, op.client_seq);
        if (typeof seq === "number") lastSeq = Math.max(lastSeq, seq);
        setOps([...stored].sort((a, b) => a.client_seq - b.client_seq));
      } catch {
        // No storage: start empty and keep ops in memory only.
      }
      clientId = await db.clientId();
    })();
    return loading;
  };

  const remove = (opIds: readonly string[]): void => {
    if (opIds.length === 0) return;
    const gone = new Set(opIds);
    setOps(ops.filter((op) => !gone.has(op.op_id)));
    void save(async (conn) => {
      const tx = conn.transaction("outbox", "readwrite");
      await Promise.all([...opIds.map((id) => tx.store.delete(id)), tx.done]);
    });
  };

  /** Once an op is no longer being sent, a newer one for the same thing makes it pointless. */
  const settleCompaction = (): void => {
    const latest = new Map<string, PendingOp>();
    for (const op of ops) latest.set(compactionKey(op), op);
    const stale = ops.filter(
      (op) => latest.get(compactionKey(op)) !== op && !inFlight.has(op.op_id),
    );
    remove(stale.map((op) => op.op_id));
  };

  const scheduleFlush = (): void => {
    timers.clearTimeout(debounceTimer);
    debounceTimer = timers.setTimeout(() => {
      debounceTimer = undefined;
      void flush();
    }, FLUSH_DEBOUNCE_MS);
  };

  const enqueue = async (draft: Draft): Promise<void> => {
    const clientTs = stamp(); // the moment of the tap, before any waiting
    const opId = randomId();
    await load();
    lastSeq += 1;
    const op: PendingOp = {
      ...draft,
      op_id: opId,
      v: OP_VERSION,
      client_ts: clientTs,
      client_seq: lastSeq,
    };
    const key = compactionKey(op);
    const replaced = ops.filter((old) => compactionKey(old) === key && !inFlight.has(old.op_id));
    const gone = new Set(replaced.map((old) => old.op_id));
    setOps([...ops.filter((old) => !gone.has(old.op_id)), op]);
    scheduleFlush();
    await save(async (conn) => {
      const tx = conn.transaction(["outbox", "meta"], "readwrite");
      const outbox = tx.objectStore("outbox");
      await Promise.all([
        ...replaced.map((old) => outbox.delete(old.op_id)),
        outbox.put(op),
        tx.objectStore("meta").put(op.client_seq, SEQ_KEY),
        tx.done,
      ]);
    });
  };

  const deadLetter = async (batch: readonly PendingOp[], reason: string): Promise<void> => {
    const gone = new Set(batch.map((op) => op.op_id));
    setOps(ops.filter((op) => !gone.has(op.op_id)));
    const deadAt = now();
    await save(async (conn) => {
      const tx = conn.transaction(["outbox", "deadletter"], "readwrite");
      await Promise.all([
        ...batch.map((op) => tx.objectStore("outbox").delete(op.op_id)),
        ...batch.map((op) => tx.objectStore("deadletter").put({ ...op, dead_at: deadAt, reason })),
        tx.done,
      ]);
    });
  };

  const backOff = (): void => {
    const base = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)] ?? 30_000;
    attempt += 1;
    timers.clearTimeout(backoffTimer);
    backoffTimer = timers.setTimeout(
      () => {
        backoffTimer = undefined;
        void flush();
      },
      Math.round(random() * base),
    );
  };

  /** The reply's news goes into the trip first, then the answered ops leave: no flicker. */
  const accept = async (tripId: string, knownVersion: number, reply: OpsOut): Promise<void> => {
    await trips.merge(tripId, { header: reply.trip, items: reply.items, since: knownVersion });
    const answered = new Set(reply.results.map((result) => result.op_id));
    remove(ops.filter((op) => answered.has(op.op_id)).map((op) => op.op_id));
  };

  const body = (tripId: string, batch: readonly PendingOp[], id: string) => {
    const knownVersion = trips.store.get(tripId)?.syncedVersion ?? 0;
    const payload: OpsIn = { client_id: id, known_version: knownVersion, ops: batch.map(toOpIn) };
    return { knownVersion, payload };
  };

  const send = async (tripId: string, batch: readonly PendingOp[]): Promise<"go" | "stop"> => {
    const { knownVersion, payload } = body(tripId, batch, clientId ?? (await db.clientId()));
    for (const op of batch) inFlight.add(op.op_id);
    status.set((s) => (s.sending ? s : { ...s, sending: true }));
    const release = (): void => {
      for (const op of batch) inFlight.delete(op.op_id);
      status.set((s) => (s.sending ? { ...s, sending: false } : s));
    };
    let reply: OpsOut;
    try {
      reply = await transport.postOps(tripId, payload, { keepalive: false });
    } catch (error) {
      release();
      settleCompaction();
      return await failed(tripId, batch, error);
    }
    release();
    attempt = 0;
    await accept(tripId, knownVersion, reply);
    return "go";
  };

  const failed = async (
    tripId: string,
    batch: readonly PendingOp[],
    error: unknown,
  ): Promise<"go" | "stop"> => {
    const code = error instanceof ApiError ? error.status : 0;
    if (code === 401) {
      status.set((s) => ({ ...s, signedOut: true }));
      timers.clearTimeout(backoffTimer);
      backoffTimer = undefined;
      return "stop";
    }
    if (isTripGone(error)) {
      // The trip and its ops go: there's nothing left to send them to.
      await trips.drop(tripId);
      remove(ops.filter((op) => op.trip_id === tripId).map((op) => op.op_id));
      return "go";
    }
    // Only ops still waiting: an Undo may have replaced some while they were out.
    const waiting = batch.filter((op) => ops.includes(op));
    if (code === 413 && waiting.length > 1) {
      const half = Math.ceil(waiting.length / 2);
      if ((await send(tripId, waiting.slice(0, half))) === "stop") return "stop";
      const rest = waiting.slice(half).filter((op) => ops.includes(op));
      return rest.length > 0 ? send(tripId, rest) : "go";
    }
    if (code === 413 || code === 422) {
      await deadLetter(waiting, code === 413 ? "too_large" : "malformed");
      return "go";
    }
    // No signal, a timeout, a server error, or anything unexpected: keep the ops, try later.
    backOff();
    return "stop";
  };

  const drain = async (): Promise<"idle" | "stopped"> => {
    for (;;) {
      if (status.get().signedOut) return "stopped";
      const batch = nextBatch(ops, inFlight);
      if (!batch) return "idle";
      timers.clearTimeout(backoffTimer);
      backoffTimer = undefined;
      if ((await send(batch.tripId, batch.ops)) === "stop") return "stopped";
    }
  };

  const flush = (): Promise<void> => {
    if (flushing) {
      flushRequests += 1;
      return flushing;
    }
    flushing = (async () => {
      try {
        await load();
        for (;;) {
          const asked = flushRequests;
          if ((await drain()) === "stopped") break;
          if (flushRequests === asked) break; // nothing new was asked for meanwhile
        }
      } finally {
        flushing = undefined;
      }
    })();
    return flushing;
  };

  /** Hidden or leaving: one best-effort copy of the next batch that outlives the page. */
  const sendKeepalive = (): void => {
    if (keepaliveOut || status.get().signedOut || clientId === undefined) return;
    const batch = nextBatch(ops, new Set());
    if (!batch) return;
    keepaliveOut = true;
    const { knownVersion, payload } = body(batch.tripId, batch.ops, clientId);
    void transport
      .postOps(batch.tripId, payload, { keepalive: true })
      .then(
        (reply) => accept(batch.tripId, knownVersion, reply),
        () => undefined, // the next flush sends them again; the server answers "duplicate"
      )
      .finally(() => {
        keepaliveOut = false;
      });
  };

  const start = (): (() => void) => {
    if (stop) return stop;
    const onOnline = (): void => {
      attempt = 0;
      void flush();
    };
    const onVisibility = (): void => {
      if (page.visibilityState === "hidden") sendKeepalive();
      else void flush();
    };
    const onPageShow = (): void => {
      void flush();
    };
    const onPageHide = (): void => {
      sendKeepalive();
    };
    win.addEventListener("online", onOnline);
    win.addEventListener("pageshow", onPageShow);
    win.addEventListener("pagehide", onPageHide);
    page.addEventListener("visibilitychange", onVisibility);
    const ticker = timers.setInterval(() => {
      if (page.visibilityState !== "hidden" && ops.length > 0 && !flushing) void flush();
    }, FLUSH_EVERY_MS);
    void flush();
    const remove = (): void => {
      win.removeEventListener("online", onOnline);
      win.removeEventListener("pageshow", onPageShow);
      win.removeEventListener("pagehide", onPageHide);
      page.removeEventListener("visibilitychange", onVisibility);
      timers.clearInterval(ticker);
      timers.clearTimeout(debounceTimer);
      timers.clearTimeout(backoffTimer);
      debounceTimer = undefined;
      backoffTimer = undefined;
      stop = undefined;
    };
    stop = remove;
    return remove;
  };

  // A trip that leaves this phone takes its ops with it (the trip store deletes the stored ones;
  // this catches any still being written).
  trips.onDropped((tripId) => {
    if (!ops.some((op) => op.trip_id === tripId)) return;
    setOps(ops.filter((op) => op.trip_id !== tripId));
    void save(async (conn) => {
      const tx = conn.transaction("outbox", "readwrite");
      const opIds = await tx.store.index("by-trip").getAllKeys(tripId);
      await Promise.all([...opIds.map((id) => tx.store.delete(id)), tx.done]);
    });
  });
  trips.keepWhile((tripId) => ops.some((op) => op.trip_id === tripId));

  return {
    setState: (tripId, itemId, state) =>
      enqueue({ kind: "item.set_state", trip_id: tripId, item_id: itemId, state }),
    setNote: (tripId, itemId, note) =>
      enqueue({ kind: "item.set_note", trip_id: tripId, item_id: itemId, note: cleanNote(note) }),
    finish: (tripId, actualTotalCents = null) => {
      if (
        actualTotalCents !== null &&
        !(
          Number.isInteger(actualTotalCents) &&
          actualTotalCents >= 0 &&
          actualTotalCents <= MAX_TOTAL_CENTS
        )
      ) {
        return Promise.reject(new RangeError("What you paid must be whole cents, up to $100,000."));
      }
      return enqueue({
        kind: "trip.finish",
        trip_id: tripId,
        actual_total_cents: actualTotalCents,
      });
    },
    reopen: (tripId) => enqueue({ kind: "trip.reopen", trip_id: tripId }),
    pending: (tripId) => {
      if (tripId === undefined) return ops;
      let list = byTrip.get(tripId);
      if (!list) {
        const mine = ops.filter((op) => op.trip_id === tripId);
        list = mine.length === 0 ? EMPTY : mine;
        byTrip.set(tripId, list);
      }
      return list;
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    status,
    flush,
    resume: () => {
      status.set((s) => (s.signedOut ? { ...s, signedOut: false } : s));
      attempt = 0;
      return flush();
    },
    start,
    deadLetters: async () => {
      try {
        return await db.withDb((conn) => conn.getAll("deadletter"));
      } catch {
        return [];
      }
    },
    idle: async () => {
      for (;;) {
        const busy = flushing;
        const writes = saving;
        await (busy ?? Promise.resolve());
        await writes;
        if (busy === flushing && writes === saving) return;
      }
    },
  };
}

export const outbox = createOutbox();

/** One trip's unsent ops (or all of them), for a screen. */
export function usePendingOps(tripId?: string): readonly PendingOp[] {
  return useSyncExternalStore(
    outbox.subscribe,
    () => outbox.pending(tripId),
    () => outbox.pending(tripId),
  );
}

/** For the sync pill: "Syncing 3…", "Sign in to sync". */
export function useOutboxStatus(): OutboxStatus {
  return useStore(outbox.status);
}
