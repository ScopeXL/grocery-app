/**
 * Add an item to a meal (docs/UX.md §4.9): the household's own items first, then Kroger's
 * products at the chosen store, and "Add as plain text" when nothing fits. Product data is
 * shown exactly as Kroger returns it; photos only through ProductImage.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { cents } from "../../lib/money";
import { useDebounced } from "../../lib/useDebounced";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { Sheet } from "../../ui/Sheet";
import type { ItemOut, ProductResult } from "./types";

const MINE_SHOWN = 6;

function tidyName(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

function searchable(term: string): boolean {
  return term.replace(/\s/g, "").length >= 3;
}

export function AddItemSheet({
  open,
  onClose,
  onPicked,
  title = "Add an item",
}: {
  open: boolean;
  onClose: () => void;
  onPicked: (item: ItemOut) => void;
  title?: string;
}) {
  const queryClient = useQueryClient();
  const inputId = useId();
  const [text, setText] = useState("");
  const term = useDebounced(text.trim(), 300);

  const items = useQuery({
    queryKey: qk.items(),
    queryFn: async () => unwrap(await api.GET("/api/items")),
    enabled: open,
  });
  const results = useQuery({
    queryKey: qk.productSearch(term.toLowerCase()),
    queryFn: async () =>
      unwrap(await api.GET("/api/kroger/products", { params: { query: { q: term } } })),
    enabled: open && searchable(term),
    staleTime: 60_000,
    retry: false,
  });
  const create = useMutation({
    mutationFn: async (body: { name: string; product_id?: string }) =>
      unwrap(await api.POST("/api/items", { body })),
    onSuccess: (item) => {
      void queryClient.invalidateQueries({ queryKey: qk.items() });
      setText("");
      onPicked(item);
    },
  });

  const needle = text.trim().toLowerCase();
  const mine = (items.data ?? [])
    .filter((item) => !needle || item.name.toLowerCase().includes(needle))
    .slice(0, MINE_SHOWN);
  const found = results.data ?? [];

  return (
    <Sheet
      open={open}
      title={title}
      onClose={() => {
        setText("");
        onClose();
      }}
    >
      <label htmlFor={inputId} className="text-body font-semibold">
        What do you need?
      </label>
      <input
        id={inputId}
        value={text}
        autoComplete="off"
        enterKeyHint="search"
        placeholder="For example, cheddar"
        onChange={(event) => {
          setText(event.target.value.slice(0, 80));
        }}
        className="mt-2 mb-4 min-h-14 w-full rounded-button border-2 border-rule bg-paper px-4 text-body"
      />

      {mine.length > 0 ? (
        <section className="mb-5">
          <h3 className="mb-2 text-body font-bold">Items you already use</h3>
          <ul className="overflow-hidden rounded-tile border border-rule">
            {mine.map((item) => (
              <li key={item.id} className="border-b border-rule last:border-b-0">
                <button
                  type="button"
                  className="flex min-h-16 w-full items-center gap-3 px-3 py-2 text-left"
                  onClick={() => {
                    setText("");
                    onPicked(item);
                  }}
                >
                  <ProductImage src={item.image_url} alt="" size={48} />
                  <span className="flex flex-col">
                    <span className="text-body font-semibold">{item.name}</span>
                    {item.size_text ? (
                      <span className="text-secondary text-ink-soft">{item.size_text}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {searchable(term) ? (
        <section className="mb-5" aria-busy={results.isFetching}>
          <h3 className="mb-2 text-body font-bold">At your store</h3>
          {results.isError ? (
            <p className="text-secondary text-ink-soft">{errorMessage(results.error)}</p>
          ) : results.isPending ? (
            <p className="text-secondary text-ink-soft">Searching…</p>
          ) : found.length === 0 ? (
            <p className="text-body">
              Nothing at your store matches “{term}”. Try a shorter name, or add it as plain text.
            </p>
          ) : (
            <ul className="overflow-hidden rounded-tile border border-rule">
              {found.map((product) => (
                <li key={product.product_id} className="border-b border-rule last:border-b-0">
                  <button
                    type="button"
                    disabled={create.isPending}
                    className="flex min-h-20 w-full items-start gap-3 px-3 py-3 text-left disabled:opacity-60"
                    onClick={() => {
                      create.mutate({
                        name: tidyName(text || term),
                        product_id: product.product_id,
                      });
                    }}
                  >
                    <ProductImage src={product.image_url} alt="" size={64} />
                    <ProductFacts product={product} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : text.trim() ? (
        <p className="mb-5 text-secondary text-ink-soft">
          Type at least 3 letters to search your store.
        </p>
      ) : null}

      <p role="alert" className="min-h-7 text-secondary font-semibold text-tomato">
        {create.isError ? errorMessage(create.error) : null}
      </p>

      {text.trim() ? (
        <Button
          variant="secondary"
          block
          disabled={create.isPending}
          onClick={() => {
            create.mutate({ name: tidyName(text) });
          }}
        >
          Add “{tidyName(text)}” as plain text
        </Button>
      ) : null}
    </Sheet>
  );
}

/** Kroger's description, size and price, stacked (UX §2: no dot-joined meta lines). */
export function ProductFacts({ product }: { product: ProductResult }) {
  const price = product.price;
  const per = price?.per_pound ? "/lb" : "";
  return (
    <span className="flex min-w-0 flex-col gap-0.5">
      <span className="text-body font-semibold">{product.description}</span>
      {product.size ? <span className="text-secondary text-ink-soft">{product.size}</span> : null}
      {price ? (
        <span className="flex flex-wrap items-center gap-2 text-secondary">
          <span className="font-semibold">
            {cents(price.sale_cents ?? price.regular_cents)}
            {per}
          </span>
          {price.sale_cents !== null ? (
            <span className="rounded-full bg-lemon px-2 text-caption font-bold text-on-lemon">
              Sale
            </span>
          ) : null}
        </span>
      ) : (
        <span className="text-secondary text-ink-soft">No price</span>
      )}
      {price?.sale_ends ? (
        <span className="text-caption text-ink-soft">
          Sale ends{" "}
          {new Date(`${price.sale_ends}T12:00:00`).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })}
        </span>
      ) : null}
      {product.availability === "not_sold" ? (
        <span className="text-secondary text-tomato">Not sold at your store</span>
      ) : product.availability === "low" ? (
        <span className="text-secondary text-ink-soft">Low stock</span>
      ) : product.availability === "out" ? (
        <span className="text-secondary text-tomato">Out of stock</span>
      ) : null}
    </span>
  );
}
