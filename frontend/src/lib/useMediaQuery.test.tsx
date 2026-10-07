import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useMediaQuery } from "./useMediaQuery";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Width() {
  return <span>{useMediaQuery("(min-width: 80rem)") ? "wide" : "narrow"}</span>;
}

describe("a media query", () => {
  it("follows the screen as it changes", () => {
    let matches = false;
    const listeners = new Set<() => void>();
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({
        get matches() {
          return matches;
        },
        addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
      })),
    );
    render(<Width />);
    expect(screen.getByText("narrow")).toBeTruthy();
    act(() => {
      matches = true;
      for (const listener of listeners) listener();
    });
    expect(screen.getByText("wide")).toBeTruthy();
  });

  it("never matches where there's no matchMedia", () => {
    vi.stubGlobal("matchMedia", undefined);
    render(<Width />);
    expect(screen.getByText("narrow")).toBeTruthy();
  });
});
