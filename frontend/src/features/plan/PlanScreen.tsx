/**
 * This week (UX §4.4): the Tonight card and each planned meal, with its sides, price (in the
 * corner) and tags. Tapping a meal opens Change. Then Add a meal and the sticky total. At
 * 1440 px the library and the list sit on either side (PlanDesktop).
 */
import { Pencil, Plus } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { api, unwrap } from "../../api/client";
import { dayLabel } from "../../lib/days";
import { mealPrice } from "../../lib/money";
import { arrivals } from "../../lib/motion";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";
import { Skeleton } from "../../ui/Skeleton";
import { AddMealSheet, mainChoice, type MainChoice } from "./AddMealSheet";
import { ChangeMealSheet } from "./ChangeMealSheet";
import { MealPrice } from "./MealPrice";
import { MealPicture, MealThumb } from "./MealThumb";
import { Suggestions } from "./Suggestions";
import { LibraryPane, ListPane } from "./PlanPanes";
import { TotalFooter } from "./TotalFooter";
import { joinNames, occasionLabel, scaleLabel, type PlannedMeal } from "./types";
import { usePlan, usePlanChange } from "./usePlan";

export function PlanScreen() {
  const plan = usePlan();
  const [adding, setAdding] = useState(false);
  const [preset, setPreset] = useState<MainChoice | undefined>(undefined);
  const [changingId, setChangingId] = useState<string | null>(null);

  const undoNewWeek = usePlanChange(async (planId: string) =>
    unwrap(await api.POST("/api/plan/new-week/undo", { body: { plan_id: planId } })),
  );
  const newWeek = usePlanChange(
    async () => unwrap(await api.POST("/api/plan/new-week")),
    (fresh) => {
      const archived = fresh.changed;
      showToast(
        "New week started",
        archived
          ? {
              label: "Undo",
              onAction: () => {
                undoNewWeek.mutate(archived);
              },
            }
          : undefined,
      );
    },
  );

  if (!plan.data) {
    return (
      <Screen title="This week">
        {plan.isError ? (
          <p className="text-body">Your plan couldn't be loaded. Try again.</p>
        ) : (
          <Skeleton rows={4} />
        )}
      </Screen>
    );
  }
  const data = plan.data;
  const today = data.today;
  const tonight =
    data.meals.find((meal) => meal.day === today && meal.occasion === "dinner") ??
    data.meals.find((meal) => meal.day === today);
  const rest = data.meals.filter((meal) => meal !== tonight);
  const hasAnything = data.meals.length > 0 || data.extras.length > 0;
  const changing = data.meals.find((meal) => meal.id === changingId) ?? null;
  const openAdd = () => {
    setPreset(undefined);
    setAdding(true);
  };

  return (
    <Screen title="This week" wide actions={hasAnything ? <TotalFooter plan={data} /> : undefined}>
      <div className="xl:grid xl:grid-cols-[17rem_minmax(0,1fr)_20rem] xl:items-start xl:gap-8">
        <aside className="hidden xl:block">
          <LibraryPane
            onAdd={(main) => {
              setPreset(mainChoice(main));
              setAdding(true);
            }}
          />
        </aside>
        <div>
          {data.meals.length === 0 ? (
            <EmptyState
              message="No meals planned yet. Add a dinner and the shopping list builds itself."
              action={<Button onClick={openAdd}>Add a meal</Button>}
            />
          ) : (
            <>
              {tonight ? <TonightCard meal={tonight} onChange={setChangingId} /> : null}
              {rest.length > 0 ? (
                <ul
                  ref={arrivals}
                  aria-label="This week's meals"
                  className="overflow-hidden rounded-tile border border-rule bg-paper"
                >
                  {rest.map((meal) => (
                    <MealRow key={meal.id} meal={meal} today={today} onChange={setChangingId} />
                  ))}
                </ul>
              ) : null}
              <Suggestions />
              <Button block className="mt-5" onClick={openAdd}>
                <Plus aria-hidden="true" />
                Add a meal
              </Button>
            </>
          )}
          {hasAnything ? (
            <div className="mt-8">
              <Button
                variant="quiet"
                className="-ml-5"
                disabled={newWeek.isPending}
                onClick={() => {
                  newWeek.mutate(undefined);
                }}
              >
                Start a new week
              </Button>
            </div>
          ) : null}
        </div>
        <aside className="hidden xl:block">
          <ListPane plan={data} />
        </aside>
      </div>
      <AddMealSheet
        open={adding}
        today={today}
        preset={preset}
        onClose={() => {
          setAdding(false);
          setPreset(undefined);
        }}
      />
      <ChangeMealSheet
        meal={changing}
        today={today}
        onClose={() => {
          setChangingId(null);
        }}
      />
    </Screen>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex min-h-6 items-center rounded-full border-2 border-rule px-2.5 text-caption font-bold">
      {children}
    </span>
  );
}

function tagTexts(meal: PlannedMeal, today: string, withDay: boolean): string[] {
  const tags: string[] = [];
  if (withDay && meal.day) tags.push(dayLabel(meal.day, today));
  if (meal.scale !== "1") tags.push(scaleLabel(meal.scale));
  if (meal.occasion !== "dinner") tags.push(occasionLabel(meal.occasion));
  return tags;
}

/** What a screen reader hears after "Change Tacos": the sides, the price, the tags. */
function describe(meal: PlannedMeal, tags: string[]): string {
  const sides = meal.sides.length ? `with ${joinNames(meal.sides.map((side) => side.name))}` : "";
  const price = mealPrice(meal.cost)?.spoken ?? "no price yet";
  return [sides, price, ...tags].filter(Boolean).join(", ");
}

/**
 * The button that opens Change: it's the meal's name, and its ::after covers the whole card, so
 * a tap anywhere on the card opens it (the List's rows work the same way). The card shows the
 * press, and the focus ring outlines the whole card.
 */
const STRETCHED =
  "text-left after:absolute after:inset-0 after:rounded-tile after:content-[''] focus-visible:outline-none focus-visible:after:outline-3 focus-visible:after:outline-offset-2 focus-visible:after:outline-(--focus-ring)";

function TonightCard({
  meal,
  onChange,
}: {
  meal: PlannedMeal;
  onChange: (mealId: string) => void;
}) {
  const descriptionId = useId();
  const tags = tagTexts(meal, "", false);
  return (
    <section
      aria-label={meal.occasion === "dinner" ? "Tonight" : "Today"}
      className="relative mb-5 overflow-hidden rounded-tile border border-rule bg-paper transition-colors duration-(--motion-tap) has-[button:active]:bg-counter"
    >
      <MealPicture dish={meal.main} />
      <div className="flex items-start gap-3 p-4">
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-secondary font-bold text-ink-soft">
            {meal.occasion === "dinner"
              ? "Tonight"
              : `Today's ${occasionLabel(meal.occasion).toLowerCase()}`}
          </span>
          <button
            type="button"
            data-stretched=""
            aria-label={`Change ${meal.main.name}`}
            aria-describedby={descriptionId}
            className={`${STRETCHED} text-title font-extrabold`}
            onClick={() => {
              onChange(meal.id);
            }}
          >
            {meal.main.name}
          </button>
          {meal.sides.length > 0 ? (
            <span className="text-body text-ink-soft">
              with {joinNames(meal.sides.map((side) => side.name))}
            </span>
          ) : null}
          {meal.cost.about_dollars === null ? (
            <span className="text-secondary text-ink-soft">No price yet</span>
          ) : null}
          {tags.length > 0 ? (
            <span className="mt-2 flex flex-wrap gap-1.5">
              {tags.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </span>
          ) : null}
        </div>
        <div className="flex flex-col items-end gap-3 self-stretch">
          <MealPrice cost={meal.cost} />
          <Pencil aria-hidden="true" className="mt-auto size-5 text-ink-soft" />
        </div>
      </div>
      <span id={descriptionId} className="sr-only">
        {describe(meal, tags)}
      </span>
    </section>
  );
}

function MealRow({
  meal,
  today,
  onChange,
}: {
  meal: PlannedMeal;
  today: string;
  onChange: (mealId: string) => void;
}) {
  const descriptionId = useId();
  const tags = tagTexts(meal, today, true);
  return (
    <li className="relative flex items-center gap-3 border-b border-rule px-3 py-3 transition-colors duration-(--motion-tap) last:border-b-0 has-[button:active]:bg-counter">
      <MealThumb dish={meal.main} />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-3">
          <button
            type="button"
            data-stretched=""
            aria-label={`Change ${meal.main.name}`}
            aria-describedby={descriptionId}
            className={`${STRETCHED} text-row leading-tight font-bold`}
            onClick={() => {
              onChange(meal.id);
            }}
          >
            {meal.main.name}
          </button>
          <MealPrice cost={meal.cost} />
        </div>
        {meal.sides.length > 0 ? (
          <span className="text-secondary text-ink-soft">
            with {joinNames(meal.sides.map((side) => side.name))}
          </span>
        ) : null}
        {meal.cost.about_dollars === null ? (
          <span className="text-secondary text-ink-soft">No price yet</span>
        ) : null}
        <div className="mt-1 flex items-end justify-between gap-3">
          <span className="flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </span>
          <Pencil aria-hidden="true" className="size-4 shrink-0 text-ink-soft" />
        </div>
      </div>
      <span id={descriptionId} className="sr-only">
        {describe(meal, tags)}
      </span>
    </li>
  );
}
