import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { Sheet } from "./Sheet";

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
