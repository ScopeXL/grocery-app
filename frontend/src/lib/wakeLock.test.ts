import { describe, expect, it } from "vitest";

import { createWakeLock } from "./wakeLock";

class FakeSentinel {
  released = false;
  private readonly listeners = new Set<() => void>();
  addEventListener(_type: "release", listener: () => void): void {
    this.listeners.add(listener);
  }
  release(): Promise<void> {
    if (!this.released) {
      this.released = true;
      for (const listener of this.listeners) listener();
    }
    return Promise.resolve();
  }
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

function setup(supported = true) {
  const requests: ReturnType<typeof deferred<FakeSentinel>>[] = [];
  const listeners = new Set<() => void>();
  const page = {
    visibilityState: "visible" as DocumentVisibilityState,
    addEventListener: (_type: "visibilitychange", listener: () => void) => {
      listeners.add(listener);
    },
    removeEventListener: (_type: "visibilitychange", listener: () => void) => {
      listeners.delete(listener);
    },
  };
  const wakeLock = {
    request: () => {
      const request = deferred<FakeSentinel>();
      requests.push(request);
      return request.promise;
    },
  };
  const lock = createWakeLock({
    navigator: supported ? { wakeLock } : {},
    document: page,
  });
  const show = async (visibility: DocumentVisibilityState) => {
    page.visibilityState = visibility;
    for (const listener of listeners) listener();
    await settle();
  };
  return { lock, requests, page, listeners, show };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

const grant = async (request: ReturnType<typeof deferred<FakeSentinel>> | undefined) => {
  const sentinel = new FakeSentinel();
  request?.resolve(sentinel);
  await settle();
  return sentinel;
};

describe("wake lock", () => {
  it("asks once on enable, however many taps, and is active when granted", async () => {
    const { lock, requests } = setup();
    lock.enable();
    lock.enable();
    expect(requests).toHaveLength(1);
    await grant(requests[0]);
    expect(lock.state.get()).toEqual({ supported: true, active: true, denied: false });
    lock.enable();
    expect(requests).toHaveLength(1); // already held
  });

  it("lets go on disable, and lets go of a lock that arrives after disable", async () => {
    const { lock, requests } = setup();
    lock.enable();
    const held = await grant(requests[0]);
    lock.disable();
    expect(held.released).toBe(true);
    expect(lock.state.get().active).toBe(false);

    lock.enable();
    lock.disable();
    const late = await grant(requests[1]);
    expect(late.released).toBe(true);
    expect(lock.state.get().active).toBe(false);
  });

  it("asks again when the page is visible again", async () => {
    const { lock, requests, show } = setup();
    lock.enable();
    const first = await grant(requests[0]);
    await show("hidden");
    await first.release(); // the browser lets go when the page is hidden
    expect(lock.state.get().active).toBe(false);
    expect(requests).toHaveLength(1);

    await show("visible");
    expect(requests).toHaveLength(2);
    await grant(requests[1]);
    expect(lock.state.get().active).toBe(true);
  });

  it("drops a lock that arrives after the page was hidden, then asks again when visible", async () => {
    const { lock, requests, show } = setup();
    lock.enable();
    await show("hidden");
    const late = await grant(requests[0]);
    expect(late.released).toBe(true);
    expect(lock.state.get().active).toBe(false);

    await show("visible");
    expect(requests).toHaveLength(2);
  });

  it("doesn't ask while the page is hidden", async () => {
    const { lock, requests, show } = setup();
    await show("hidden");
    lock.enable();
    expect(requests).toHaveLength(0);
    await show("visible");
    expect(requests).toHaveLength(1);
  });

  it("remembers a refusal: becoming visible doesn't ask again, the next tap does", async () => {
    const { lock, requests, show } = setup();
    lock.enable();
    requests[0]?.reject(new DOMException("Battery saver is on", "NotAllowedError"));
    await settle();
    expect(lock.state.get()).toEqual({ supported: true, active: false, denied: true });

    await show("hidden");
    await show("visible");
    expect(requests).toHaveLength(1);

    lock.enable(); // the next tap
    expect(requests).toHaveLength(2);
    await grant(requests[1]);
    expect(lock.state.get()).toEqual({ supported: true, active: true, denied: false });
  });

  it("stops listening for visibility once disabled", async () => {
    const { lock, requests, listeners, show } = setup();
    lock.enable();
    expect(listeners.size).toBe(1);
    lock.disable();
    expect(listeners.size).toBe(0);
    await show("visible");
    expect(requests).toHaveLength(1);
  });

  it("does nothing where the browser has no wake lock", () => {
    const { lock, requests } = setup(false);
    lock.enable();
    expect(requests).toHaveLength(0);
    expect(lock.state.get()).toEqual({ supported: false, active: false, denied: false });
  });
});
