/**
 * First run (docs/UX.md §4.3): choose the store, add a first dinner, done. Three steps, and
 * the second can be skipped.
 */
import { useNavigate } from "@tanstack/react-router";

import { BellMark } from "../../ui/BellMark";
import { Button } from "../../ui/Button";
import { ChooseStore } from "../stores/ChooseStore";

export type FirstRunStep = "store" | "dinner" | "done";

export function FirstRunScreen({ step }: { step: FirstRunStep }) {
  const navigate = useNavigate();
  const number = { store: 1, dinner: 2, done: 3 }[step];
  return (
    <main className="mx-auto w-full max-w-md px-4 pt-[calc(env(safe-area-inset-top)+32px)] pb-12">
      <BellMark className="mb-4 size-12" />
      <p className="text-secondary text-ink-soft">Step {String(number)} of 3</p>
      {step === "store" ? (
        <>
          <h1 className="mb-2 text-title font-extrabold">Choose your store</h1>
          <p className="mb-6 text-body text-ink-soft">
            Dinner Bell uses its prices and aisles for your meals and your list.
          </p>
          <ChooseStore
            onChosen={() => void navigate({ to: "/welcome", search: { step: "dinner" } })}
          />
        </>
      ) : step === "dinner" ? (
        <>
          <h1 className="mb-2 text-title font-extrabold">Add your first dinner</h1>
          <p className="mb-6 text-body text-ink-soft">
            Start with a dinner you make often. Add what you buy for it, and each item remembers its
            product for next time.
          </p>
          <div className="flex flex-col gap-2">
            <Button
              block
              onClick={() =>
                void navigate({ to: "/meals/new", search: { role: "main", first: true } })
              }
            >
              Add your first dinner
            </Button>
            <Button
              variant="quiet"
              block
              onClick={() => void navigate({ to: "/welcome", search: { step: "done" } })}
            >
              Skip for now
            </Button>
          </div>
        </>
      ) : (
        <>
          <h1 className="mb-2 text-title font-extrabold">You’re set.</h1>
          <p className="mb-6 text-body text-ink-soft">
            Plan this week’s dinners and the shopping list builds itself. Add more meals any time
            from Meals.
          </p>
          <Button block onClick={() => void navigate({ to: "/" })}>
            See this week’s plan
          </Button>
        </>
      )}
    </main>
  );
}
