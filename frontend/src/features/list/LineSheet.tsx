/**
 * A line's sheet (UX §4.11): change how many to buy (the server keeps the difference, so later
 * meals still add on top), Have it already, Swap product (for this trip, or always), Open in
 * Kroger, and the extras that feed the line.
 */
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Minus, Plus } from "lucide-react";
import { useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { add, parseFraction, toMixed, toText, type Fraction } from "../../lib/fraction";
import { about } from "../../lib/money";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { Sheet } from "../../ui/Sheet";
import { underlined } from "../../ui/styles";
import { ProductFacts } from "../meals/AddItemSheet";
import { RenameItem } from "../meals/RenameItem";
import type { Line } from "../plan/types";
import { usePlanChange, useRemoveExtra } from "../plan/usePlan";
import { usedByText } from "./LineRow";

const UNIT_WORDS: Record<Line["unit"], string> = { package: "", each: "", pound: " lb" };

export function mixed(text: string): string {
  const value = parseFraction(text);
  return value ? toMixed(value) : text;
}

export function LineSheet({ line, onClose }: { line: Line | null; onClose: () => void }) {
  const [swapping, setSwapping] = useState(false);
  const close = () => {
    setSwapping(false);
    onClose();
  };
  return (
    <Sheet open={line !== null} title={line?.name ?? "Item"} onClose={close}>
      {line ? (
        swapping && line.item_id ? (
          <Alternatives
            itemId={line.item_id}
            onDone={() => {
              setSwapping(false);
            }}
          />
        ) : (
          <LineDetails
            line={line}
            onSwap={() => {
              setSwapping(true);
            }}
          />
        )
      ) : null}
    </Sheet>
  );
}

function LineDetails({ line, onSwap }: { line: Line; onSwap: () => void }) {
  const itemId = line.item_id;
  const change = usePlanChange(
    async (body: { have_it?: boolean | null; quantity?: string | null; unit?: Line["unit"] }) => {
      if (!itemId) throw new Error("not an item");
      return unwrap(
        await api.PUT("/api/plan/items/{item_id}", {
          params: { path: { item_id: itemId } },
          body: { ...body, always: false },
        }),
      );
    },
  );
  const setExtra = usePlanChange(async ({ id, quantity }: { id: string; quantity: string }) =>
    unwrap(
      await api.PATCH("/api/plan/extras/{extra_id}", {
        params: { path: { extra_id: id } },
        body: { quantity },
      }),
    ),
  );
  const undoSwap = usePlanChange(async () => {
    if (!itemId) throw new Error("not an item");
    return unwrap(
      await api.PUT("/api/plan/items/{item_id}", {
        params: { path: { item_id: itemId } },
        body: { swap_product_id: null, always: false },
      }),
    );
  });
  const removeExtra = useRemoveExtra();
  const usedBy = usedByText(line);
  const textExtra = itemId === null ? line.extras[0] : undefined;
  const step: Fraction = line.unit === "pound" ? { n: 1, d: 4 } : { n: 1, d: 1 };
  const quantity = parseFraction(line.quantity) ?? { n: 0, d: 1 };
  const minimum = textExtra ? step : { n: 0, d: 1 };

  const setQuantity = (next: Fraction) => {
    if (next.n * minimum.d < minimum.n * next.d) return;
    if (textExtra) {
      setExtra.mutate({ id: textExtra.id, quantity: toText(next) });
    } else {
      change.mutate({ quantity: toText(next), unit: line.unit });
    }
  };
  const busy = change.isPending || setExtra.isPending || undoSwap.isPending;

  return (
    <>
      <div className="mb-5 grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-3">
        <ProductImage src={line.image_url} alt="" size={96} />
        <div className="flex flex-col gap-0.5">
          <span className="text-body">{line.amount_text}</span>
          {line.cost_cents !== null ? (
            <span className="text-body font-semibold">{about(line.cost_cents)}</span>
          ) : null}
          {line.sale ? (
            <span className="text-secondary">
              <span className="rounded-full bg-lemon px-2 text-caption font-bold text-on-lemon">
                Sale
              </span>{" "}
              {line.sale.ends
                ? `ends ${new Date(`${line.sale.ends}T12:00:00`).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                  })}`
                : null}
            </span>
          ) : null}
          {usedBy ? <span className="text-secondary text-ink-soft">{usedBy}</span> : null}
          {line.swapped ? (
            <span className="text-secondary text-ink-soft">A different product, for this trip</span>
          ) : null}
          {line.warnings.map((warning) => (
            <span key={warning} className="text-secondary font-semibold text-tomato">
              {warning}
            </span>
          ))}
        </div>
        {itemId ? <RenameItem itemId={itemId} name={line.name} /> : null}
      </div>

      <h3 className="mb-2 text-body font-bold">How many to buy</h3>
      <div className="mb-2 flex items-center gap-3">
        <Button
          variant="secondary"
          aria-label="One less"
          disabled={busy || quantity.n * minimum.d <= minimum.n * quantity.d}
          onClick={() => {
            setQuantity(add(quantity, { n: -step.n, d: step.d }));
          }}
        >
          <Minus aria-hidden="true" />
        </Button>
        <span className="min-w-24 text-center text-row font-bold" aria-live="polite">
          {line.quantity_text}
        </span>
        <Button
          variant="secondary"
          aria-label="One more"
          disabled={busy}
          onClick={() => {
            setQuantity(add(quantity, step));
          }}
        >
          <Plus aria-hidden="true" />
        </Button>
      </div>
      {itemId && line.quantity !== line.computed ? (
        <p className="mb-2 text-secondary text-ink-soft">
          The list works out {mixed(line.computed)}
          {UNIT_WORDS[line.unit]}.{" "}
          <Button
            variant="quiet"
            className="px-0"
            disabled={busy}
            onClick={() => {
              change.mutate({ quantity: null });
            }}
          >
            Use {mixed(line.computed)}
          </Button>
        </p>
      ) : null}

      {line.extras.length > 0 ? (
        <section className="mt-4">
          <h3 className="mb-2 text-body font-bold">Added outside meals</h3>
          <ul className="overflow-hidden rounded-tile border border-rule">
            {line.extras.map((extra) => (
              <li
                key={extra.id}
                className="flex items-center gap-3 border-b border-rule px-3 py-2 last:border-b-0"
              >
                <span className="flex-1 text-body">
                  {extra.added_by ? `${extra.added_by.name} added ` : "Added "}
                  {mixed(extra.quantity)}
                  {UNIT_WORDS[line.unit]}
                </span>
                <Button
                  variant="quiet-danger"
                  disabled={removeExtra.isPending}
                  onClick={() => {
                    removeExtra.mutate({ id: extra.id, name: line.name });
                  }}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {itemId ? (
        <div className="mt-6 flex flex-col gap-2">
          <Button
            variant="secondary"
            block
            disabled={busy}
            onClick={() => {
              change.mutate({ have_it: line.have_it !== true });
            }}
          >
            {line.have_it === true ? "Need it after all" : "Have it already"}
          </Button>
          <Button variant="secondary" block onClick={onSwap}>
            {line.flags.includes("no_product") ? "Choose a product" : "Swap product"}
          </Button>
          {line.swapped ? (
            <Button
              variant="quiet"
              block
              disabled={busy}
              onClick={() => {
                undoSwap.mutate(undefined);
              }}
            >
              Back to the usual product
            </Button>
          ) : null}
          {line.product_url ? (
            <a
              href={line.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className={`inline-flex min-h-11 items-center justify-center gap-2 text-body font-semibold text-accent ${underlined}`}
            >
              Open in Kroger
              <ExternalLink aria-hidden="true" className="size-5" />
            </a>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

/** Other products, each with its price per ounce (or pound, or piece) to compare. */
function Alternatives({ itemId, onDone }: { itemId: string; onDone: () => void }) {
  const found = useQuery({
    queryKey: qk.alternatives(itemId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/plan/items/{item_id}/alternatives", {
          params: { path: { item_id: itemId } },
        }),
      ),
    staleTime: 60_000,
    retry: false,
  });
  const swap = usePlanChange(
    async ({ productId, always }: { productId: string | null; always: boolean }) =>
      unwrap(
        await api.PUT("/api/plan/items/{item_id}", {
          params: { path: { item_id: itemId } },
          body: { swap_product_id: productId, always },
        }),
      ),
    onDone,
  );
  const options = found.data?.alternatives ?? [];
  return (
    <>
      <Button variant="quiet" className="mb-2 -ml-5" onClick={onDone}>
        Back
      </Button>
      {found.isError ? (
        <p className="text-body">{errorMessage(found.error)}</p>
      ) : found.isPending ? (
        <p className="text-secondary text-ink-soft">Looking at your store…</p>
      ) : (
        <ul className="overflow-hidden rounded-tile border border-rule">
          {options.map((option) => (
            <li
              key={option.product.product_id}
              className="flex flex-col gap-2 border-b border-rule px-3 py-3 last:border-b-0"
            >
              <div className="flex items-start gap-3">
                <ProductImage src={option.product.image_url} alt="" size={64} />
                <span className="flex min-w-0 flex-col">
                  <ProductFacts product={option.product} />
                  {option.unit_price_text ? (
                    <span className="text-secondary font-semibold">{option.unit_price_text}</span>
                  ) : null}
                </span>
              </div>
              {option.current ? (
                <span className="text-secondary font-semibold text-accent">On your list now</span>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    disabled={swap.isPending}
                    onClick={() => {
                      swap.mutate({ productId: option.product.product_id, always: false });
                    }}
                  >
                    For this trip
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={swap.isPending}
                    onClick={() => {
                      swap.mutate({ productId: option.product.product_id, always: true });
                    }}
                  >
                    Always use this
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
