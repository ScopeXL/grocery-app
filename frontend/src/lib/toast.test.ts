import { describe, expect, it } from "vitest";

import { anchorToasts, toastAnchor } from "./toast";

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
