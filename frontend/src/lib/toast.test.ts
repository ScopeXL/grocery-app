import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  anchorToasts,
  clearToasts,
  dismissToast,
  showToast,
  TOAST_EXIT_MS,
  TOAST_MS,
  toastAnchor,
  toasts,
} from "./toast";

describe("where toasts sit", () => {
  it("in an open sheet, then back above the bar when it closes", () => {
    const bar = document.createElement("div");
    const sheet = document.createElement("div");
    const barGone = anchorToasts(bar);
    expect(toastAnchor.get()).toBe(bar);
    const sheetGone = anchorToasts(sheet);
    expect(toastAnchor.get()).toBe(sheet);
    sheetGone();
    expect(toastAnchor.get()).toBe(bar);
    barGone();
    expect(toastAnchor.get()).toBeNull();
  });

  it("stays in the sheet when the screen's bar goes first", () => {
    const bar = document.createElement("div");
    const sheet = document.createElement("div");
    const barGone = anchorToasts(bar);
    const sheetGone = anchorToasts(sheet);
    barGone();
    expect(toastAnchor.get()).toBe(sheet);
    sheetGone();
    expect(toastAnchor.get()).toBeNull();
  });
});

describe("a toast's life", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearToasts();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows for 6 seconds, eases out, then goes", () => {
    showToast("Milk added");
    expect(toasts.get().map((toast) => toast.message)).toEqual(["Milk added"]);
    vi.advanceTimersByTime(TOAST_MS);
    expect(toasts.get()[0]?.leaving).toBe(true);
    vi.advanceTimersByTime(TOAST_EXIT_MS);
    expect(toasts.get()).toEqual([]);
  });

  it("eases out as soon as it's dismissed (Undo), once", () => {
    const id = showToast("Removed Mia", { label: "Undo", onAction: vi.fn() });
    dismissToast(id);
    dismissToast(id);
    expect(toasts.get()[0]?.leaving).toBe(true);
    vi.advanceTimersByTime(TOAST_EXIT_MS);
    expect(toasts.get()).toEqual([]);
  });

  it("keeps three at most: a fourth eases the oldest out", () => {
    for (const message of ["One", "Two", "Three", "Four"]) showToast(message);
    const staying = toasts.get().filter((toast) => !toast.leaving);
    expect(staying.map((toast) => toast.message)).toEqual(["Two", "Three", "Four"]);
    expect(toasts.get().find((toast) => toast.message === "One")?.leaving).toBe(true);
  });
});
