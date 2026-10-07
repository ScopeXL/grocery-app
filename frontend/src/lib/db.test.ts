import "fake-indexeddb/auto";

import { describe, expect, it, vi } from "vitest";

import { createLocalDb, isConnectionLost } from "./db";

let count = 0;
function fresh(randomId = () => "client-1") {
  count += 1;
  return createLocalDb({ name: `db-test-${String(count)}`, randomId });
}

describe("local database", () => {
  it("has the trips, outbox, dead-letter and meta stores", async () => {
    const db = fresh();
    const stores = await db.withDb((conn) => Promise.resolve([...conn.objectStoreNames]));
    expect(stores.sort()).toEqual(["deadletter", "meta", "outbox", "trips"]);
    const indexes = await db.withDb((conn) =>
      Promise.resolve([...conn.transaction("outbox").store.indexNames]),
    );
    expect(indexes).toEqual(["by-trip"]);
  });

  it("reopens once when the connection was dropped (iOS after backgrounding)", async () => {
    const db = fresh();
    await db.setMeta("greeting", "hello");
    await db.withDb((conn) => {
      conn.close(); // as iOS does behind the app's back
      return Promise.resolve();
    });
    expect(await db.getMeta("greeting")).toBe("hello");
  });

  it("tries a lost connection only once more, and passes other errors straight on", async () => {
    const db = fresh();
    const lost = vi.fn(() => Promise.reject(new DOMException("Connection lost", "UnknownError")));
    await expect(db.withDb(lost)).rejects.toThrow("Connection lost");
    expect(lost).toHaveBeenCalledTimes(2);

    const broken = vi.fn(() => Promise.reject(new Error("A real failure")));
    await expect(db.withDb(broken)).rejects.toThrow("A real failure");
    expect(broken).toHaveBeenCalledTimes(1);
  });

  it("knows which errors mean the connection was lost", () => {
    expect(isConnectionLost(new DOMException("x", "UnknownError"))).toBe(true);
    expect(isConnectionLost(new DOMException("x", "InvalidStateError"))).toBe(true);
    expect(isConnectionLost(new DOMException("x", "QuotaExceededError"))).toBe(false);
    expect(isConnectionLost(new Error("x"))).toBe(false);
    expect(isConnectionLost("x")).toBe(false);
  });

  it("makes the client ID once and keeps it", async () => {
    count += 1;
    const name = `db-test-${String(count)}`;
    const first = createLocalDb({ name, randomId: () => "client-a" });
    expect(await first.clientId()).toBe("client-a");
    expect(await first.clientId()).toBe("client-a");
    first.close();
    const afterRestart = createLocalDb({ name, randomId: () => "client-b" });
    expect(await afterRestart.clientId()).toBe("client-a");
  });

  it("round-trips small values by name", async () => {
    const db = fresh();
    expect(await db.getMeta("missing")).toBeUndefined();
    await db.setMeta("client_seq", 41);
    expect(await db.getMeta("client_seq")).toBe(41);
  });
});
