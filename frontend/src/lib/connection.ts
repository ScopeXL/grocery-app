/**
 * Is the server reachable? Decided by real request results, never by navigator.onLine alone
 * (docs/PLAN.md §9.4). The offline pill appears only after 3 s of unreachability.
 */
import { createStore } from "./store";

export type Reachability = "unknown" | "reachable" | "unreachable";

export interface ConnectionState {
  server: Reachability;
  showOffline: boolean;
}

export const connection = createStore<ConnectionState>({ server: "unknown", showOffline: false });

const OFFLINE_PILL_DELAY_MS = 3000;
let offlineTimer: ReturnType<typeof setTimeout> | undefined;

export function markReachable(): void {
  clearTimeout(offlineTimer);
  offlineTimer = undefined;
  connection.set((s) =>
    s.server === "reachable" && !s.showOffline ? s : { server: "reachable", showOffline: false },
  );
}

export function markUnreachable(): void {
  if (connection.get().server === "unreachable") return;
  connection.set((s) => ({ ...s, server: "unreachable" }));
  offlineTimer ??= setTimeout(() => {
    offlineTimer = undefined;
    if (connection.get().server === "unreachable") {
      connection.set((s) => ({ ...s, showOffline: true }));
    }
  }, OFFLINE_PILL_DELAY_MS);
}
