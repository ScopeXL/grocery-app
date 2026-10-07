/// <reference lib="webworker" />
/**
 * Service worker (docs/PLAN.md §9.5): precache the app shell and fall back to index.html for
 * navigations so the app opens offline, and keep a trip's product photos so shopping mode shows
 * them with no signal. It deliberately has NO route for /api: API responses are never cached or
 * intercepted (IndexedDB is the offline layer, and cookie-authenticated data must not outlive
 * signing out). Updates wait for the user to tap Refresh; nothing reloads the app under a shopper.
 *
 * Photos (docs/adr/0016): Kroger's product photos only, cache first, at most 150, kept at most
 * 3 days, given up first when storage runs short, and deleted once their trip is over. Kroger's
 * image host sends no CORS headers (docs/KROGER.md), so the copies are opaque (status 0).
 * The names below must match src/lib/images.ts.
 */
import { CacheableResponsePlugin } from "workbox-cacheable-response";
import { clientsClaim } from "workbox-core";
import type { WorkboxPlugin } from "workbox-core/types.js";
import { ExpirationPlugin } from "workbox-expiration";
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
  type PrecacheEntry,
} from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { CacheFirst } from "workbox-strategies";

declare let self: ServiceWorkerGlobalScope & { __WB_MANIFEST: (PrecacheEntry | string)[] };

const IMAGE_CACHE = "kroger-img-v1";
const IMAGE_ORIGIN = "https://www.kroger.com";
const IMAGE_PATH = "/product/images/";
const WARM_AT_ONCE = 4;

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
// The first install takes charge of the open page at once, so a trip's photos can be saved
// without a reload. Later versions still wait for Refresh (SKIP_WAITING below).
clientsClaim();
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), { denylist: [/^\/api\//] }),
);

/**
 * Workbox's plugin classes declare each hook as `T | undefined`, which exactOptionalPropertyTypes
 * won't accept as an optional hook. They are complete plugins, so say so once, here.
 */
function plugin(instance: object): WorkboxPlugin {
  return instance;
}

const photos = new CacheFirst({
  cacheName: IMAGE_CACHE,
  matchOptions: { ignoreVary: true },
  fetchOptions: { credentials: "omit" },
  plugins: [
    plugin(new CacheableResponsePlugin({ statuses: [0, 200] })),
    plugin(
      new ExpirationPlugin({ maxEntries: 150, maxAgeSeconds: 3 * 86_400, purgeOnQuotaError: true }),
    ),
  ],
});

function isProductPhoto(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.origin === IMAGE_ORIGIN && parsed.pathname.startsWith(IMAGE_PATH);
  } catch {
    return false;
  }
}

registerRoute(
  ({ url, request }) => request.destination === "image" && isProductPhoto(url.href),
  photos,
);

/** Product photo URLs from a message, once each; anything else is ignored. */
function photoUrls(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const urls = value.filter((url: unknown): url is string => typeof url === "string");
  return [...new Set(urls)].filter(isProductPhoto);
}

/** Save photos through the photo strategy, 4 at a time, reporting {done, total, saved}. */
async function warm(
  event: ExtendableEvent,
  urls: readonly string[],
  port: MessagePort | undefined,
): Promise<void> {
  const total = urls.length;
  let next = 0;
  let done = 0;
  let saved = 0;
  const report = (): void => {
    port?.postMessage({ done, total, saved });
  };
  if (total > 0) {
    const cache = await caches.open(IMAGE_CACHE);
    const worker = async (): Promise<void> => {
      for (let url = urls[next++]; url !== undefined; url = urls[next++]) {
        try {
          const request = new Request(url, { mode: "no-cors", credentials: "omit" });
          await Promise.allSettled(photos.handleAll({ event, request }));
          if (await cache.match(request, { ignoreVary: true })) saved += 1;
        } catch {
          // Not saved this time; the next warm-up tries again.
        }
        done += 1;
        report();
      }
    };
    await Promise.all(Array.from({ length: Math.min(WARM_AT_ONCE, total) }, worker));
  } else {
    report();
  }
  port?.close();
}

/** Delete saved photos, except the ones another trip still shows. */
async function release(urls: readonly string[], keep: readonly string[]): Promise<void> {
  const kept = new Set(keep);
  const cache = await caches.open(IMAGE_CACHE);
  await Promise.all(
    urls.filter((url) => !kept.has(url)).map((url) => cache.delete(url, { ignoreVary: true })),
  );
}

self.addEventListener("message", (event) => {
  const data: unknown = event.data;
  if (typeof data !== "object" || data === null) return;
  const message = data as { type?: unknown; urls?: unknown; keep?: unknown };
  if (message.type === "SKIP_WAITING") {
    void self.skipWaiting();
  } else if (message.type === "TRIP_IMAGES_WARM") {
    event.waitUntil(warm(event, photoUrls(message.urls), event.ports[0]));
  } else if (message.type === "TRIP_IMAGES_RELEASE") {
    const keep = Array.isArray(message.keep)
      ? message.keep.filter((url: unknown): url is string => typeof url === "string")
      : [];
    event.waitUntil(release(photoUrls(message.urls), keep));
  }
});
