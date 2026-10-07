/**
 * Add a meal (UX §4.5): choose a Main from every main (favorites first, a search on top), then
 * what it's for (starting with what it was last planned for, else dinner: ADR 0026), an optional
 * day (Sunday-to-Saturday pills) and its Sides (the usual ones first, then all sides). The toast
 * "Tacos added" offers Undo.
 */
import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { Sheet } from "../../ui/Sheet";
import { Skeleton } from "../../ui/Skeleton";
import type { DishCard } from "../meals/types";
import { DayPicker, OccasionPicker } from "./MealChoices";
import { MealPrice } from "./MealPrice";
import { SidePicker } from "./SidePicker";
import type { Occasion } from "./types";
import { usePlanChange } from "./usePlan";

export function AddMealSheet({
  open,
  today,
  onClose,
  preset,
}: {
  open: boolean;
  today: string;
  onClose: () => void;
  /** Start at the second step for this Main (from a meal's own page or the library pane). */
  preset?: MainChoice | undefined;
}) {
  const queryClient = useQueryClient();
  // null: the main's own default, until someone taps another occasion.
  const [occasion, setOccasion] = useState<Occasion | null>(null);
  const [chosen, setChosen] = useState<MainChoice | null>(null);
  const [sides, setSides] = useState<string[]>([]);
  const [day, setDay] = useState<string | null>(null);
  const main = chosen ?? preset ?? null;
  const mains = useQuery({
    queryKey: qk.dishList("main", false),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes", { params: { query: { role: "main" } } })),
    enabled: open,
  });
  // The freshest default wins: the list refetches when the sheet opens again after an add.
  const latest = main ? mains.data?.find((card) => card.id === main.id) : undefined;
  const shownOccasion = occasion ?? latest?.default_occasion ?? main?.defaultOccasion ?? "dinner";

  const reset = () => {
    setChosen(null);
    setSides([]);
    setDay(null);
    setOccasion(null);
  };
  const close = () => {
    reset();
    onClose();
  };

  const undo = usePlanChange(async (mealId: string) =>
    unwrap(
      await api.DELETE("/api/plan/meals/{meal_id}", { params: { path: { meal_id: mealId } } }),
    ),
  );
  const add = usePlanChange(
    async (withSides: boolean) => {
      if (!main) throw new Error("no main chosen");
      return unwrap(
        await api.POST("/api/plan/meals", {
          body: {
            main_id: main.id,
            side_ids: withSides ? sides : [],
            day,
            occasion: shownOccasion,
            scale: "1",
          },
        }),
      );
    },
    (plan) => {
      const name = main?.name ?? "Meal";
      close();
      // Its default occasion may have changed.
      void queryClient.invalidateQueries({ queryKey: qk.dishList("main", false) });
      const mealId = plan.changed;
      showToast(
        `${name} added`,
        mealId
          ? {
              label: "Undo",
              onAction: () => {
                undo.mutate(mealId);
              },
            }
          : undefined,
      );
    },
  );

  return (
    <Sheet
      open={open}
      title={main ? `Add ${main.name}` : "Add a meal"}
      step={main ? "details" : "main"}
      onClose={close}
      footer={
        main ? (
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={add.isPending}
              pending={add.isPending && !add.variables}
              onClick={() => {
                add.mutate(false);
              }}
            >
              Skip sides
            </Button>
            <Button
              className="flex-1"
              disabled={add.isPending}
              pending={add.isPending && add.variables}
              onClick={() => {
                add.mutate(true);
              }}
            >
              Add to plan
            </Button>
          </div>
        ) : undefined
      }
    >
      {main ? (
        <DetailsStep
          mainId={main.id}
          occasion={shownOccasion}
          onOccasion={setOccasion}
          sides={sides}
          onSides={setSides}
          day={day}
          onDay={setDay}
          today={today}
          onBack={
            preset
              ? undefined
              : () => {
                  setChosen(null);
                  setSides([]);
                  setOccasion(null);
                }
          }
        />
      ) : (
        <MainStep
          mains={mains}
          onChoose={(card) => {
            setChosen(mainChoice(card));
          }}
        />
      )}
    </Sheet>
  );
}

/** A main as Add a meal needs it: which one, and what it's usually planned for. */
export interface MainChoice {
  id: string;
  name: string;
  defaultOccasion: Occasion;
}

export function mainChoice(card: Pick<DishCard, "id" | "name" | "default_occasion">): MainChoice {
  return { id: card.id, name: card.name, defaultOccasion: card.default_occasion };
}

function MainStep({
  mains,
  onChoose,
}: {
  mains: UseQueryResult<DishCard[]>;
  onChoose: (card: DishCard) => void;
}) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const all = mains.data ?? [];
  const shown = needle ? all.filter((card) => card.name.toLowerCase().includes(needle)) : all;

  return (
    <>
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
      {mains.isError ? (
        <p className="text-body">{errorMessage(mains.error)}</p>
      ) : mains.isPending ? (
        <Skeleton rows={3} />
      ) : shown.length === 0 ? (
        <p className="text-body">
          {all.length === 0
            ? "No mains yet. Make one in Meals first."
            : `Nothing matches “${query.trim()}”. Try another word.`}
        </p>
      ) : (
        <ul className="overflow-hidden rounded-tile border border-rule">
          {shown.map((card) => (
            <li key={card.id} className="border-b border-rule last:border-b-0">
              <button
                type="button"
                className="press-row flex min-h-16 w-full items-center gap-3 px-3 py-2 text-left"
                onClick={() => {
                  onChoose(card);
                }}
              >
                {card.photo_url ? (
                  <img
                    src={card.photo_url}
                    alt=""
                    className="size-16 shrink-0 rounded-tile object-cover"
                  />
                ) : (
                  <ProductImage src={card.item_images[0] ?? null} alt="" size={64} />
                )}
                <span className="min-w-0 flex-1 text-body font-semibold">{card.name}</span>
                <MealPrice cost={card.cost} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function DetailsStep({
  mainId,
  occasion,
  onOccasion,
  sides,
  onSides,
  day,
  onDay,
  today,
  onBack,
}: {
  mainId: string;
  occasion: Occasion;
  onOccasion: (occasion: Occasion) => void;
  sides: string[];
  onSides: (ids: string[]) => void;
  day: string | null;
  onDay: (day: string | null) => void;
  today: string;
  onBack?: (() => void) | undefined;
}) {
  return (
    <>
      {onBack ? (
        <Button variant="quiet" className="mb-2 -ml-5" onClick={onBack}>
          Choose another main
        </Button>
      ) : null}
      <OccasionPicker occasion={occasion} onOccasion={onOccasion} />
      <DayPicker day={day} today={today} onDay={onDay} />
      <SidePicker mainId={mainId} chosen={sides} onChange={onSides} />
    </>
  );
}
