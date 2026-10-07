/**
 * Choose the household's store by ZIP code (docs/UX.md §4.3 step 1, §4.16 Store).
 * Fuel centers are already removed by the server. The location ID picks a store but is never
 * shown (UX §1).
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MapPin } from "lucide-react";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import type { components } from "../../api/schema";
import { Button } from "../../ui/Button";

type StoreOption = components["schemas"]["StoreOption"];
type StoreOut = components["schemas"]["StoreOut"];

export function ChooseStore({ onChosen }: { onChosen: (store: StoreOut) => void }) {
  const queryClient = useQueryClient();
  const zipId = useId();
  const [zip, setZip] = useState("");
  const [searched, setSearched] = useState<string | null>(null);

  const search = useMutation({
    mutationFn: async (value: string) =>
      unwrap(await api.GET("/api/stores/search", { params: { query: { zip: value } } })),
    onSuccess: (_stores, value) => {
      setSearched(value);
    },
  });

  const choose = useMutation({
    mutationFn: async (store: StoreOption) =>
      unwrap(await api.PUT("/api/stores/active", { body: { location_id: store.location_id } })),
    onSuccess: (store) => {
      queryClient.setQueryData(qk.activeStore(), { store });
      onChosen(store);
    },
  });

  const valid = /^\d{5}$/.test(zip);
  const stores = search.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) search.mutate(zip);
        }}
      >
        <label htmlFor={zipId} className="text-body font-semibold">
          Your ZIP code
        </label>
        <div className="flex gap-2">
          <input
            id={zipId}
            value={zip}
            inputMode="numeric"
            autoComplete="postal-code"
            maxLength={5}
            pattern="[0-9]*"
            placeholder="5 digits"
            onChange={(event) => {
              setZip(event.target.value.replace(/\D/g, "").slice(0, 5));
            }}
            className="min-h-12 w-36 rounded-button border-2 border-rule bg-paper px-4 text-row tracking-wider"
          />
          <Button type="submit" disabled={!valid || search.isPending}>
            {search.isPending ? "Finding…" : "Find stores"}
          </Button>
        </div>
      </form>

      <p role="alert" className="min-h-7 text-secondary font-semibold text-tomato">
        {search.isError ? errorMessage(search.error) : null}
        {choose.isError ? errorMessage(choose.error) : null}
      </p>

      {searched !== null && stores.length === 0 && !search.isPending ? (
        <p className="text-body">
          No stores near {searched}. Check the ZIP code, or try a nearby one.
        </p>
      ) : null}

      {stores.length > 0 ? (
        <ul
          className="overflow-hidden rounded-tile border border-rule bg-paper"
          aria-label="Stores"
        >
          {stores.map((store) => {
            const saving = choose.isPending && choose.variables.location_id === store.location_id;
            return (
              <li key={store.location_id} className="border-b border-rule last:border-b-0">
                <button
                  type="button"
                  disabled={choose.isPending}
                  onClick={() => {
                    choose.mutate(store);
                  }}
                  className="flex min-h-14 w-full items-start gap-3 px-4 py-3 text-left disabled:opacity-60"
                >
                  <MapPin aria-hidden="true" className="mt-1 size-6 shrink-0 text-accent" />
                  <span className="flex flex-col">
                    <span className="text-row font-semibold">{store.name}</span>
                    {store.address_lines.map((line) => (
                      <span key={line} className="text-secondary text-ink-soft">
                        {line}
                      </span>
                    ))}
                    {saving ? <span className="text-secondary text-accent">Saving…</span> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
