/**
 * Send to Kroger cart (UX §5.5, PLAN §7.5): Pickup or delivery, what goes and what can't, then
 * what happened to each item. The server sends one item at a time and never retries; this
 * sheet only ever sends what the person tapped for:
 *
 * * **Send N items:** everything not sent yet.
 * * **Send these again:** only what didn't go (Kroger said no, or didn't answer).
 * * **Send again anyway:** everything, already in the cart or not, behind a second sheet. A cart
 *   add can't be undone here, so this is the one place a confirmation beats Undo (UX §1).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import type { components } from "../../api/schema";
import { relativeTime } from "../../lib/format";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { Sheet } from "../../ui/Sheet";
import { ModalityChoice, type Modality } from "../kroger/ModalityChoice";

type Cart = components["schemas"]["CartOut"];
type CartLine = components["schemas"]["CartLineOut"];

function items(count: number): string {
  return count === 1 ? "1 item" : `${String(count)} items`;
}

function useCart(tripId: string, open: boolean, sending: boolean) {
  return useQuery({
    queryKey: qk.cart(tripId),
    queryFn: async () =>
      unwrap(await api.GET("/api/trips/{trip_id}/cart", { params: { path: { trip_id: tripId } } })),
    enabled: open,
    // While items are going out, follow along (this phone's send, or another phone's).
    refetchInterval: (query) => (sending || query.state.data?.sending ? 1000 : false),
  });
}

function Group({
  title,
  lines,
  children,
}: {
  title: string;
  lines: CartLine[];
  children?: ReactNode;
}) {
  if (lines.length === 0) return null;
  return (
    <section aria-label={title} className="mb-5">
      <h3 className="mb-2 text-body font-bold">
        {title} ({String(lines.length)})
      </h3>
      {children}
      <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
        {lines.map((line) => (
          <li
            key={line.trip_item_id}
            className="flex min-h-14 items-center gap-3 border-b border-rule px-3 py-2 last:border-b-0"
          >
            <ProductImage src={line.image_url} alt="" size={48} />
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="text-body font-semibold">{line.name}</span>
              <span className="text-secondary text-ink-soft">{line.qty_text}</span>
              {line.status === "sending" ? (
                <span className="text-secondary text-ink-soft">Sending…</span>
              ) : null}
              {line.note ? (
                <span
                  className={`text-secondary ${
                    line.status === "failed" || line.status === "unknown"
                      ? "font-semibold text-tomato"
                      : "text-ink-soft"
                  }`}
                >
                  {line.note}
                </span>
              ) : null}
              {line.status === "added" && line.sent_at ? (
                <span className="text-secondary text-ink-soft">
                  {line.sent_by ? `Sent by ${line.sent_by}, ` : "Sent "}
                  {relativeTime(line.sent_at)}
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function NotConnected({ cart, onClose }: { cart: Cart; onClose: () => void }) {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col gap-4">
      <p className="text-body">
        {cart.account === "needs_reconnect"
          ? "Kroger signed Dinner Bell out. Reconnect Kroger in Settings, then send this list."
          : "Connect your Kroger account in Settings first. Then a saved list goes to your cart in one tap."}
      </p>
      <Button
        onClick={() => {
          onClose();
          void navigate({ to: "/settings" });
        }}
      >
        Go to Settings
      </Button>
    </div>
  );
}

export function SendToCartSheet({
  tripId,
  open,
  onClose,
}: {
  tripId: string;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [chosen, setChosen] = useState<Modality | undefined>(undefined);
  const send = useMutation({
    mutationFn: async (body: { item_ids: string[]; again: boolean; modality: Modality }) =>
      unwrap(
        await api.POST("/api/trips/{trip_id}/send-to-cart", {
          params: { path: { trip_id: tripId } },
          body,
        }),
      ),
    onMutate: () => {
      setMessage(null);
    },
    onSuccess: (result) => {
      queryClient.setQueryData(qk.cart(tripId), result.cart);
      setMessage(result.message);
    },
    onError: (failure) => {
      setMessage(errorMessage(failure));
      void queryClient.invalidateQueries({ queryKey: qk.cart(tripId) });
    },
  });
  const cart = useCart(tripId, open, send.isPending);
  const close = () => {
    setConfirming(false);
    setMessage(null);
    onClose();
  };

  const data = cart.data;
  const lines = data?.lines ?? [];
  const ready = lines.filter((line) => line.status === "ready");
  const sending = lines.filter((line) => line.status === "sending");
  const trouble = lines.filter((line) => line.status === "failed" || line.status === "unknown");
  const added = lines.filter((line) => line.status === "added");
  const cannot = lines.filter((line) => line.status === "cannot_send");
  const busy = send.isPending || Boolean(data?.sending);
  const sentBefore = added.length + trouble.length > 0;
  const modality = chosen ?? data?.modality ?? "PICKUP";
  const go = (lines: CartLine[], again: boolean) => {
    send.mutate({ item_ids: lines.map((line) => line.trip_item_id), again, modality });
  };
  // This phone's send knows its size; another phone's shows only what's left.
  const batch = send.isPending ? send.variables.item_ids.length : 0;
  const showBar = sending.length > 0 && batch >= sending.length;

  let footer: ReactNode = null;
  if (data?.account === "connected") {
    footer = (
      <div className="flex flex-col gap-2">
        {busy ? (
          <div className="flex flex-col gap-1" role="status">
            <span className="text-secondary font-semibold">
              {sending.length > 0
                ? `Sending to your Kroger cart: ${items(sending.length)} to go`
                : "Sending to your Kroger cart…"}
            </span>
            {showBar ? (
              <progress className="trip-progress" max={batch} value={batch - sending.length} />
            ) : null}
          </div>
        ) : null}
        {ready.length > 0 ? (
          <Button
            block
            disabled={busy}
            onClick={() => {
              go(ready, false);
            }}
          >
            {sentBefore ? `Send the other ${items(ready.length)}` : `Send ${items(ready.length)}`}
          </Button>
        ) : null}
        {trouble.length > 0 ? (
          <Button
            block
            variant="secondary"
            disabled={busy}
            onClick={() => {
              go(trouble, true);
            }}
          >
            Send these again
          </Button>
        ) : null}
        {ready.length === 0 && trouble.length === 0 && added.length > 0 ? (
          <Button
            variant="quiet"
            disabled={busy}
            onClick={() => {
              setConfirming(true);
            }}
          >
            Send again anyway
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <>
      <Sheet open={open && !confirming} title="Send to Kroger cart" onClose={close} footer={footer}>
        {!data ? (
          cart.isError ? (
            <p className="text-body">{errorMessage(cart.error)}</p>
          ) : (
            <p className="text-body text-ink-soft">Loading…</p>
          )
        ) : data.account !== "connected" ? (
          <NotConnected cart={data} onClose={close} />
        ) : (
          <>
            <p role="status" className="mb-4 text-body font-semibold empty:hidden">
              {message ??
                (ready.length === 0 && trouble.length === 0 && added.length > 0 && !busy
                  ? "Everything here is already in your Kroger cart."
                  : "")}
            </p>
            {ready.length > 0 && !sentBefore ? (
              <div className="mb-5 flex flex-col gap-3">
                <ModalityChoice
                  label="Pickup or delivery?"
                  value={modality}
                  disabled={busy}
                  onChange={setChosen}
                />
                <p className="text-secondary text-ink-soft">
                  Items go to the store chosen in your Kroger account. You’ll review and check out
                  in the Kroger app.
                </p>
              </div>
            ) : null}
            <Group title="Didn’t go" lines={trouble}>
              <p className="mb-2 text-secondary text-ink-soft">
                If Kroger didn’t answer, look in your Kroger cart before sending these again.
              </p>
            </Group>
            <Group title={sentBefore ? "Not sent yet" : "Going to your cart"} lines={ready} />
            <Group title="Sending" lines={sending} />
            <Group title="In your Kroger cart" lines={added} />
            <Group title="Add these in the Kroger app" lines={cannot} />
            {data.demo ? (
              <p className="text-secondary text-ink-soft">
                Sample mode: nothing reaches a real Kroger cart.
              </p>
            ) : null}
          </>
        )}
      </Sheet>
      <Sheet
        open={open && confirming}
        title="Send again?"
        onClose={() => {
          setConfirming(false);
        }}
        footer={
          <div className="flex flex-col gap-2">
            <Button
              block
              onClick={() => {
                setConfirming(false);
                go(added, true);
              }}
            >
              Send {items(added.length)} again
            </Button>
            <Button
              variant="quiet"
              onClick={() => {
                setConfirming(false);
              }}
            >
              Keep my cart as it is
            </Button>
          </div>
        }
      >
        <p className="text-body">
          These are already in your Kroger cart. Sending them again adds them again, and Dinner Bell
          can’t take them out: you’d remove extras in the Kroger app.
        </p>
      </Sheet>
    </>
  );
}
