/**
 * Turns live-update events into cache updates (docs/PLAN.md §9.4). Planning events only
 * invalidate (the server computes totals), debounced 250 ms with a 1 s ceiling.
 */
import type { QueryClient, QueryKey } from "@tanstack/react-query";

import { qk } from "../api/keys";
import type { ServerEvent } from "./events";
import { outbox } from "./outbox";
import { applyTripEvent, syncActiveTrips } from "./trips";

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
        // The stream (re)opened: send anything waiting, and catch up if we missed events.
        void outbox.flush();
        if (event.mode === "resync") {
          void queryClient.invalidateQueries();
          void syncActiveTrips();
        }
        break;
      case "trip.created":
      case "trip.items":
      case "trip.state":
        // Trip events carry the change itself; the trip on this phone merges it by version.
        void applyTripEvent(event);
        invalidate(qk.trips());
        invalidate(qk.plan());
        break;
      case "members.changed":
        invalidate(qk.members());
        invalidate(qk.session());
        break;
      case "settings.changed":
        invalidate(qk.settings());
        invalidate(qk.session());
        invalidate(qk.activeStore());
        invalidate(qk.krogerAccount()); // connected, disconnected, or "reconnect"
        break;
      case "cart.changed":
        // Items going to the Kroger cart, from this phone or another.
        if (typeof event.trip_id === "string") invalidate(qk.cart(event.trip_id));
        break;
      case "dishes.changed":
        // A dish's lines feed the list.
        invalidate(qk.dishes());
        invalidate(qk.plan());
        break;
      case "items.changed":
        // An item's size or link changes how dishes read their amounts and costs.
        invalidate(qk.items());
        invalidate(qk.dishes());
        invalidate(qk.plan());
        break;
      case "plan.changed":
        invalidate(qk.plan());
        break;
      case "session.expired":
        onSignedOut();
        break;
      default:
        break;
    }
  };
}
