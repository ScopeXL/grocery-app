import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { ToggleRow } from "./ToggleRow";

const SEARCH_SIDES_FROM = 6; // a search box once there are more sides than fit at a glance

/** Usual sides first, as large toggles, then every other side with a search. */
export function SidePicker({
  mainId,
  chosen,
  onChange,
  disabled = false,
  current = [],
}: {
  mainId: string;
  chosen: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  /** Sides already on the meal, so one archived since can still be taken off. */
  current?: { id: string; name: string }[];
}) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const usual = useQuery({
    queryKey: qk.usualSides(mainId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/dishes/{dish_id}/usual-sides", {
          params: { path: { dish_id: mainId } },
        }),
      ),
  });
  const all = useQuery({
    queryKey: qk.dishList("side", false),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes", { params: { query: { role: "side" } } })),
  });
  const toggle = (id: string) => {
    onChange(chosen.includes(id) ? chosen.filter((side) => side !== id) : [...chosen, id]);
  };
  const usualIds = new Set((usual.data ?? []).map((side) => side.id));
  const needle = query.trim().toLowerCase();
  const others = (all.data ?? []).filter(
    (card) => !usualIds.has(card.id) && (!needle || card.name.toLowerCase().includes(needle)),
  );
  const listed = new Set([...usualIds, ...(all.data ?? []).map((card) => card.id)]);
  const gone = all.data ? current.filter((side) => !listed.has(side.id)) : [];

  return (
    <>
      {gone.length > 0 ? (
        <div className="mb-5 flex flex-col gap-2">
          {gone.map((side) => (
            <ToggleRow
              key={side.id}
              on={chosen.includes(side.id)}
              disabled={disabled}
              label={side.name}
              onClick={() => {
                toggle(side.id);
              }}
            />
          ))}
        </div>
      ) : null}
      {usual.data && usual.data.length > 0 ? (
        <section className="mb-5">
          <h3 className="mb-2 text-body font-bold">Usual sides</h3>
          <div className="flex flex-col gap-2">
            {usual.data.map((side) => (
              <ToggleRow
                key={side.id}
                on={chosen.includes(side.id)}
                disabled={disabled}
                label={side.name}
                onClick={() => {
                  toggle(side.id);
                }}
              />
            ))}
          </div>
        </section>
      ) : null}
      {all.data?.length === 0 ? (
        <p className="text-secondary text-ink-soft">
          No sides yet. Add rice, a salad, anything you serve alongside, in Meals.
        </p>
      ) : (all.data?.length ?? 0) > usualIds.size ? (
        <section>
          <h3 className="mb-2 text-body font-bold">{usualIds.size > 0 ? "All sides" : "Sides"}</h3>
          {(all.data?.length ?? 0) > SEARCH_SIDES_FROM ? (
            <>
              <label htmlFor={searchId} className="sr-only">
                Search sides
              </label>
              <input
                id={searchId}
                type="search"
                value={query}
                placeholder="Search sides"
                onChange={(event) => {
                  setQuery(event.target.value);
                }}
                className="mb-3 min-h-12 w-full rounded-button border-2 border-rule bg-paper px-4 text-body"
              />
            </>
          ) : null}
          <div className="flex flex-col gap-2">
            {others.map((card) => (
              <ToggleRow
                key={card.id}
                on={chosen.includes(card.id)}
                disabled={disabled}
                label={card.name}
                onClick={() => {
                  toggle(card.id);
                }}
              />
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
