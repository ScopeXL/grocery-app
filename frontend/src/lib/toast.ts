/**
 * Toasts with an optional action (usually Undo). Shown for 6 seconds (docs/UX.md §1), at most
 * three at once. A toast that's done first eases out (`leaving`, styles/motion.css), then goes.
 */
import { createStore } from "./store";

export interface Toast {
  id: number;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  /** Easing out: it can't be tapped, and screen readers skip it. */
  leaving?: boolean;
}

export const toasts = createStore<Toast[]>([]);
export const TOAST_MS = 6000;
/** How long a toast takes to ease out (motion.css's exit time). */
export const TOAST_EXIT_MS = 180;
const MOST_SHOWN = 3;
let nextId = 1;

function reducedMotion(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

export function showToast(message: string, action?: { label: string; onAction: () => void }) {
  const id = nextId++;
  const toast: Toast = action
    ? { id, message, actionLabel: action.label, onAction: action.onAction }
    : { id, message };
  toasts.set((list) => [...list, toast]);
  // A fourth one: the oldest eases out to make room.
  const shown = toasts.get().filter((other) => !other.leaving);
  for (const old of shown.slice(0, Math.max(0, shown.length - MOST_SHOWN))) dismissToast(old.id);
  setTimeout(() => {
    dismissToast(id);
  }, TOAST_MS);
  return id;
}

export function dismissToast(id: number): void {
  const toast = toasts.get().find((shown) => shown.id === id);
  if (!toast || toast.leaving) return;
  const remove = () => {
    toasts.set((list) => list.filter((shown) => shown.id !== id));
  };
  if (reducedMotion()) {
    remove();
    return;
  }
  toasts.set((list) =>
    list.map((shown) => (shown.id === id ? { ...shown, leaving: true } : shown)),
  );
  setTimeout(remove, TOAST_EXIT_MS);
}

/** Clear every toast (leaving shopping mode: its Undo buttons belong to that screen). */
export function clearToasts(): void {
  toasts.set([]);
}

/**
 * Where toasts sit: just above a screen's bottom bar when it has one (so they never cover its
 * buttons), else above the tab bar. While a sheet is open they sit at its bottom, since the page
 * behind it can't be tapped. Bars and sheets register an anchor element (ui/ToastAnchor); the
 * newest one still on screen wins. No style is computed.
 */
export const toastAnchor = createStore<HTMLElement | null>(null);
const anchors: HTMLElement[] = [];

/** Toasts show in `node` until the returned function runs (when it leaves the screen). */
export function anchorToasts(node: HTMLElement): () => void {
  anchors.push(node);
  toastAnchor.set(node);
  return () => {
    const at = anchors.lastIndexOf(node);
    if (at !== -1) anchors.splice(at, 1);
    toastAnchor.set(anchors.at(-1) ?? null);
  };
}
