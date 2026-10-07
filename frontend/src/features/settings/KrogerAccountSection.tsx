/**
 * Settings → Kroger account (UX §4.16): Connect Kroger, who connected it, Pickup or delivery,
 * and Disconnect. When Kroger has signed Dinner Bell out, a banner asks to reconnect.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingCart } from "lucide-react";
import type { ReactNode } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { relativeTime } from "../../lib/format";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { Section } from "../../ui/Screen";
import { useConnectKroger, useKrogerAccount } from "../kroger/account";
import { ModalityChoice, type Modality } from "../kroger/ModalityChoice";

function Row({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-16 flex-wrap items-center gap-3 border-b border-rule px-4 py-3 last:border-b-0">
      {children}
    </div>
  );
}

function PickupOrDelivery() {
  const queryClient = useQueryClient();
  const settings = useQuery({
    queryKey: qk.settings(),
    queryFn: async () => unwrap(await api.GET("/api/settings")),
  });
  const choose = useMutation({
    mutationFn: async (modality: Modality) =>
      unwrap(await api.PATCH("/api/settings", { body: { cart_modality: modality } })),
    onSuccess: (saved) => {
      queryClient.setQueryData(qk.settings(), saved);
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  return (
    <ModalityChoice
      label="Send lists for"
      value={choose.isPending ? choose.variables : settings.data?.cart_modality}
      disabled={!settings.data}
      onChange={(modality) => {
        choose.mutate(modality);
      }}
    />
  );
}

export function KrogerAccountSection() {
  const queryClient = useQueryClient();
  const account = useKrogerAccount();
  const connect = useConnectKroger();
  const disconnect = useMutation({
    mutationFn: async () => {
      unwrap(await api.DELETE("/api/kroger/connection"));
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: qk.krogerAccount() });
      showToast("Kroger disconnected", {
        label: "Connect again",
        onAction: () => {
          connect.mutate();
        },
      });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const data = account.data;
  if (!data) return null;
  const connectButton = (label: string) => (
    <Button
      variant={data.status === "needs_reconnect" ? "primary" : "secondary"}
      disabled={connect.isPending}
      onClick={() => {
        connect.mutate();
      }}
    >
      {label}
    </Button>
  );

  return (
    <Section title="Kroger account">
      {data.status === "needs_reconnect" ? (
        <div role="status" className="border-b border-rule bg-lemon px-4 py-3 text-on-lemon">
          <p className="text-body font-semibold">Kroger signed Dinner Bell out.</p>
          <p className="text-secondary">Reconnect to send saved lists to your Kroger cart.</p>
        </div>
      ) : null}
      {data.status === "connected" ? (
        <>
          <Row>
            <ShoppingCart aria-hidden="true" className="shrink-0 text-basil" />
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="text-body font-semibold">Connected</span>
              {data.connected_by ? (
                <span className="text-secondary text-ink-soft">By {data.connected_by}</span>
              ) : null}
              {data.connected_at ? (
                <span className="text-secondary text-ink-soft">
                  {relativeTime(data.connected_at)}
                </span>
              ) : null}
            </div>
            <Button
              variant="quiet-danger"
              disabled={disconnect.isPending}
              onClick={() => {
                disconnect.mutate();
              }}
            >
              Disconnect
            </Button>
          </Row>
          <Row>
            <PickupOrDelivery />
          </Row>
        </>
      ) : (
        <Row>
          <p className="w-full text-body text-ink-soft">
            Send a saved list straight to your Kroger cart, then check out in the Kroger app.
          </p>
          {data.can_connect ? (
            connectButton(data.status === "needs_reconnect" ? "Reconnect Kroger" : "Connect Kroger")
          ) : (
            <p className="w-full text-secondary text-ink-soft">
              Connecting isn’t set up on this server yet. Whoever runs Dinner Bell can turn it on
              (KROGER_REDIRECT_URI).
            </p>
          )}
        </Row>
      )}
      {data.demo ? (
        <Row>
          <p className="text-secondary text-ink-soft">
            Sample mode: the Kroger sign-in is a demo, and nothing reaches a real cart.
          </p>
        </Row>
      ) : null}
    </Section>
  );
}
