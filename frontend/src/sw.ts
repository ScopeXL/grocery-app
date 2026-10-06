/// <reference lib="webworker" />
/**
 * Service worker (docs/PLAN.md §9.5): precache the app shell and fall back to index.html for
 * navigations so the app opens offline. It deliberately has NO route for /api: API responses
 * are never cached or intercepted (IndexedDB is the offline layer, from M3).
 * Updates wait for the user to tap Refresh; nothing reloads the app under a shopper.
 */
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
  type PrecacheEntry,
} from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

declare let self: ServiceWorkerGlobalScope & { __WB_MANIFEST: (PrecacheEntry | string)[] };

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), { denylist: [/^\/api\//] }),
);

self.addEventListener("message", (event) => {
  const data = event.data as { type?: string } | null;
  if (data?.type === "SKIP_WAITING") void self.skipWaiting();
});
