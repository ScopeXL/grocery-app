/**
 * Trip photos on the phone (docs/PLAN.md §9.5, docs/adr/0016). Asks the service worker to save
 * a trip's product photos before the store, and to let them go once no trip needs them.
 *
 * Only Kroger's product photos are saved, in their own cache that keeps them at most 3 days.
 * Kroger's image host sends no CORS headers, so the saved copies are opaque. Any other image
 * (sample mode serves its photos from /api, which the worker never touches) is left to the
 * browser, and isn't counted. The names below must match src/sw.ts.
 */

export const IMAGE_CACHE = "kroger-img-v1";
const PHOTO_ORIGIN = "https://www.kroger.com";
const PHOTO_PATH = "/product/images/";
/** Give up waiting if the worker goes quiet this long (iOS may stop it mid-way). */
export const WARM_QUIET_MS = 20_000;

export interface WarmProgress {
  done: number;
  total: number;
  saved: number;
}

export interface WarmResult {
  saved: number;
  total: number;
}

interface Controller {
  postMessage: (message: unknown, transfer: Transferable[]) => void;
}

export interface ImagesDeps {
  /** navigator.serviceWorker, or undefined where there is none. */
  serviceWorker?: { readonly controller: Controller | null } | undefined;
  createChannel?: () => MessageChannel;
  caches?: Pick<CacheStorage, "open"> | undefined;
  setTimeout?: (callback: () => void, ms: number) => ReturnType<typeof setTimeout>;
  clearTimeout?: (handle: ReturnType<typeof setTimeout> | undefined) => void;
}

export interface Images {
  warmTripImages: (
    tripId: string,
    urls: readonly string[],
    onProgress?: (saved: number, total: number) => void,
  ) => Promise<WarmResult>;
  releaseTripImages: (urls: readonly string[], keep?: readonly string[]) => Promise<void>;
  forgetImage: (url: string) => Promise<void>;
}

/** Is this one of Kroger's product photos (the only images the worker saves)? */
export function isProductPhoto(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.origin === PHOTO_ORIGIN && parsed.pathname.startsWith(PHOTO_PATH);
  } catch {
    return false;
  }
}

function asProgress(value: unknown): WarmProgress | undefined {
  if (typeof value !== "object" || value === null) return undefined;
  const { done, total, saved } = value as Partial<WarmProgress>;
  if (typeof done !== "number" || typeof total !== "number" || typeof saved !== "number") {
    return undefined;
  }
  return { done, total, saved };
}

export function createImages(deps: ImagesDeps = {}): Images {
  const worker: ImagesDeps["serviceWorker"] =
    "serviceWorker" in deps
      ? deps.serviceWorker
      : "serviceWorker" in navigator
        ? navigator.serviceWorker
        : undefined;
  const cacheStorage: ImagesDeps["caches"] =
    "caches" in deps ? deps.caches : "caches" in globalThis ? caches : undefined;
  const createChannel = deps.createChannel ?? (() => new MessageChannel());
  const startTimer =
    deps.setTimeout ?? ((callback: () => void, ms: number) => setTimeout(callback, ms));
  const stopTimer =
    deps.clearTimeout ??
    ((handle: ReturnType<typeof setTimeout> | undefined) => {
      clearTimeout(handle);
    });

  const forget = async (urls: readonly string[]): Promise<void> => {
    if (!cacheStorage || urls.length === 0) return;
    try {
      const cache = await cacheStorage.open(IMAGE_CACHE);
      await Promise.all(urls.map((url) => cache.delete(url, { ignoreVary: true })));
    } catch {
      // Nothing saved, or no storage: nothing to forget.
    }
  };

  const warmTripImages: Images["warmTripImages"] = (tripId, urls, onProgress) => {
    const photos = [...new Set(urls)].filter(isProductPhoto);
    const total = photos.length;
    const controller = worker?.controller ?? null;
    if (controller === null || total === 0) return Promise.resolve({ saved: 0, total });
    return new Promise((resolve) => {
      const channel = createChannel();
      let result: WarmResult = { saved: 0, total };
      let timer: ReturnType<typeof setTimeout> | undefined;
      const finish = (): void => {
        stopTimer(timer);
        channel.port1.onmessage = null;
        channel.port1.close();
        resolve(result);
      };
      const waitQuietly = (): void => {
        stopTimer(timer);
        timer = startTimer(finish, WARM_QUIET_MS);
      };
      channel.port1.onmessage = (event: MessageEvent) => {
        const progress = asProgress(event.data);
        if (!progress) return;
        result = { saved: progress.saved, total: progress.total };
        onProgress?.(progress.saved, progress.total);
        if (progress.done >= progress.total) finish();
        else waitQuietly();
      };
      waitQuietly();
      controller.postMessage({ type: "TRIP_IMAGES_WARM", tripId, urls: photos }, [channel.port2]);
    });
  };

  const releaseTripImages: Images["releaseTripImages"] = async (urls, keep = []) => {
    const kept = new Set(keep);
    const drop = [...new Set(urls)].filter((url) => isProductPhoto(url) && !kept.has(url));
    if (drop.length === 0) return;
    const controller = worker?.controller ?? null;
    if (controller) {
      controller.postMessage({ type: "TRIP_IMAGES_RELEASE", urls: drop, keep: [...kept] }, []);
      return;
    }
    // No worker in charge of this page (a hard reload, say): delete them from here.
    await forget(drop);
  };

  return {
    warmTripImages,
    releaseTripImages,
    // A saved photo that fails to draw is deleted, so the next try fetches it again (PLAN §9.5).
    forgetImage: (url) => forget([url]),
  };
}

const images = createImages();

/**
 * Save a trip's photos for the store, 4 at a time. `onProgress(saved, total)` follows along;
 * it resolves with how many are saved, or `{saved: 0, total}` when no service worker controls
 * the page yet. `total` counts Kroger product photos, once each.
 */
export function warmTripImages(
  tripId: string,
  urls: readonly string[],
  onProgress?: (saved: number, total: number) => void,
): Promise<WarmResult> {
  return images.warmTripImages(tripId, urls, onProgress);
}

/** Delete saved photos, except those in `keep` (ones another active trip still shows). */
export function releaseTripImages(
  urls: readonly string[],
  keep: readonly string[] = [],
): Promise<void> {
  return images.releaseTripImages(urls, keep);
}

/** Delete one saved photo, e.g. when it fails to draw. */
export function forgetImage(url: string): Promise<void> {
  return images.forgetImage(url);
}
