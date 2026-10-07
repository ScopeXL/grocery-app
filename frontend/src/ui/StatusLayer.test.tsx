import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const at = { pathname: "/list" };
const outboxStatus = { pending: 0, sending: false, signedOut: false };

vi.mock("virtual:pwa-register/react", () => ({
  useRegisterSW: () => ({
    needRefresh: [true, vi.fn()],
    offlineReady: [false, vi.fn()],
    updateServiceWorker: vi.fn(() => Promise.resolve()),
  }),
}));
vi.mock("@tanstack/react-router", () => ({
  useRouterState: ({ select }: { select: (s: { location: { pathname: string } }) => unknown }) =>
    select({ location: { pathname: at.pathname } }),
  Link: ({ children }: { children: ReactNode }) => <a href="/sign-in">{children}</a>,
}));
vi.mock("../lib/outbox", () => ({
  outbox: { flush: () => Promise.resolve() },
  useOutboxStatus: () => outboxStatus,
}));

const { OfflinePill, UpdatePrompt } = await import("./StatusLayer");

afterEach(() => {
  cleanup();
  at.pathname = "/list";
  Object.assign(outboxStatus, { pending: 0, signedOut: false });
});

describe("the update prompt (PLAN §9.5)", () => {
  it("offers a refresh outside shopping mode once nothing is waiting to sync", () => {
    render(<UpdatePrompt />);
    expect(screen.getByRole("button", { name: "Refresh" })).toBeTruthy();
  });

  it("never appears inside shopping mode", () => {
    at.pathname = "/shop/trip-1";
    render(<UpdatePrompt />);
    expect(screen.queryByRole("button", { name: "Refresh" })).toBeNull();
  });

  it("waits while check-offs are still waiting to be sent", () => {
    outboxStatus.pending = 2;
    render(<UpdatePrompt />);
    expect(screen.queryByRole("button", { name: "Refresh" })).toBeNull();
  });
});

describe("the connection pill", () => {
  it("counts what's syncing, and asks to sign in when the session ended with taps waiting", () => {
    outboxStatus.pending = 3;
    const { rerender } = render(<OfflinePill />);
    expect(screen.getByRole("status").textContent).toBe("Syncing 3…");
    outboxStatus.signedOut = true;
    rerender(<OfflinePill />);
    expect(screen.getByRole("link", { name: "Sign in to sync" })).toBeTruthy();
  });
});
