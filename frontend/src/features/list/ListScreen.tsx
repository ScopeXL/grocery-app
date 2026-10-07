/**
 * The shopping list (UX §4.11), built from this week's plan: the pantry check, the lines grouped
 * by aisle (the store's walking order) or by meal, then Extras with Usuals and Add something
 * else. Tapping a line opens its sheet. Printing gives every line in aisle order.
 */
import { Link, useNavigate } from "@tanstack/react-router";
import { Printer } from "lucide-react";
import { useState } from "react";

import { Button } from "../../ui/Button";
import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";
import { TotalFooter } from "../plan/TotalFooter";
import type { Line, PlanOut } from "../plan/types";
import { usePlan } from "../plan/usePlan";
import { ExtrasSection } from "./ExtrasSection";
import { LineRow } from "./LineRow";
import { LineSheet } from "./LineSheet";
import { PantryCheck } from "./PantryCheck";

type Grouping = "aisle" | "meal";
const GROUPING_KEY = "dinnerbell.list.grouping";

function savedGrouping(): Grouping {
  try {
    return localStorage.getItem(GROUPING_KEY) === "meal" ? "meal" : "aisle";
  } catch {
    return "aisle";
  }
}

function saveGrouping(value: Grouping): void {
  try {
    localStorage.setItem(GROUPING_KEY, value);
  } catch {
    // A private window may refuse storage; the choice just isn't remembered.
  }
}

export interface Group {
  key: string;
  label: string;
  lines: Line[];
}

/** Consecutive lines in the same section (lines arrive in walking order). */
export function byAisle(lines: Line[]): Group[] {
  const groups: Group[] = [];
  for (const line of lines) {
    const last = groups[groups.length - 1];
    if (last?.key === line.section.key) last.lines.push(line);
    else groups.push({ key: line.section.key, label: line.section.label, lines: [line] });
  }
  return groups;
}

/** Each line under the first meal on the plan that uses it ("for Tacos and Chili" says the rest). */
export function byMeal(plan: PlanOut, lines: Line[]): Group[] {
  const order = new Map(plan.meals.map((meal, index) => [meal.id, index]));
  const groups: Group[] = plan.meals.map((meal) => ({
    key: meal.id,
    label: meal.main.name,
    lines: [],
  }));
  for (const line of lines) {
    const first = Math.min(...line.used_by.map((use) => order.get(use.meal_id) ?? Infinity));
    groups[first]?.lines.push(line);
  }
  return groups.filter((group) => group.lines.length > 0);
}

export function isUnpriced(line: Line): boolean {
  return line.have_it !== true && (line.cost_cents === null || line.at_least);
}

export function ListScreen({ show }: { show?: "unpriced" | undefined }) {
  const plan = usePlan();
  const navigate = useNavigate();
  const [grouping, setGrouping] = useState<Grouping>(savedGrouping);
  const [openKey, setOpenKey] = useState<string | null>(null);

  if (!plan.data) {
    return (
      <Screen title="Shopping list">
        {plan.isError ? (
          <p className="text-body">Your list couldn't be loaded. Try again.</p>
        ) : null}
      </Screen>
    );
  }
  const data = plan.data;
  const shown = show === "unpriced" ? data.lines.filter(isUnpriced) : data.lines;
  const forMeals = shown.filter((line) => line.used_by.length > 0);
  const extras = shown.filter((line) => line.used_by.length === 0);
  const groups = grouping === "aisle" ? byAisle(forMeals) : byMeal(data, forMeals);
  const pantry = data.lines.filter((line) => line.staple && line.have_it === null);
  const open = data.lines.find((line) => line.key === openKey) ?? null;
  const empty = data.lines.length === 0 && data.meals.length === 0;

  return (
    <Screen
      title="Shopping list"
      actions={
        empty ? undefined : (
          <div className="flex w-full items-center gap-4">
            <TotalFooter plan={data} />
            {/* A wrapper, because Button's own inline-flex would beat "hidden" (CSS order). */}
            <div className="hidden lg:block">
              <Button
                variant="secondary"
                onClick={() => {
                  window.print();
                }}
              >
                <Printer aria-hidden="true" />
                Print
              </Button>
            </div>
          </div>
        )
      }
    >
      <div className="print:hidden">
        {empty ? (
          <EmptyState
            message="Your list fills in as you plan meals. You can also add things like milk."
            action={<Button onClick={() => void navigate({ to: "/" })}>Add a meal</Button>}
          />
        ) : (
          <>
            <div
              role="group"
              aria-label="Group the list"
              className="mb-5 grid grid-cols-2 rounded-button border-2 border-rule bg-paper p-1"
            >
              {(["aisle", "meal"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={grouping === value}
                  onClick={() => {
                    setGrouping(value);
                    saveGrouping(value);
                  }}
                  className="flex min-h-12 items-center justify-center rounded-button text-body font-semibold aria-pressed:bg-basil aria-pressed:text-on-basil"
                >
                  {value === "aisle" ? "By aisle" : "By meal"}
                </button>
              ))}
            </div>

            {show === "unpriced" ? (
              <div className="mb-5 flex flex-wrap items-center gap-3 rounded-tile bg-paper p-3">
                <p className="flex-1 text-body">Showing items with no price.</p>
                <Link to="/list" className="min-h-12 content-center font-semibold text-basil">
                  Show everything
                </Link>
              </div>
            ) : (
              <PantryCheck lines={pantry} />
            )}

            {groups.map((group) => (
              <section key={group.key} aria-label={group.label} className="mb-6">
                <h2 className="mb-2 text-row font-bold">{group.label}</h2>
                <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
                  {group.lines.map((line) => (
                    <LineRow key={line.key} line={line} onOpen={setOpenKey} />
                  ))}
                </ul>
              </section>
            ))}
          </>
        )}
        {show === "unpriced" && extras.length === 0 ? null : (
          <ExtrasSection plan={data} lines={extras} onOpen={setOpenKey} />
        )}
      </div>
      <PrintList lines={data.lines} />
      <LineSheet
        line={open}
        onClose={() => {
          setOpenKey(null);
        }}
      />
    </Screen>
  );
}

/** On paper: everything still to buy, in the store's walking order, with a box to tick. */
function PrintList({ lines }: { lines: Line[] }) {
  const toBuy = lines.filter((line) => line.have_it !== true && line.quantity !== "0");
  return (
    <div className="hidden print:block">
      {byAisle(toBuy).map((group) => (
        <section key={group.key} className="mb-4 break-inside-avoid">
          <h2 className="mb-1 text-body font-bold">{group.label}</h2>
          <ul>
            {group.lines.map((line) => (
              <li key={line.key} className="flex items-baseline gap-3 py-0.5 text-secondary">
                <span
                  aria-hidden="true"
                  className="inline-block size-4 shrink-0 border-2 border-ink"
                />
                <span className="font-semibold">{line.name}</span>
                <span>{line.amount_text}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
