import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { toastAnchor } from "../lib/toast";
import { Sheet } from "./Sheet";
import { ToastAnchor } from "./ToastAnchor";

beforeAll(() => {
  // jsdom has no modal dialogs; opening and closing are all these tests need.
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
});
afterEach(cleanup);

function Stepped({ step, choice }: { step: string; choice: string }) {
  return (
    <Sheet open title="Add an item" step={step} onClose={vi.fn()}>
      <button type="button">{choice}</button>
    </Sheet>
  );
}

describe("a sheet with steps", () => {
  it("starts a new step at the top of its content, with focus", () => {
    const view = render(<Stepped step="search" choice="Sample result" />);
    screen.getByRole("button", { name: "Sample result" }).focus();
    view.rerender(<Stepped step="name" choice="Choose another product" />);
    expect(document.activeElement).toBe(screen.getByRole("region", { name: "Add an item" }));
  });

  it("leaves focus alone while the step stays", () => {
    const view = render(<Stepped step="search" choice="Sample result" />);
    const choice = screen.getByRole("button", { name: "Sample result" });
    choice.focus();
    view.rerender(<Stepped step="search" choice="Sample result" />);
    expect(document.activeElement).toBe(choice);
  });
});

describe("toasts while a sheet is open", () => {
  function Screen({ open, renders }: { open: boolean; renders: number }) {
    return (
      <>
        <Sheet open={open} title="Shredded cheddar" onClose={vi.fn()}>
          <p>Sample line</p>
        </Sheet>
        {/* After the content, like Screen's action bar. */}
        <div data-renders={renders} className="relative">
          <ToastAnchor />
        </div>
      </>
    );
  }

  it("show in the sheet, even after the screen's bar re-renders", () => {
    const view = render(<Screen open={false} renders={1} />);
    const onBar = toastAnchor.get();
    view.rerender(<Screen open renders={1} />);
    const inSheet = toastAnchor.get();
    expect(inSheet && screen.getByRole("dialog").contains(inSheet)).toBe(true);
    view.rerender(<Screen open renders={2} />);
    expect(toastAnchor.get()).toBe(inSheet);
    view.rerender(<Screen open={false} renders={3} />);
    expect(toastAnchor.get()).toBe(onBar);
  });
});
