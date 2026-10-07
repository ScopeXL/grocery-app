import { Link, useRouterState } from "@tanstack/react-router";
import { WifiOff } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useRegisterSW } from "virtual:pwa-register/react";

import { connection } from "../lib/connection";
import { outbox, useOutboxStatus } from "../lib/outbox";
import { useStore } from "../lib/store";
import { dismissToast, toastAnchor, toasts } from "../lib/toast";

const UPDATE_CHECK_MS = 60 * 60 * 1000;

/**
 * The quiet connection pill: never an error wall (docs/UX.md §6, PLAN §9.4). Offline after 3 s
 * without the server; "Syncing 3…" while saved taps go out; "Sign in to sync" when the session
 * ended with taps still waiting.
 */
export function OfflinePill() {
  const { showOffline } = useStore(connection);
  const { pending, signedOut } = useOutboxStatus();
  // Shopping mode says this in its own header, out of the way of its buttons.
  const shopping = useRouterState({
    select: (state) => state.location.pathname.startsWith("/shop/"),
  });
  let pill: ReactNode = null;
  if (shopping) {
    pill = null;
  } else if (signedOut && pending > 0) {
    pill = (
      <Link
        to="/sign-in"
        className="pointer-events-auto inline-flex min-h-12 items-center gap-2 rounded-full bg-ink px-4 py-2 text-secondary font-semibold text-counter [--focus-ring:var(--counter)]"
      >
        Sign in to sync
      </Link>
    );
  } else if (showOffline) {
    pill = (
      <span className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-secondary font-semibold text-counter">
        <WifiOff aria-hidden="true" size={18} />
        {pending > 0 ? "Offline, saved on this phone" : "Offline"}
      </span>
    );
  } else if (pending > 0) {
    pill = (
      <span className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-secondary font-semibold text-counter">
        Syncing {String(pending)}…
      </span>
    );
  }
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-[calc(env(safe-area-inset-top)+8px)] z-30 flex justify-center print:hidden"
    >
      {pill}
    </div>
  );
}

/** "A new version is ready" — the app never reloads itself under someone (docs/PLAN.md §9.5). */
export function UpdatePrompt() {
  const shopping = useRouterState({
    select: (state) => state.location.pathname.startsWith("/shop/"),
  });
  const { pending } = useOutboxStatus();
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

  // Never under a shopper, and never while taps are waiting to be sent (PLAN §9.5).
  if (!needRefresh || shopping || pending > 0) return null;
  return (
    <div className="fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+var(--tabbar-h)+12px)] z-30 flex justify-center px-4 print:hidden lg:bottom-6">
      <div className="flex items-center gap-3 rounded-button bg-ink py-2 pr-2 pl-4 text-counter [--focus-ring:var(--counter)]">
        <span className="text-secondary font-semibold">A new version is ready.</span>
        <button
          type="button"
          className="min-h-12 rounded-button bg-counter px-4 text-secondary font-bold text-ink"
          onClick={() => {
            void outbox.flush().then(() => updateServiceWorker(true));
          }}
        >
          Refresh
        </button>
      </div>
    </div>
  );
}

/** Toasts sit in the thumb zone: just above the screen's bottom bar, else above the tab bar. */
export function ToastRegion() {
  const list = useStore(toasts);
  const anchor = useStore(toastAnchor);
  const items = list.map((toast) => (
    <div
      key={toast.id}
      className="pointer-events-auto flex w-full max-w-md items-center justify-between gap-3 rounded-button bg-ink py-2 pr-2 pl-4 text-counter [--focus-ring:var(--counter)]"
    >
      <span className="text-secondary font-semibold">{toast.message}</span>
      {toast.actionLabel ? (
        <button
          type="button"
          // The toast flips with the theme (ink on counter), so its action is the inverse pill:
          // lemon text on the light dark-mode toast was unreadable (1.17:1).
          className="min-h-12 rounded-button bg-counter px-4 text-secondary font-bold text-ink"
          onClick={() => {
            toast.onAction?.();
            dismissToast(toast.id);
          }}
        >
          {toast.actionLabel}
        </button>
      ) : null}
    </div>
  ));
  if (anchor) return createPortal(items, anchor);
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+var(--tabbar-h)+12px)] z-40 flex flex-col items-center gap-2 px-4 print:hidden lg:bottom-6"
    >
      {items}
    </div>
  );
}

/** Put inside a fixed bottom bar: toasts then appear just above it. */
export function ToastAnchor() {
  return (
    <div
      ref={(node) => {
        toastAnchor.set(node);
        return () => {
          if (toastAnchor.get() === node) toastAnchor.set(null);
        };
      }}
      role="status"
      aria-live="polite"
      className="pointer-events-none absolute inset-x-0 bottom-full mb-2 flex flex-col items-center gap-2 px-4 print:hidden"
    />
  );
}
