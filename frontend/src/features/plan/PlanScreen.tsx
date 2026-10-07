/**
 * This week (UX §4.4): the Tonight card, each planned meal with its sides, day and scale and a
 * Change button, Add a meal, and the sticky total. At 1440 px the library and the list sit on
 * either side (PlanDesktop).
 */
import { Link } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useState, type ReactNode } from "react";

import { api, unwrap } from "../../api/client";
import { dayLabel } from "../../lib/days";
import { costLine } from "../../lib/money";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";
import { AddMealSheet, mainChoice, type MainChoice } from "./AddMealSheet";
import { ChangeMealSheet } from "./ChangeMealSheet";
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
        ) : null}
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
    <span className="inline-flex min-h-7 items-center rounded-full border-2 border-rule px-3 text-caption font-bold">
      {children}
    </span>
  );
}

function mealTags(meal: PlannedMeal, today: string, withDay: boolean): ReactNode[] {
  const tags: ReactNode[] = [];
  if (withDay && meal.day) tags.push(<Tag key="day">{dayLabel(meal.day, today)}</Tag>);
  if (meal.scale !== "1") tags.push(<Tag key="scale">{scaleLabel(meal.scale)}</Tag>);
  if (meal.occasion !== "dinner") {
    tags.push(<Tag key="occasion">{occasionLabel(meal.occasion)}</Tag>);
  }
  return tags;
}

function TonightCard({
  meal,
  onChange,
}: {
  meal: PlannedMeal;
  onChange: (mealId: string) => void;
}) {
  const tags = mealTags(meal, "", false);
  return (
    <section
      aria-label={meal.occasion === "dinner" ? "Tonight" : "Today"}
      className="mb-5 overflow-hidden rounded-tile border border-rule bg-paper"
    >
      <MealPicture dish={meal.main} />
      <div className="flex flex-wrap items-end gap-3 p-4">
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-secondary font-bold text-accent">
            {meal.occasion === "dinner"
              ? "Tonight"
              : `Today's ${occasionLabel(meal.occasion).toLowerCase()}`}
          </span>
          <Link
            to="/meals/$dishId"
            params={{ dishId: meal.main.id }}
            className="inline-flex min-h-10 items-center text-title font-extrabold"
          >
            {meal.main.name}
          </Link>
          {meal.sides.length > 0 ? (
            <span className="text-body text-ink-soft">
              with {joinNames(meal.sides.map((side) => side.name))}
            </span>
          ) : null}
          <span className="text-secondary text-ink-soft">{costLine(meal.cost).total}</span>
          {tags.length > 0 ? <span className="mt-2 flex flex-wrap gap-2">{tags}</span> : null}
        </div>
        <Button
          variant="secondary"
          aria-label={`Change ${meal.main.name}`}
          onClick={() => {
            onChange(meal.id);
          }}
        >
          Change
        </Button>
      </div>
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
  const tags = mealTags(meal, today, true);
  return (
    <li className="flex items-center gap-3 border-b border-rule px-3 py-3 last:border-b-0">
      <MealThumb dish={meal.main} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Link
          to="/meals/$dishId"
          params={{ dishId: meal.main.id }}
          className="inline-flex min-h-10 items-center text-row leading-tight font-bold"
        >
          {meal.main.name}
        </Link>
        {meal.sides.length > 0 ? (
          <span className="text-secondary text-ink-soft">
            with {joinNames(meal.sides.map((side) => side.name))}
          </span>
        ) : null}
        <span className="text-secondary text-ink-soft">{costLine(meal.cost).total}</span>
        {tags.length > 0 ? <span className="mt-1 flex flex-wrap gap-2">{tags}</span> : null}
      </div>
      <Button
        variant="secondary"
        aria-label={`Change ${meal.main.name}`}
        onClick={() => {
          onChange(meal.id);
        }}
      >
        Change
      </Button>
    </li>
  );
}
