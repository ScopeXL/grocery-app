import { describe, expect, it, vi } from "vitest";

import { createImages, IMAGE_CACHE, isProductPhoto, WARM_QUIET_MS } from "./images";

const photo = (n: number) => `https://www.kroger.com/product/images/medium/front/${String(n)}`;
const SAMPLE = "/api/kroger/fake-images/99999001.svg";

function fakeController() {
  const messages: { message: unknown; transfer: Transferable[] }[] = [];
  return {
    messages,
    controller: {
      postMessage: (message: unknown, transfer: Transferable[]) => {
        messages.push({ message, transfer });
      },
    },
  };
}

describe("trip photos", () => {
  it("knows Kroger's product photos from everything else", () => {
    expect(isProductPhoto(photo(1))).toBe(true);
    expect(isProductPhoto("https://www.kroger.com/p/sample/0001")).toBe(false);
    expect(isProductPhoto("https://images.example.com/product/images/1")).toBe(false);
    expect(isProductPhoto(SAMPLE)).toBe(false);
    expect(isProductPhoto("not a url")).toBe(false);
  });

  it("saves nothing without a service worker in charge of the page", async () => {
    const images = createImages({ serviceWorker: { controller: null } });
    expect(await images.warmTripImages("trip-1", [photo(1), photo(2), photo(2), SAMPLE])).toEqual({
      saved: 0,
      total: 2,
    });
  });

  it("asks the worker for the trip's photos once each, and follows its progress", async () => {
    const { controller, messages } = fakeController();
    const images = createImages({ serviceWorker: { controller } });
    const progress: [number, number][] = [];
    const warming = images.warmTripImages(
      "trip-1",
      [photo(1), photo(2), photo(1), SAMPLE],
      (saved, total) => progress.push([saved, total]),
    );
    expect(messages[0]?.message).toEqual({
      type: "TRIP_IMAGES_WARM",
      tripId: "trip-1",
      urls: [photo(1), photo(2)],
    });
    const port = messages[0]?.transfer[0] as MessagePort;
    port.postMessage({ done: 1, total: 2, saved: 0 }); // one couldn't be fetched
    port.postMessage({ done: 2, total: 2, saved: 1 });
    expect(await warming).toEqual({ saved: 1, total: 2 });
    expect(progress).toEqual([
      [0, 2],
      [1, 2],
    ]);
  });

  it("stops waiting when the worker goes quiet", async () => {
    const { controller } = fakeController();
    let quiet: (() => void) | undefined;
    const images = createImages({
      serviceWorker: { controller },
      setTimeout: (callback, ms) => {
        if (ms === WARM_QUIET_MS) quiet = callback;
        return 0;
      },
      clearTimeout: () => undefined,
    });
    const warming = images.warmTripImages("trip-1", [photo(1)]);
    quiet?.();
    expect(await warming).toEqual({ saved: 0, total: 1 });
  });

  it("asks the worker to delete photos no other trip shows", async () => {
    const { controller, messages } = fakeController();
    const images = createImages({ serviceWorker: { controller } });
    await images.releaseTripImages([photo(1), photo(2), SAMPLE], [photo(2)]);
    expect(messages.map((entry) => entry.message)).toEqual([
      { type: "TRIP_IMAGES_RELEASE", urls: [photo(1)], keep: [photo(2)] },
    ]);
    await images.releaseTripImages([photo(2)], [photo(2)]);
    expect(messages).toHaveLength(1); // nothing to delete, nothing sent
  });

  it("deletes from the cache itself when no worker is in charge", async () => {
    const deleted: string[] = [];
    const open = vi.fn((name: string) => {
      expect(name).toBe(IMAGE_CACHE);
      return Promise.resolve({
        delete: (url: string) => {
          deleted.push(url);
          return Promise.resolve(true);
        },
      } as unknown as Cache);
    });
    const images = createImages({ serviceWorker: undefined, caches: { open } });
    await images.releaseTripImages([photo(1), photo(2)], [photo(2)]);
    expect(deleted).toEqual([photo(1)]);
    await images.forgetImage(photo(3));
    expect(deleted).toEqual([photo(1), photo(3)]);
  });
});
