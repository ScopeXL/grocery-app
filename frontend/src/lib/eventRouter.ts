/**
 * Turns live-update events into cache updates (docs/PLAN.md §9.4). Planning events only
 * invalidate (the server computes totals), debounced 250 ms with a 1 s ceiling.
 */
import type { QueryClient, QueryKey } from "@tanstack/react-query";

import { qk } from "../api/keys";
import type { ServerEvent } from "./events";

const DEBOUNCE_MS = 250;
const MAX_WAIT_MS = 1000;

export function createInvalidator(queryClient: QueryClient) {
  const pending = new Map<string, QueryKey>();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let firstQueuedAt: number | undefined;

  const flush = () => {
    timer = undefined;
    firstQueuedAt = undefined;
    const keys = [...pending.values()];
    pending.clear();
    for (const queryKey of keys) void queryClient.invalidateQueries({ queryKey });
  };

  return (queryKey: QueryKey) => {
    pending.set(JSON.stringify(queryKey), queryKey);
    const now = Date.now();
    firstQueuedAt ??= now;
    clearTimeout(timer);
    const wait = Math.min(DEBOUNCE_MS, Math.max(0, firstQueuedAt + MAX_WAIT_MS - now));
    timer = setTimeout(flush, wait);
  };
}

export function createEventHandler(queryClient: QueryClient, onSignedOut: () => void) {
  const invalidate = createInvalidator(queryClient);
  return (event: ServerEvent) => {
    switch (event.type) {
      case "hello":
        if (event.mode === "resync") void queryClient.invalidateQueries();
        break;
      case "members.changed":
        invalidate(qk.members());
        invalidate(qk.session());
        break;
      case "settings.changed":
        invalidate(qk.settings());
        invalidate(qk.session());
        break;
      case "session.expired":
        onSignedOut();
        break;
      default:
        break;
    }
  };
}
