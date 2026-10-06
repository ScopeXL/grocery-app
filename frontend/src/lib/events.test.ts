import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HELLO_TIMEOUT_MS, LiveUpdates, WATCHDOG_MS, liveStatus, type ServerEvent } from "./events";

class FakeSource {
  static all: FakeSource[] = [];
  onmessage: ((message: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(readonly url: string) {
    FakeSource.all.push(this);
  }
  close() {
    this.closed = true;
  }
  emit(data: object, lastEventId = "") {
    this.onmessage?.({ data: JSON.stringify(data), lastEventId } as MessageEvent<string>);
  }
}

function fakeDocument() {
  const listeners = new Set<() => void>();
  return {
    visibilityState: "visible" as DocumentVisibilityState,
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
    fire() {
      for (const listener of listeners) listener();
    },
  };
}

function setup(
  probe: () => Promise<"ok" | "signed-out" | "offline"> = () => Promise.resolve("ok"),
) {
  const events: ServerEvent[] = [];
  const polls: number[] = [];
  const doc = fakeDocument();
  const live = new LiveUpdates({
    onEvent: (event) => events.push(event),
    onPoll: () => polls.push(Date.now()),
    probeSession: probe,
    createSource: (url) => new FakeSource(url) as unknown as EventSource,
    random: () => 0.5,
    document: doc as unknown as Document,
  });
  return { live, events, polls, doc };
}

const latest = () => {
  const source = FakeSource.all.at(-1);
  if (!source) throw new Error("no EventSource was opened");
  return source;
};

beforeEach(() => {
  vi.useFakeTimers();
  FakeSource.all = [];
  liveStatus.set("connecting");
});

afterEach(() => {
  vi.useRealTimers();
});

describe("LiveUpdates", () => {
  it("is live after hello and passes events on", () => {
    const { live, events } = setup();
    live.start();
    latest().emit({ type: "hello", mode: "live", epoch: "e1", seq: 4 });
    latest().emit({ type: "members.changed" }, "e1:5");
    expect(liveStatus.get()).toBe("live");
    expect(events.map((e) => e.type)).toEqual(["hello", "members.changed"]);
    live.stop();
  });

  it("reconnects from the last position it saw", async () => {
    const { live } = setup();
    live.start();
    latest().emit({ type: "hello", mode: "live", epoch: "e1", seq: 4 });
    latest().emit({ type: "plan.changed" }, "e1:5");
    latest().onerror?.();
    await vi.runOnlyPendingTimersAsync();
    expect(latest().url).toBe("/api/events?since=e1%3A5");
    live.stop();
  });

  it("treats a gap in the sequence as a reason to reconnect", () => {
    const { live, events } = setup();
    live.start();
    const first = latest();
    first.emit({ type: "hello", mode: "live", epoch: "e1", seq: 4 });
    first.emit({ type: "plan.changed" }, "e1:7");
    expect(first.closed).toBe(true);
    expect(latest()).not.toBe(first);
    expect(latest().url).toBe("/api/events?since=e1%3A4");
    expect(events.map((e) => e.type)).toEqual(["hello"]);
    live.stop();
  });

  it("reconnects when nothing arrives for 40 seconds", () => {
    const { live } = setup();
    live.start();
    const first = latest();
    first.emit({ type: "hello", mode: "live", epoch: "e1", seq: 0 });
    vi.advanceTimersByTime(WATCHDOG_MS + 1);
    expect(first.closed).toBe(true);
    expect(FakeSource.all).toHaveLength(2);
    live.stop();
  });

  it("stops and reports signed out when the session is gone", async () => {
    const { live, events } = setup(() => Promise.resolve("signed-out"));
    live.start();
    latest().onerror?.();
    await vi.runOnlyPendingTimersAsync();
    expect(liveStatus.get()).toBe("signed-out");
    expect(events.map((e) => e.type)).toContain("session.expired");
    expect(FakeSource.all).toHaveLength(1);
  });

  it("falls back to polling when no hello ever arrives (a buffering proxy)", () => {
    const { live, polls } = setup();
    live.start();
    vi.advanceTimersByTime(HELLO_TIMEOUT_MS + 1);
    expect(liveStatus.get()).toBe("polling");
    expect(polls.length).toBeGreaterThan(0);
    live.stop();
  });

  it("closes while hidden and reopens when visible", () => {
    const { live, doc } = setup();
    live.start();
    const first = latest();
    doc.visibilityState = "hidden";
    doc.fire();
    expect(first.closed).toBe(true);
    doc.visibilityState = "visible";
    doc.fire();
    expect(FakeSource.all).toHaveLength(2);
    live.stop();
  });
});
