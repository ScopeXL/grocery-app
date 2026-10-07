import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { toastAnchor } from "../lib/toast";
import { Sheet } from "./Sheet";
import { ToastAnchor } from "./ToastAnchor";

// The sheet's slide-away animation; a test ends it with finishSlide().
let finishSlide: () => void = () => undefined;

beforeAll(() => {
  // jsdom has no modal dialogs and no animations; these stand in for what the sheet uses.
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
  HTMLElement.prototype.getAnimations = function getAnimations() {
    const finished = new Promise<void>((resolve) => {
      finishSlide = resolve;
    });
    return [{ finished }] as unknown as Animation[];
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

describe("closing a sheet", () => {
  function Milk({ open }: { open: boolean }) {
    // Like the sheets' callers: what's inside goes away as soon as the sheet is told to close.
    return (
      <Sheet open={open} title={open ? "Milk" : "Item"} onClose={vi.fn()}>
        {open ? <p>Sample line</p> : null}
      </Sheet>
    );
  }

  it("slides away still open and showing what it showed, then closes", async () => {
    const view = render(<Milk open />);
    const dialog = screen.getByRole<HTMLDialogElement>("dialog", { name: "Milk" });
    expect(document.activeElement).toBe(dialog); // the sheet, not its Close button
    view.rerender(<Milk open={false} />);
    expect(dialog.open).toBe(true);
    expect(dialog.dataset.closing).toBe("");
    expect(dialog.inert).toBe(true);
    expect(dialog.getAttribute("aria-hidden")).toBe("true");
    expect(dialog.textContent).toContain("Milk");
    expect(dialog.textContent).toContain("Sample line");

    await act(async () => {
      finishSlide();
      await Promise.resolve();
    });
    expect(dialog.open).toBe(false);
    expect(dialog.dataset.closing).toBeUndefined();
    expect(dialog.textContent).toBe("");
  });

  it("stays open when it's opened again while sliding away", async () => {
    const view = render(<Milk open />);
    const dialog = screen.getByRole<HTMLDialogElement>("dialog", { name: "Milk" });
    view.rerender(<Milk open={false} />);
    view.rerender(<Milk open />);
    await act(async () => {
      finishSlide();
      await Promise.resolve();
    });
    expect(dialog.open).toBe(true);
    expect(dialog.dataset.closing).toBeUndefined();
    expect(dialog.inert).toBe(false);
    expect(dialog.textContent).toContain("Sample line");
  });
});
