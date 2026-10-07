/**
 * The phone's own database (docs/PLAN.md §9.4): trips being shopped, the outbox of shopping
 * actions not yet sent, ops the server refused as malformed (the dead-letter store), and small
 * values such as this device's client ID. It changes only through versioned upgrade() steps, so
 * an app update never wipes it.
 *
 * iOS can drop IndexedDB connections after the app has been in the background, so every call
 * goes through withDb(), which reopens the database once on UnknownError or InvalidStateError.
 */
import { openDB, type DBSchema, type IDBPDatabase } from "idb";

import type { DeadOp, PendingOp } from "./outbox";
import type { LocalTrip } from "./trips";

export const DB_NAME = "dinnerbell";
export const DB_VERSION = 1;

export interface DinnerBellSchema extends DBSchema {
  /** Active trips, and trips finished in the last 24 h, keyed by trip id. */
  trips: { key: string; value: LocalTrip };
  /** Shopping actions not yet accepted by the server, keyed by op_id. */
  outbox: { key: string; value: PendingOp; indexes: { "by-trip": string } };
  /** Ops the server refused as malformed (a client bug), kept for diagnosis. */
  deadletter: { key: string; value: DeadOp };
  /** Small values by name: the client ID, the last client_seq, and so on. */
  meta: { key: string; value: unknown };
}

export type LocalDatabase = IDBPDatabase<DinnerBellSchema>;

export interface LocalDb {
  /** Run `fn` against the open database, reopening once if the connection was lost. */
  withDb: <T>(fn: (db: LocalDatabase) => Promise<T>) => Promise<T>;
  getMeta: (key: string) => Promise<unknown>;
  setMeta: (key: string, value: unknown) => Promise<void>;
  /** This device's ID for the ops API: generated once, then kept. Never fails. */
  clientId: () => Promise<string>;
  close: () => void;
}

export interface LocalDbOptions {
  name?: string;
  randomId?: () => string;
}

const CLIENT_ID_KEY = "client_id";

/** Each step brings an older database up to the next version. Never edit a shipped step. */
function upgrade(db: LocalDatabase, oldVersion: number): void {
  if (oldVersion < 1) {
    db.createObjectStore("trips");
    const outbox = db.createObjectStore("outbox", { keyPath: "op_id" });
    outbox.createIndex("by-trip", "trip_id");
    db.createObjectStore("deadletter", { keyPath: "op_id" });
    db.createObjectStore("meta");
  }
}

/** The errors a dropped connection produces; anything else is a real failure. */
export function isConnectionLost(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("name" in error)) return false;
  return error.name === "UnknownError" || error.name === "InvalidStateError";
}

export function createLocalDb(options: LocalDbOptions = {}): LocalDb {
  const name = options.name ?? DB_NAME;
  const randomId = options.randomId ?? (() => crypto.randomUUID());
  let opening: Promise<LocalDatabase> | undefined;
  let clientIdPromise: Promise<string> | undefined;

  const forget = (): void => {
    const current = opening;
    opening = undefined;
    void current?.then(
      (db) => {
        db.close();
      },
      () => undefined,
    );
  };

  const open = (): Promise<LocalDatabase> => {
    opening ??= openDB<DinnerBellSchema>(name, DB_VERSION, {
      upgrade: (db, oldVersion) => {
        upgrade(db, oldVersion);
      },
      // A newer version of the app wants to upgrade: step aside so it can.
      blocking: forget,
      // The browser closed the connection (iOS does this): open a new one next time.
      terminated: () => {
        opening = undefined;
      },
    }).catch((error: unknown) => {
      opening = undefined;
      throw error;
    });
    return opening;
  };

  const withDb = async <T>(fn: (db: LocalDatabase) => Promise<T>): Promise<T> => {
    try {
      return await fn(await open());
    } catch (error) {
      if (!isConnectionLost(error)) throw error;
      forget();
      return fn(await open());
    }
  };

  const clientId = (): Promise<string> => {
    clientIdPromise ??= withDb(async (db) => {
      const tx = db.transaction("meta", "readwrite");
      const stored = await tx.store.get(CLIENT_ID_KEY);
      if (typeof stored === "string" && stored !== "") {
        await tx.done;
        return stored;
      }
      const id = randomId();
      await Promise.all([tx.store.put(id, CLIENT_ID_KEY), tx.done]);
      return id;
    }).catch(() => {
      // No storage (a private window, or full): this session still gets an ID of its own.
      return randomId();
    });
    return clientIdPromise;
  };

  return {
    withDb,
    getMeta: (key) => withDb((db) => db.get("meta", key)),
    setMeta: async (key, value) => {
      await withDb((db) => db.put("meta", value, key));
    },
    clientId,
    close: forget,
  };
}

export const localDb = createLocalDb();
export const { withDb, getMeta, setMeta, clientId } = localDb;
