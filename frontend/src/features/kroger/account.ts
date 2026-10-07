/**
 * The household's Kroger account (PLAN §7.5): read it, and start Connect Kroger. Connecting
 * leaves the app for Kroger's sign-in page; Kroger sends the phone back to the server, which
 * lands it on Settings with `?kroger=<result>`.
 */
import { useMutation, useQuery } from "@tanstack/react-query";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import type { components } from "../../api/schema";
import { showToast } from "../../lib/toast";

export type KrogerAccount = components["schemas"]["KrogerAccountOut"];
export type ConnectResult = "connected" | "denied" | "expired" | "failed";

export function useKrogerAccount() {
  return useQuery({
    queryKey: qk.krogerAccount(),
    queryFn: async () => unwrap(await api.GET("/api/kroger/account")),
  });
}

export function useConnectKroger() {
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/kroger/connect")),
    onSuccess: ({ authorize_url }) => {
      window.location.assign(authorize_url);
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
}

/** What the phone hears after coming back from Kroger's sign-in page. */
export const CONNECT_RESULTS: Record<ConnectResult, string> = {
  connected: "Kroger connected",
  denied: "Kroger wasn't connected",
  expired: "That sign-in took too long. Try Connect Kroger again.",
  failed: "Kroger couldn't be connected. Try again.",
};

export function connectResult(value: unknown): ConnectResult | undefined {
  return value === "connected" || value === "denied" || value === "expired" || value === "failed"
    ? value
    : undefined;
}
