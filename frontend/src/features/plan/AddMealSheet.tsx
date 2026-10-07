/**
 * Add a meal (UX §4.5): choose a Main (search; occasion chips with Dinner chosen; favorites
 * first), then an optional day (Sunday-to-Saturday pills) and its Sides (the usual ones first,
 * as large toggles, then all sides). The toast "Tacos added" offers Undo.
 */
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { costLine } from "../../lib/money";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";
import { ProductImage } from "../../ui/ProductImage";
import { Sheet } from "../../ui/Sheet";
import { OCCASIONS, type DishCard, type Occasion } from "../meals/types";
import { DayPicker } from "./MealChoices";
import { SidePicker } from "./SidePicker";
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
  /** Start at the sides step for this Main (from a meal's own page). */
  preset?: { id: string; name: string } | undefined;
}) {
  const [occasion, setOccasion] = useState<Occasion>("dinner");
  const [chosen, setChosen] = useState<{ id: string; name: string } | null>(null);
  const [sides, setSides] = useState<string[]>([]);
  const [day, setDay] = useState<string | null>(null);
  const main = chosen ?? preset ?? null;

  const reset = () => {
    setChosen(null);
    setSides([]);
    setDay(null);
    setOccasion("dinner");
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
            occasion,
            scale: "1",
          },
        }),
      );
    },
    (plan) => {
      const name = main?.name ?? "Meal";
      close();
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
      onClose={close}
      footer={
        main ? (
          <div className="flex gap-2">
            <Button
              variant="secondary"
              disabled={add.isPending}
              onClick={() => {
                add.mutate(false);
              }}
            >
              Skip sides
            </Button>
            <Button
              className="flex-1"
              disabled={add.isPending}
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
        <SidesStep
          mainId={main.id}
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
                }
          }
        />
      ) : (
        <MainStep
          open={open}
          occasion={occasion}
          onOccasion={setOccasion}
          onChoose={(card) => {
            setChosen({ id: card.id, name: card.name });
          }}
        />
      )}
    </Sheet>
  );
}

function MainStep({
  open,
  occasion,
  onOccasion,
  onChoose,
}: {
  open: boolean;
  occasion: Occasion;
  onOccasion: (value: Occasion) => void;
  onChoose: (card: DishCard) => void;
}) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const mains = useQuery({
    queryKey: qk.dishList("main", false),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes", { params: { query: { role: "main" } } })),
    enabled: open,
  });
  const needle = query.trim().toLowerCase();
  const all = mains.data ?? [];
  const shown = all.filter(
    (card) =>
      card.occasions.includes(occasion) && (!needle || card.name.toLowerCase().includes(needle)),
  );

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
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Occasion">
        {OCCASIONS.map((item) => (
          <Chip
            key={item.value}
            on={occasion === item.value}
            onClick={() => {
              onOccasion(item.value);
            }}
          >
            {item.label}
          </Chip>
        ))}
      </div>
      {mains.isError ? (
        <p className="text-body">{errorMessage(mains.error)}</p>
      ) : mains.isPending ? (
        <p className="text-secondary text-ink-soft">Loading…</p>
      ) : shown.length === 0 ? (
        <p className="text-body">
          {all.length === 0
            ? "No mains yet. Make one in Meals first."
            : "Nothing matches. Try another word or occasion."}
        </p>
      ) : (
        <ul className="overflow-hidden rounded-tile border border-rule">
          {shown.map((card) => (
            <li key={card.id} className="border-b border-rule last:border-b-0">
              <button
                type="button"
                className="flex min-h-16 w-full items-center gap-3 px-3 py-2 text-left"
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
                <span className="flex min-w-0 flex-col">
                  <span className="text-body font-semibold">{card.name}</span>
                  <span className="text-secondary text-ink-soft">{costLine(card.cost).total}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export function SidesStep({
  mainId,
  sides,
  onSides,
  day,
  onDay,
  today,
  onBack,
}: {
  mainId: string;
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
      <DayPicker day={day} today={today} onDay={onDay} />
      <SidePicker mainId={mainId} chosen={sides} onChange={onSides} />
    </>
  );
}
