/** Toasts with an optional action (usually Undo). Shown for 6 seconds (docs/UX.md §1). */
import { createStore } from "./store";

export interface Toast {
  id: number;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const toasts = createStore<Toast[]>([]);
export const TOAST_MS = 6000;
let nextId = 1;

export function showToast(message: string, action?: { label: string; onAction: () => void }) {
  const id = nextId++;
  const toast: Toast = action
    ? { id, message, actionLabel: action.label, onAction: action.onAction }
    : { id, message };
  toasts.set((list) => [...list.slice(-2), toast]);
  setTimeout(() => {
    dismissToast(id);
  }, TOAST_MS);
  return id;
}

export function dismissToast(id: number): void {
  toasts.set((list) => list.filter((toast) => toast.id !== id));
}

/** Clear every toast (leaving shopping mode: its Undo buttons belong to that screen). */
export function clearToasts(): void {
  toasts.set([]);
}

/**
 * Where toasts sit: just above a screen's bottom bar when it has one (so they never cover its
 * buttons), else above the tab bar. Bars register an anchor element here; no style is computed.
 */
export const toastAnchor = createStore<HTMLElement | null>(null);
