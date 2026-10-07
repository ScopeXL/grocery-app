/**
 * Keeps the screen on while shopping (docs/PLAN.md §9.7): a phone that dims every 30 seconds
 * makes a list hard to follow with full hands.
 *
 * * enable() runs from the Start shopping tap (Safari is kinder to a user gesture). It asks only
 *   while the page is visible, with at most one request in flight.
 * * The browser lets go of the lock when the page is hidden; we ask again when it's visible.
 *   A lock that arrives after the page went hidden is let go at once.
 * * Refused (NotAllowedError, for example battery saver): `denied` is set, and the next tap asks
 *   once more. Becoming visible doesn't keep asking.
 * * disable() when leaving shopping mode, finishing the trip, or seeing "finished by someone
 *   else". The state lives in an external store so tests can drive a fake.
 */
import { useEffect } from "react";

import { createStore, useStore, type Store } from "./store";

export interface WakeLockState {
  supported: boolean;
  active: boolean;
  denied: boolean;
}

interface LockHandle {
  release: () => Promise<void>;
  addEventListener: (type: "release", listener: () => void) => void;
}

interface LockApi {
  request: (type: "screen") => Promise<LockHandle>;
}

export interface WakeLockDeps {
  navigator?: { wakeLock?: LockApi | undefined };
  document?: {
    readonly visibilityState: DocumentVisibilityState;
    addEventListener: (type: "visibilitychange", listener: () => void) => void;
    removeEventListener: (type: "visibilitychange", listener: () => void) => void;
  };
}

export interface WakeLock {
  state: Store<WakeLockState>;
  enable: () => void;
  disable: () => void;
}

function isNotAllowed(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "NotAllowedError"
  );
}

export function createWakeLock(deps: WakeLockDeps = {}): WakeLock {
  const lockApi: LockApi | undefined = (deps.navigator ?? navigator).wakeLock;
  const page: NonNullable<WakeLockDeps["document"]> = deps.document ?? document;
  const state = createStore<WakeLockState>({
    supported: lockApi !== undefined,
    active: false,
    denied: false,
  });
  let wanted = false;
  let held: LockHandle | null = null;
  let requesting = false;
  let listening = false;

  const letGo = (lock: LockHandle): void => {
    void lock.release().catch(() => undefined);
  };

  const ask = (fromTap: boolean): void => {
    if (!lockApi || !wanted || held || requesting) return;
    if (page.visibilityState !== "visible") return;
    if (state.get().denied && !fromTap) return;
    requesting = true;
    void lockApi.request("screen").then(
      (lock) => {
        requesting = false;
        if (!wanted || page.visibilityState !== "visible") {
          letGo(lock); // arrived too late: the page was hidden, or shopping ended
          return;
        }
        held = lock;
        lock.addEventListener("release", () => {
          if (held !== lock) return;
          held = null;
          state.set((s) => (s.active ? { ...s, active: false } : s));
        });
        state.set((s) => ({ ...s, active: true, denied: false }));
      },
      (error: unknown) => {
        requesting = false;
        const refused = isNotAllowed(error);
        state.set((s) => ({ ...s, active: false, denied: s.denied || refused }));
      },
    );
  };

  const onVisibility = (): void => {
    if (page.visibilityState === "visible") ask(false);
  };

  return {
    state,
    enable: () => {
      wanted = true;
      if (!listening) {
        page.addEventListener("visibilitychange", onVisibility);
        listening = true;
      }
      ask(true);
    },
    disable: () => {
      wanted = false;
      if (listening) {
        page.removeEventListener("visibilitychange", onVisibility);
        listening = false;
      }
      const lock = held;
      held = null;
      if (lock) letGo(lock);
      state.set((s) => (s.active ? { ...s, active: false } : s));
    },
  };
}

const wakeLock = createWakeLock();

/** { supported, active, denied }, for the "Screen stays on" note and the one-time tip. */
export const wakeLockState = wakeLock.state;

/** Keep the screen on. Call it from a tap (Start shopping) where you can. */
export function enable(): void {
  wakeLock.enable();
}

/** Let the screen sleep again: leaving shopping mode, finishing, "finished by someone else". */
export function disable(): void {
  wakeLock.disable();
}

/** Keeps the screen on while `active` and the component is mounted. */
export function useKeepAwake(active: boolean): WakeLockState {
  useEffect(() => {
    if (!active) return undefined;
    enable();
    return () => {
      disable();
    };
  }, [active]);
  return useStore(wakeLockState);
}
