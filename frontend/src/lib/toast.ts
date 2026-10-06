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
