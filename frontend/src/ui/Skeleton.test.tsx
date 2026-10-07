import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Skeleton } from "./Skeleton";

afterEach(cleanup);

describe("loading placeholders", () => {
  it("tell a screen reader what's loading, and hide the grey shapes", () => {
    const { container } = render(<Skeleton rows={2} label="Searching your store…" />);
    expect(screen.getByRole("status").textContent).toBe("Searching your store…");
    expect(container.querySelector("[aria-hidden='true']")?.children).toHaveLength(2);
  });
});
