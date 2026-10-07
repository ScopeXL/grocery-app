/**
 * Trips kept on this phone (docs/PLAN.md §9.1, §9.4): every active trip, plus trips finished in
 * the last 24 h, so shopping mode works with no signal. The server is the source of truth; this
 * is its copy, merged by version so replies and live events can arrive in any order.
 *
 * * A trip's header is replaced only by one at least as new; an item only by a newer version.
 * * Items taken off the list stay, marked removed, so every view simply skips them.
 * * `syncedVersion` says how far the copy is known to be complete. Deltas and the outbox ask
 *   for everything after it, so a missed live event can never leave a hole in the list.
 *
 * An in-memory mirror (tripStore) gives screens a synchronous read; IndexedDB keeps the copy
 * across restarts, including iOS killing the app mid-trip. Trips stay out of the TanStack Query
 * cache on purpose (PLAN §9.4).
 */
import { useSyncExternalStore } from "react";

import { api, ApiError, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { clockOffset } from "./clock";
import { markUnreachable } from "./connection";
import { localDb, type LocalDatabase, type LocalDb } from "./db";
import type { ServerEvent } from "./events";
import { releaseTripImages } from "./images";

export type TripHeader = components["schemas"]["TripHeader"];
export type TripItemOut = components["schemas"]["TripItemOut"];
export type TripOut = components["schemas"]["TripOut"];
export type TripsOut = components["schemas"]["TripsOut"];
export type MemberRef = components["schemas"]["MemberRef"];
export type ItemState = TripItemOut["state"];
export type TripStatus = TripHeader["status"];

export interface LocalTrip {
  header: TripHeader;
  members: MemberRef[];
  items: Record<string, TripItemOut>;
  /** Every change up to this trip version is in `items`; deltas and the outbox ask from here. */
  syncedVersion: number;
  /** When this copy last changed on this phone (ms). */
  savedAt: number;
}

/** News about a trip, from a download, an ops reply or a live event. */
export interface TripUpdate {
  header?: TripHeader | undefined;
  members?: readonly MemberRef[] | undefined;
  items?: readonly TripItemOut[] | undefined;
  /** The update holds every change after this trip version (a delta, an ops reply, an event). */
  since?: number | undefined;
  /** A full snapshot: items missing from it had been taken off the list. */
  complete?: boolean | undefined;
}

export interface TripStore {
  get: (id: string) => LocalTrip | undefined;
  /** Every trip on this phone; the same array until something changes. */
  list: () => readonly LocalTrip[];
  subscribe: (listener: () => void) => () => void;
}

export interface TripsTransport {
  listTrips: () => Promise<TripsOut>;
  /** The whole trip, or only what changed after `sinceVersion`. Throws ApiError. */
  getTrip: (id: string, sinceVersion?: number) => Promise<TripOut>;
}

export interface TripsDeps {
  db?: LocalDb;
  transport?: TripsTransport;
  /** Corrected time in ms, for the 24-hour rule. */
  now?: () => number;
  /** Lets go of photos no trip on this phone still needs (docs/adr/0016). */
  releasePhotos?: (urls: string[], keep: string[]) => void;
}

export interface Trips {
  store: TripStore;
  hydrate: () => Promise<void>;
  download: (id: string) => Promise<LocalTrip | undefined>;
  syncActive: () => Promise<boolean>;
  applyEvent: (event: ServerEvent) => Promise<void>;
  remember: (trip: TripOut) => Promise<void>;
  merge: (id: string, update: TripUpdate) => Promise<LocalTrip | undefined>;
  drop: (id: string) => Promise<void>;
  /** Called with a trip's id whenever it leaves this phone. */
  onDropped: (listener: (id: string) => void) => () => void;
  /** A trip is never tidied away while any of these says it still has work (unsent ops). */
  keepWhile: (busy: (id: string) => boolean) => () => void;
}

/** Finished trips stay this long: late check-offs still count on the server (PLAN §9.2). */
export const FINISHED_KEPT_MS = 24 * 60 * 60 * 1000;
const REQUEST_TIMEOUT_MS = 10_000;
const OFFLINE_MESSAGE = "You're offline. Try again when you have signal.";

/**
 * One sync request, with the 10 s timeout (PLAN §9.4). A reply we can't read (a store Wi-Fi
 * sign-in page answering 200, say) counts as no reply at all: ApiError status 0.
 */
export async function syncRequest<T>(call: (signal: AbortSignal) => Promise<T>): Promise<T> {
  try {
    return await call(AbortSignal.timeout(REQUEST_TIMEOUT_MS));
  } catch (error) {
    if (error instanceof ApiError) throw error;
    markUnreachable();
    throw new ApiError(0, "offline", OFFLINE_MESSAGE);
  }
}

/** The server says the trip doesn't exist. A 404 from anything else (a proxy) isn't proof. */
export function isTripGone(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404 && error.code === "trip_not_found";
}

export const apiTripsTransport: TripsTransport = {
  listTrips: () => syncRequest(async (signal) => unwrap(await api.GET("/api/trips", { signal }))),
  getTrip: (id, sinceVersion) =>
    syncRequest(async (signal) =>
      unwrap(
        await api.GET("/api/trips/{trip_id}", {
          params: {
            path: { trip_id: id },
            query: sinceVersion === undefined ? {} : { since_version: sinceVersion },
          },
          signal,
        }),
      ),
    ),
};

/** Just the header fields of a full trip (members and items are kept beside it). */
export function headerOf(trip: TripHeader): TripHeader {
  return {
    id: trip.id,
    status: trip.status,
    version: trip.version,
    plan_id: trip.plan_id,
    store_name: trip.store_name,
    created_at: trip.created_at,
    created_by: trip.created_by,
    estimate_cents: trip.estimate_cents,
    savings_cents: trip.savings_cents,
    not_priced: trip.not_priced,
    prices_as_of: trip.prices_as_of,
    actual_total_cents: trip.actual_total_cents,
    finished_at: trip.finished_at,
    status_by: trip.status_by,
    status_ts: trip.status_ts,
    item_count: trip.item_count,
    done_count: trip.done_count,
    missed_count: trip.missed_count,
  };
}

/** A downloaded trip as an update: a full one is complete; a delta holds what followed `since`. */
export function updateFrom(trip: TripOut, since?: number): TripUpdate {
  return {
    header: headerOf(trip),
    members: trip.members,
    items: trip.items,
    complete: trip.complete,
    since: trip.complete ? 0 : since,
  };
}

/**
 * A live event is one whole server write, so it holds every version that write took: it starts
 * just before its oldest item, or just before its header when it carries no items.
 */
export function eventSince(header: TripHeader, items: readonly TripItemOut[]): number {
  const oldest = items.reduce((low, item) => Math.min(low, item.version), header.version);
  return oldest - 1;
}

function sameFields<T extends object>(a: T, b: T): boolean {
  const keys = Object.keys(a) as (keyof T)[];
  return keys.length === Object.keys(b).length && keys.every((key) => Object.is(a[key], b[key]));
}

function sameMembers(a: readonly MemberRef[], b: readonly MemberRef[]): boolean {
  return (
    a.length === b.length &&
    a.every((member, index) => {
      const other = b[index];
      return other !== undefined && sameFields(member, other);
    })
  );
}

/**
 * Merge news into a trip. Pure: the result is `local` itself when nothing changed, and
 * undefined only when there's no trip yet and the update brings no header to start one.
 */
export function mergeTrip(
  local: LocalTrip | undefined,
  incoming: TripUpdate,
  now: number = Date.now(),
): LocalTrip | undefined {
  const fresh = incoming.header;
  const newer = fresh !== undefined && (!local || fresh.version >= local.header.version);
  const header = newer && !(local && sameFields(fresh, local.header)) ? fresh : local?.header;
  if (!header) return undefined;
  let changed = header !== local?.header;

  let members = local?.members ?? [];
  if (incoming.members && (newer || !local) && !sameMembers(members, incoming.members)) {
    members = [...incoming.members];
    changed = true;
  }

  let items = local?.items ?? {};
  let copied = false;
  const put = (item: TripItemOut): void => {
    if (!copied) {
      items = { ...items };
      copied = true;
    }
    items[item.id] = item;
    changed = true;
  };
  for (const item of incoming.items ?? []) {
    const current = items[item.id];
    if (!current || item.version > current.version) put(item);
  }
  if (incoming.complete && fresh) {
    // Anything this phone holds that the snapshot doesn't, and that hasn't changed since the
    // snapshot was taken, was taken off the list.
    const present = new Set((incoming.items ?? []).map((item) => item.id));
    for (const item of Object.values(items)) {
      if (!present.has(item.id) && !item.removed && item.version <= fresh.version) {
        put({ ...item, removed: true });
      }
    }
  }

  let syncedVersion = local?.syncedVersion ?? 0;
  const from = incoming.complete ? 0 : incoming.since;
  if (fresh && from !== undefined && from <= syncedVersion && fresh.version > syncedVersion) {
    syncedVersion = fresh.version;
    changed = true;
  }

  if (!changed && local) return local;
  return { header, members, items, syncedVersion, savedAt: now };
}

/** The photos a trip shows, once each, in list order. */
export function photoUrls(trip: LocalTrip): string[] {
  const items = Object.values(trip.items)
    .filter((item) => !item.removed)
    .sort((a, b) => a.position - b.position);
  const urls = new Set<string>();
  for (const item of items) if (item.image_url) urls.add(item.image_url);
  return [...urls];
}

function asHeader(value: unknown, id: string): TripHeader | undefined {
  if (typeof value !== "object" || value === null) return undefined;
  const header = value as Partial<TripHeader>;
  return header.id === id && typeof header.version === "number" ? (value as TripHeader) : undefined;
}

function asItems(value: unknown): TripItemOut[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item: unknown): item is TripItemOut =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as Partial<TripItemOut>).id === "string" &&
      typeof (item as Partial<TripItemOut>).version === "number",
  );
}

/** A stored trip as this build expects it, or undefined if it's unreadable. */
function readStored(value: unknown): LocalTrip | undefined {
  if (typeof value !== "object" || value === null) return undefined;
  const trip = value as Partial<LocalTrip>;
  if (typeof trip.header?.id !== "string" || typeof trip.items !== "object") return undefined;
  return {
    header: trip.header,
    members: Array.isArray(trip.members) ? trip.members : [],
    items: trip.items,
    syncedVersion: typeof trip.syncedVersion === "number" ? trip.syncedVersion : 0,
    savedAt: typeof trip.savedAt === "number" ? trip.savedAt : 0,
  };
}

export function createTrips(deps: TripsDeps = {}): Trips {
  const db = deps.db ?? localDb;
  const transport = deps.transport ?? apiTripsTransport;
  const now = deps.now ?? (() => Date.now() + clockOffset());
  const releasePhotos =
    deps.releasePhotos ??
    ((urls: string[], keep: string[]) => {
      void releaseTripImages(urls, keep);
    });

  const memory = new Map<string, LocalTrip>();
  let snapshot: readonly LocalTrip[] = [];
  const listeners = new Set<() => void>();
  const dropListeners = new Set<(id: string) => void>();
  const busyChecks = new Set<(id: string) => boolean>();
  let hydrating: Promise<void> | undefined;
  let writing: Promise<void> = Promise.resolve();

  const notify = (): void => {
    snapshot = [...memory.values()];
    for (const listener of listeners) listener();
  };

  const store: TripStore = {
    get: (id) => memory.get(id),
    list: () => snapshot,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };

  /** Writes go one at a time, in order, so an older copy never lands after a newer one. */
  const write = (work: (conn: LocalDatabase) => Promise<unknown>): Promise<void> => {
    const run = async (): Promise<void> => {
      try {
        await db.withDb(work);
      } catch {
        // No storage (a private window, or full): the copy in memory still works this session.
      }
    };
    writing = writing.then(run);
    return writing;
  };

  const hydrate = (): Promise<void> => {
    hydrating ??= (async () => {
      try {
        const stored = await db.withDb((conn) => conn.getAll("trips"));
        for (const value of stored) {
          const trip = readStored(value);
          if (trip) memory.set(trip.header.id, trip);
        }
      } catch {
        // No storage: start with nothing on this phone.
      }
      notify();
    })();
    return hydrating;
  };

  /** Photos of `trip` that no active trip on this phone shows can go (docs/adr/0016). */
  const releaseFor = (trip: LocalTrip): void => {
    const urls = photoUrls(trip);
    if (urls.length === 0) return;
    const keep = new Set<string>();
    for (const other of memory.values()) {
      if (other.header.id === trip.header.id || other.header.status !== "active") continue;
      for (const url of photoUrls(other)) keep.add(url);
    }
    releasePhotos(urls, [...keep]);
  };

  const merge = async (id: string, update: TripUpdate): Promise<LocalTrip | undefined> => {
    await hydrate();
    const before = memory.get(id);
    if (update.header && update.header.id !== id) return before;
    const after = mergeTrip(before, update, now());
    if (!after || after === before) return before;
    memory.set(id, after);
    notify();
    if (before?.header.status === "active" && after.header.status === "finished") {
      releaseFor(after);
    }
    await write((conn) => conn.put("trips", after, id));
    return after;
  };

  const drop = async (id: string): Promise<void> => {
    await hydrate();
    const trip = memory.get(id);
    if (trip) {
      memory.delete(id);
      notify();
      releaseFor(trip);
    }
    for (const listener of dropListeners) listener(id);
    await write(async (conn) => {
      const tx = conn.transaction(["trips", "outbox"], "readwrite");
      const outbox = tx.objectStore("outbox");
      const opIds = await outbox.index("by-trip").getAllKeys(id);
      await Promise.all([
        tx.objectStore("trips").delete(id),
        ...opIds.map((opId) => outbox.delete(opId)),
        tx.done,
      ]);
    });
  };

  /** Tidy a trip away, unless something on this phone still has to be sent for it. */
  const dropIfIdle = async (id: string): Promise<void> => {
    for (const busy of busyChecks) if (busy(id)) return;
    try {
      const waiting = await db.withDb((conn) => conn.countFromIndex("outbox", "by-trip", id));
      if (waiting > 0) return;
    } catch {
      // Can't tell: keep it, and look again next time.
      return;
    }
    await drop(id);
  };

  const download = async (id: string): Promise<LocalTrip | undefined> => {
    await hydrate();
    const since = memory.get(id)?.syncedVersion;
    let trip: TripOut;
    try {
      trip = await transport.getTrip(id, since);
    } catch (error) {
      if (!isTripGone(error)) throw error;
      await drop(id);
      return undefined;
    }
    return merge(id, updateFrom(trip, since));
  };

  const syncActive = async (): Promise<boolean> => {
    await hydrate();
    let listed: TripsOut;
    try {
      listed = await transport.listTrips();
    } catch (error) {
      if (error instanceof ApiError) return false;
      throw error;
    }
    let complete = true;
    for (const header of listed.active) {
      try {
        await download(header.id);
      } catch (error) {
        if (!(error instanceof ApiError)) throw error;
        complete = false;
      }
    }
    const known = new Map<string, TripHeader>();
    for (const header of [...listed.active, ...listed.finished]) known.set(header.id, header);
    const cutoff = now() - FINISHED_KEPT_MS;
    for (const id of [...memory.keys()]) {
      const header = known.get(id);
      // The list's header tells us about a finish (or reopen) on another phone.
      if (header) await merge(id, { header });
      const trip = memory.get(id);
      if (!trip) continue;
      const finishedAt = trip.header.finished_at ? Date.parse(trip.header.finished_at) : NaN;
      const old = trip.header.status === "finished" && finishedAt < cutoff;
      if (!header || old) await dropIfIdle(id);
    }
    return complete;
  };

  const applyEvent = async (event: ServerEvent): Promise<void> => {
    const id = event.trip_id;
    if (typeof id !== "string") return;
    switch (event.type) {
      case "trip.items":
      case "trip.state": {
        await hydrate();
        if (!memory.has(id)) return; // only trips this phone keeps; others download when opened
        const header = asHeader(event.trip, id);
        const items = event.type === "trip.items" ? asItems(event.items) : [];
        if (header) await merge(id, { header, items, since: eventSince(header, items) });
        else if (items.length > 0) await merge(id, { items });
        return;
      }
      case "trip.created":
        try {
          await download(id);
        } catch (error) {
          // Offline or signed out: the next sync downloads it.
          if (!(error instanceof ApiError)) throw error;
        }
        return;
      case "trip.deleted":
        await drop(id);
        return;
      default:
        return;
    }
  };

  const remember = async (trip: TripOut): Promise<void> => {
    await merge(trip.id, updateFrom(trip));
  };

  return {
    store,
    hydrate,
    download,
    syncActive,
    applyEvent,
    remember,
    merge,
    drop,
    onDropped: (listener) => {
      dropListeners.add(listener);
      return () => {
        dropListeners.delete(listener);
      };
    },
    keepWhile: (busy) => {
      busyChecks.add(busy);
      return () => {
        busyChecks.delete(busy);
      };
    },
  };
}

export const trips = createTrips();
export const tripStore = trips.store;

/** Load the trips saved on this phone. Safe to call often; route loaders can await it. */
export function hydrateTrips(): Promise<void> {
  return trips.hydrate();
}

/**
 * Fetch a trip: only what changed if this phone has it, the whole trip if not. Merges and
 * saves it. A trip the server no longer has is dropped, with its unsent ops. Throws ApiError
 * when offline.
 */
export function downloadTrip(id: string): Promise<LocalTrip | undefined> {
  return trips.download(id);
}

/**
 * Bring every active trip onto this phone (app start, back to visible, resync), and tidy away
 * trips finished over 24 h ago or no longer listed. False if the server couldn't be reached.
 */
export function syncActiveTrips(): Promise<boolean> {
  return trips.syncActive();
}

/** trip.items and trip.state merge into trips kept here; trip.created downloads the new trip. */
export function applyTripEvent(event: ServerEvent): Promise<void> {
  return trips.applyEvent(event);
}

/** Keep a trip a screen already has (Save list, Shop this again, a trip's details), no fetch. */
export function rememberTrip(trip: TripOut): Promise<void> {
  return trips.remember(trip);
}

/** Remove a trip, and its unsent ops, from this phone. */
export function dropTrip(id: string): Promise<void> {
  return trips.drop(id);
}

export function useLocalTrip(id: string): LocalTrip | undefined {
  return useSyncExternalStore(
    tripStore.subscribe,
    () => tripStore.get(id),
    () => tripStore.get(id),
  );
}

export function useLocalTrips(): readonly LocalTrip[] {
  return useSyncExternalStore(tripStore.subscribe, tripStore.list, tripStore.list);
}
