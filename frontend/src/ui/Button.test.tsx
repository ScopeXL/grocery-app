import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Button } from "./Button";

afterEach(cleanup);

describe("a button waiting on the server", () => {
  it("keeps its name, can't be tapped again, and says it's busy", () => {
    render(<Button pending>Save changes</Button>);
    const button = screen.getByRole("button", { name: "Save changes" });
    expect(button).toHaveProperty("disabled", true);
    expect(button.getAttribute("aria-busy")).toBe("true");
  });

  it("is an ordinary button otherwise", () => {
    render(<Button>Save changes</Button>);
    const button = screen.getByRole("button", { name: "Save changes" });
    expect(button).toHaveProperty("disabled", false);
    expect(button.hasAttribute("aria-busy")).toBe(false);
  });
});
