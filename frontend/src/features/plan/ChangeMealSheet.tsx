/**
 * Change a planned meal (UX §4.4): how much (×½, ×1, ×2), the day, the occasion, its sides,
 * swap the main, or remove it (with Undo). Each tap saves at once; the list follows.
 */
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";
import { Sheet } from "../../ui/Sheet";
import { OCCASIONS } from "../meals/types";
import { DayPicker } from "./MealChoices";
import { SidePicker } from "./SidePicker";
import { SCALES, type PlannedMeal } from "./types";
import { usePlanChange, useRemoveMeal } from "./usePlan";

interface MealChange {
  main_id?: string;
  day?: string | null;
  occasion?: PlannedMeal["occasion"];
  scale?: PlannedMeal["scale"];
}

export function ChangeMealSheet({
  meal,
  today,
  onClose,
}: {
  meal: PlannedMeal | null;
  today: string;
  onClose: () => void;
}) {
  const [swapping, setSwapping] = useState(false);
  const close = () => {
    setSwapping(false);
    onClose();
  };
  const update = usePlanChange(async ({ id, body }: { id: string; body: MealChange }) =>
    unwrap(
      await api.PATCH("/api/plan/meals/{meal_id}", { params: { path: { meal_id: id } }, body }),
    ),
  );
  const setSides = usePlanChange(async ({ id, sides }: { id: string; sides: string[] }) =>
    unwrap(
      await api.PUT("/api/plan/meals/{meal_id}/sides", {
        params: { path: { meal_id: id } },
        body: { side_ids: sides },
      }),
    ),
  );
  const remove = useRemoveMeal();
  const busy = update.isPending || setSides.isPending;

  return (
    <Sheet
      open={meal !== null}
      title={meal ? `Change ${meal.main.name}` : "Change"}
      onClose={close}
    >
      {meal ? (
        swapping ? (
          <SwapMain
            current={meal.main.id}
            onPick={(mainId) => {
              update.mutate({ id: meal.id, body: { main_id: mainId } });
              setSwapping(false);
            }}
            onBack={() => {
              setSwapping(false);
            }}
          />
        ) : (
          <>
            <h3 className="mb-2 text-body font-bold">How much</h3>
            <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="How much">
              {SCALES.map((scale) => (
                <Chip
                  key={scale.value}
                  on={meal.scale === scale.value}
                  disabled={busy}
                  onClick={() => {
                    update.mutate({ id: meal.id, body: { scale: scale.value } });
                  }}
                >
                  {scale.label}
                </Chip>
              ))}
            </div>

            <DayPicker
              day={meal.day}
              today={today}
              disabled={busy}
              onDay={(day) => {
                update.mutate({ id: meal.id, body: { day } });
              }}
            />

            <h3 className="mb-2 text-body font-bold">Occasion</h3>
            <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Occasion">
              {OCCASIONS.map((occasion) => (
                <Chip
                  key={occasion.value}
                  on={meal.occasion === occasion.value}
                  disabled={busy}
                  onClick={() => {
                    update.mutate({ id: meal.id, body: { occasion: occasion.value } });
                  }}
                >
                  {occasion.label}
                </Chip>
              ))}
            </div>

            <SidePicker
              mainId={meal.main.id}
              chosen={meal.sides.map((side) => side.id)}
              current={meal.sides}
              disabled={busy}
              onChange={(sides) => {
                setSides.mutate({ id: meal.id, sides });
              }}
            />

            <div className="mt-6 flex flex-col items-start gap-1 border-t border-rule pt-4">
              <Button
                variant="quiet"
                className="-ml-5"
                onClick={() => {
                  setSwapping(true);
                }}
              >
                Swap {meal.main.name} for another main
              </Button>
              <Button
                variant="quiet-danger"
                className="-ml-5"
                disabled={remove.isPending}
                onClick={() => {
                  remove.mutate({ id: meal.id, name: meal.main.name });
                  close();
                }}
              >
                Remove from this week
              </Button>
            </div>
          </>
        )
      ) : null}
    </Sheet>
  );
}

function SwapMain({
  current,
  onPick,
  onBack,
}: {
  current: string;
  onPick: (mainId: string) => void;
  onBack: () => void;
}) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const mains = useQuery({
    queryKey: qk.dishList("main", false),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes", { params: { query: { role: "main" } } })),
  });
  const needle = query.trim().toLowerCase();
  const shown = (mains.data ?? []).filter(
    (card) => card.id !== current && (!needle || card.name.toLowerCase().includes(needle)),
  );
  return (
    <>
      <Button variant="quiet" className="mb-2 -ml-5" onClick={onBack}>
        Back
      </Button>
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
        className="mb-3 min-h-12 w-full rounded-button border-2 border-rule bg-paper px-4 text-body"
      />
      <ul className="overflow-hidden rounded-tile border border-rule">
        {shown.map((card) => (
          <li key={card.id} className="border-b border-rule last:border-b-0">
            <button
              type="button"
              className="flex min-h-14 w-full items-center px-4 text-left text-body font-semibold"
              onClick={() => {
                onPick(card.id);
              }}
            >
              {card.name}
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
