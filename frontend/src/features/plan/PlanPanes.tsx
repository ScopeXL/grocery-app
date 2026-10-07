/**
 * The Plan screen's side panes at 1440 px (UX §3): the meal library on the left, to add from,
 * and the list it builds on the right, in walking order. Phones get the same things from the
 * Add a meal sheet and the List tab.
 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { about } from "../../lib/money";
import { Button } from "../../ui/Button";
import { underlined } from "../../ui/styles";
import { byAisle } from "../list/ListScreen";
import type { DishCard } from "../meals/types";
import { MealPrice } from "./MealPrice";
import type { PlanOut } from "./types";

export function LibraryPane({ onAdd }: { onAdd: (main: DishCard) => void }) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const mains = useQuery({
    queryKey: qk.dishList("main", false),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes", { params: { query: { role: "main" } } })),
  });
  const needle = query.trim().toLowerCase();
  const shown = (mains.data ?? []).filter(
    (card) => !needle || card.name.toLowerCase().includes(needle),
  );
  return (
    <section aria-label="Meal library" className="flex flex-col gap-3">
      <h2 className="text-row font-bold">Your meals</h2>
      <label htmlFor={searchId} className="sr-only">
        Search mains
      </label>
      <input
        id={searchId}
        type="search"
        value={query}
        placeholder="Search mains"
        onChange={(event) => {
          setQuery(event.target.value);
        }}
        className="min-h-12 w-full rounded-button border-2 border-rule bg-paper px-4 text-body"
      />
      {mains.isError ? (
        <p className="text-secondary">{errorMessage(mains.error)}</p>
      ) : (
        <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
          {shown.map((card) => (
            <li
              key={card.id}
              className="flex items-center gap-2 border-b border-rule py-2 pr-2 pl-3 last:border-b-0"
            >
              <Link
                to="/meals/$dishId"
                params={{ dishId: card.id }}
                className="press-row flex min-h-11 min-w-0 flex-1 flex-col justify-center"
              >
                <span className="text-body leading-tight font-semibold">{card.name}</span>
              </Link>
              <MealPrice cost={card.cost} />
              <Button
                variant="secondary"
                aria-label={`Add ${card.name} to this week`}
                onClick={() => {
                  onAdd(card);
                }}
              >
                Add
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ListPane({ plan }: { plan: PlanOut }) {
  const toBuy = plan.lines.filter((line) => line.have_it !== true);
  return (
    <section aria-label="List summary" className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-row font-bold">The list</h2>
        <Link
          to="/list"
          className={`min-h-11 content-center font-semibold text-accent ${underlined}`}
        >
          Open the list
        </Link>
      </div>
      {toBuy.length === 0 ? (
        <p className="text-secondary text-ink-soft">It fills in as you plan meals.</p>
      ) : (
        byAisle(toBuy).map((group) => (
          <div key={group.key}>
            <h3 className="mb-1 text-secondary font-bold">{group.label}</h3>
            <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
              {group.lines.map((line) => (
                <li
                  key={line.key}
                  className="flex items-baseline gap-2 border-b border-rule px-3 py-2 text-secondary last:border-b-0"
                >
                  <span className="min-w-0 flex-1">
                    <span className="font-semibold">{line.name}</span>{" "}
                    <span className="text-ink-soft">{line.quantity_text}</span>
                  </span>
                  <span className="shrink-0">
                    {line.cost_cents !== null ? about(line.cost_cents) : "no price"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
