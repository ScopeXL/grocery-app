import { WifiOff } from "lucide-react";
import { useEffect } from "react";
import { useRegisterSW } from "virtual:pwa-register/react";

import { connection } from "../lib/connection";
import { useStore } from "../lib/store";
import { dismissToast, toasts } from "../lib/toast";

const UPDATE_CHECK_MS = 60 * 60 * 1000;

/** The quiet offline pill: never an error wall (docs/UX.md §6). */
export function OfflinePill() {
  const { showOffline } = useStore(connection);
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-[calc(env(safe-area-inset-top)+8px)] z-30 flex justify-center print:hidden"
    >
      {showOffline ? (
        <span className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-secondary font-semibold text-counter">
          <WifiOff aria-hidden="true" size={18} />
          Offline
        </span>
      ) : null}
    </div>
  );
}

/** "A new version is ready" — the app never reloads itself under someone (docs/PLAN.md §9.5). */
export function UpdatePrompt() {
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      if (!registration) return;
      setInterval(() => {
        void registration.update();
      }, UPDATE_CHECK_MS);
    },
  });

  useEffect(() => {
    const check = () => {
      if (document.visibilityState === "visible" && "serviceWorker" in navigator) {
        void navigator.serviceWorker.getRegistration().then((r) => r?.update());
      }
    };
    document.addEventListener("visibilitychange", check);
    return () => {
      document.removeEventListener("visibilitychange", check);
    };
  }, []);

  if (!needRefresh) return null;
  return (
    <div className="fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+84px)] z-30 flex justify-center px-4 print:hidden lg:bottom-6">
      <div className="flex items-center gap-3 rounded-button bg-ink py-2 pr-2 pl-4 text-counter">
        <span className="text-secondary font-semibold">A new version is ready.</span>
        <button
          type="button"
          className="min-h-12 rounded-button bg-lemon px-4 text-secondary font-bold text-on-lemon"
          onClick={() => void updateServiceWorker(true)}
        >
          Refresh
        </button>
      </div>
    </div>
  );
}

/** Toasts sit above the tab bar, in the thumb zone. */
export function ToastRegion() {
  const list = useStore(toasts);
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+84px)] z-40 flex flex-col items-center gap-2 px-4 print:hidden lg:bottom-6"
    >
      {list.map((toast) => (
        <div
          key={toast.id}
          className="pointer-events-auto flex w-full max-w-md items-center justify-between gap-3 rounded-button bg-ink py-2 pr-2 pl-4 text-counter"
        >
          <span className="text-secondary font-semibold">{toast.message}</span>
          {toast.actionLabel ? (
            <button
              type="button"
              className="min-h-12 rounded-button px-4 text-secondary font-bold text-lemon"
              onClick={() => {
                toast.onAction?.();
                dismissToast(toast.id);
              }}
            >
              {toast.actionLabel}
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
