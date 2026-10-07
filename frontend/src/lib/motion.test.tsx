import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { arrivals, useChangeCount } from "./motion";

afterEach(cleanup);

function Total({ text }: { text: string }) {
  const changes = useChangeCount(text);
  return <span data-changes={changes}>{text}</span>;
}

describe("a total that pops when it changes", () => {
  it("counts changes, starting at none, so nothing pops on first paint", () => {
    const view = render(<Total text="About $25" />);
    expect(screen.getByText("About $25").dataset.changes).toBe("0");
    view.rerender(<Total text="About $25" />);
    expect(screen.getByText("About $25").dataset.changes).toBe("0");
    view.rerender(<Total text="About $19" />);
    expect(screen.getByText("About $19").dataset.changes).toBe("1");
    view.rerender(<Total text="About $25" />);
    expect(screen.getByText("About $25").dataset.changes).toBe("2");
  });
});

describe("a count that arrives after loading", () => {
  function Progress({ handled }: { handled: number | null }) {
    const changes = useChangeCount(handled);
    return <span data-changes={changes}>{handled ?? "…"}</span>;
  }

  it("doesn't pop when it first arrives, only when it changes after", () => {
    const view = render(<Progress handled={null} />);
    view.rerender(<Progress handled={0} />);
    expect(screen.getByText("0").dataset.changes).toBe("0");
    view.rerender(<Progress handled={1} />);
    expect(screen.getByText("1").dataset.changes).toBe("1");
  });
});

describe("a list whose later rows ease in", () => {
  it("is marked a frame after it appears, not at once", () => {
    vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame"] });
    try {
      render(
        <ul ref={arrivals} aria-label="Sample meals">
          <li>Tacos</li>
        </ul>,
      );
      const list = screen.getByRole("list", { name: "Sample meals" });
      expect(list.dataset.arrivals).toBeUndefined();
      act(() => {
        vi.advanceTimersToNextFrame();
      });
      expect(list.dataset.arrivals).toBe("");
    } finally {
      vi.useRealTimers();
    }
  });
});
