/**
 * "Get ready for the store" (PLAN §9.5, UX §4.12): when a trip opens, save it on this phone,
 * save its photos, check the app opens without signal, and ask the browser to keep this
 * phone's storage. It ends on the one line that matters: Ready for the store.
 */
import { Check, Info, Loader } from "lucide-react";
import { useEffect, useState } from "react";

import { warmTripImages } from "../../lib/images";
import { isAndroid, isIOS } from "../../lib/platform";
import { useStore } from "../../lib/store";
import { photoUrls } from "../../lib/trips";
import type { TripView } from "../../lib/tripView";
import { wakeLockState } from "../../lib/wakeLock";
import { Button } from "../../ui/Button";

const KEY = "dinnerbell.ready";

function seen(tripId: string): boolean {
  try {
    return localStorage.getItem(`${KEY}.${tripId}`) === "1";
  } catch {
    return false;
  }
}

/** When the screen can't be kept on (PLAN §9.7): where to change it, for this phone. */
function dimTip(): string {
  if (isIOS()) {
    return "Your screen may dim while you shop. Settings → Display & Brightness → Auto-Lock";
  }
  if (isAndroid()) return "Your screen may dim while you shop. Display → Screen timeout";
  return "Your screen may dim while you shop.";
}

async function worksOffline(): Promise<boolean> {
  // Older browsers have no service worker; their types say otherwise.
  const workers = (navigator as { serviceWorker?: ServiceWorkerContainer }).serviceWorker;
  if (!workers?.controller) return false;
  try {
    // Workbox stores precached files with a revision query, so match without it.
    return (await caches.match("/index.html", { ignoreSearch: true })) !== undefined;
  } catch {
    return false;
  }
}

/** Ask the browser to keep this phone's storage (iOS can clear it otherwise). */
function keepStorage(): void {
  const storage = (navigator as { storage?: StorageManager }).storage;
  void storage?.persist().catch(() => false);
}

export function ReadyCard({
  tripId,
  view,
  downloaded,
}: {
  tripId: string;
  view: TripView;
  downloaded: "pending" | "ok" | "failed";
}) {
  const [hidden, setHidden] = useState(() => seen(tripId));
  const [photos, setPhotos] = useState<{ saved: number; total: number } | null>(null);
  const [photosTried, setPhotosTried] = useState(false); // every photo tried, saved or not
  const [offline, setOffline] = useState<boolean | null>(null);
  const wake = useStore(wakeLockState);
  const key = [...photoUrls(view.trip)].sort().join(" ");

  useEffect(() => {
    if (hidden) return;
    let cancelled = false;
    const wanted = key ? key.split(" ") : [];
    void warmTripImages(tripId, wanted, (done, total) => {
      if (!cancelled) setPhotos({ saved: done, total });
    }).then((result) => {
      if (cancelled) return;
      setPhotos(result);
      setPhotosTried(true);
    });
    void worksOffline().then((ok) => {
      if (!cancelled) setOffline(ok);
    });
    keepStorage();
    return () => {
      cancelled = true;
    };
  }, [tripId, key, hidden]);

  if (hidden) return null;
  const saved = downloaded !== "pending";
  const allPhotos = photos !== null && photos.saved >= photos.total;
  // Ready once everything was tried: photos that couldn't be saved show when there's signal.
  const ready = saved && photosTried && offline !== null;
  const checks: [string, "done" | "waiting" | "partly"][] = [
    [
      downloaded === "failed" ? "Saved on this phone earlier" : "Saved on this phone",
      saved ? "done" : "waiting",
    ],
    [
      photos === null
        ? "Saving photos"
        : photos.total === 0
          ? "No photos to save"
          : `${String(photos.saved)} of ${String(photos.total)} photos saved`,
      allPhotos ? "done" : photosTried ? "partly" : "waiting",
    ],
    [
      offline === false ? "Opens without signal once installed" : "Opens without signal",
      offline !== null ? "done" : "waiting",
    ],
  ];
  return (
    <section
      aria-label="Get ready for the store"
      className="mb-6 rounded-tile border-2 border-basil bg-paper p-4"
    >
      <h2 className="mb-2 text-row font-bold">
        {ready ? "Ready for the store" : "Getting ready for the store"}
      </h2>
      <ul className="mb-3 flex flex-col gap-1">
        {checks.map(([label, state]) => (
          <li key={label} className="flex items-center gap-2 text-secondary">
            {state === "done" ? (
              <Check aria-hidden="true" className="size-5 text-basil" />
            ) : state === "partly" ? (
              <Info aria-hidden="true" className="size-5 text-ink-soft" />
            ) : (
              <Loader aria-hidden="true" className="size-5 text-ink-soft" />
            )}
            {label}
          </li>
        ))}
        <li className="flex items-start gap-2 text-secondary">
          {wake.active ? (
            <Check aria-hidden="true" className="size-5 shrink-0 text-basil" />
          ) : (
            <Info aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ink-soft" />
          )}
          {wake.active ? "Screen stays on" : dimTip()}
        </li>
      </ul>
      {ready ? (
        <Button
          variant="secondary"
          onClick={() => {
            try {
              localStorage.setItem(`${KEY}.${tripId}`, "1");
            } catch {
              // Storage refused: the card just shows again next time.
            }
            setHidden(true);
          }}
        >
          OK
        </Button>
      ) : null}
    </section>
  );
}
