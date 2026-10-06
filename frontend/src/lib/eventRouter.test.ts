import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createEventHandler, createInvalidator } from "./eventRouter";

let client: QueryClient;

beforeEach(() => {
  vi.useFakeTimers();
  client = new QueryClient();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("event router", () => {
  it("debounces repeated invalidations into one per key", () => {
    const spy = vi.spyOn(client, "invalidateQueries");
    const invalidate = createInvalidator(client);
    invalidate(["members"]);
    invalidate(["members"]);
    invalidate(["session"]);
    expect(spy).not.toHaveBeenCalled();
    vi.advanceTimersByTime(250);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("never waits longer than a second under a steady stream", () => {
    const spy = vi.spyOn(client, "invalidateQueries");
    const invalidate = createInvalidator(client);
    for (let i = 0; i < 10; i++) {
      invalidate(["members"]);
      vi.advanceTimersByTime(200);
    }
    expect(spy).toHaveBeenCalled();
  });

  it("signs out on session.expired and refetches everything on resync", () => {
    const signedOut = vi.fn();
    const spy = vi.spyOn(client, "invalidateQueries");
    const handle = createEventHandler(client, signedOut);
    handle({ type: "hello", mode: "resync" });
    expect(spy).toHaveBeenCalledWith();
    handle({ type: "session.expired" });
    expect(signedOut).toHaveBeenCalledOnce();
  });
});
