/**
 * The sticky total (UX §4.4): "About $142" with the sale savings beside it, when prices were
 * checked, and what isn't counted. Separate lines, never one string joined with dots.
 */
import { Link } from "@tanstack/react-router";

import type { PlanOut } from "./types";

export function TotalFooter({ plan, compact = false }: { plan: PlanOut; compact?: boolean }) {
  const totals = plan.totals;
  if (compact) {
    return (
      <div className="flex w-full items-center justify-between gap-3" aria-live="polite">
        <span className="text-row font-extrabold" data-testid="total">
          {totals.total_text}
        </span>
        {totals.savings_text ? (
          <span className="shrink-0 rounded-full bg-lemon px-3 py-0.5 text-caption font-bold text-on-lemon">
            {totals.savings_text}
          </span>
        ) : null}
      </div>
    );
  }
  return (
    <div className="flex w-full flex-col" aria-live="polite">
      <div className="flex items-center justify-between gap-3">
        <span className="text-total font-extrabold" data-testid="total">
          {totals.total_text}
        </span>
        {totals.savings_text ? (
          <span className="shrink-0 rounded-full bg-lemon px-3 py-0.5 text-caption font-bold text-on-lemon">
            {totals.savings_text}
          </span>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col text-caption text-ink-soft">
          <span>Before tax, fees and tip</span>
          {totals.prices_as_of_text ? <span>{totals.prices_as_of_text}</span> : null}
          {plan.prices_note ? <span>{plan.prices_note}</span> : null}
        </div>
        {totals.not_priced_text ? (
          <Link
            to="/list"
            search={{ show: "unpriced" }}
            className="inline-flex min-h-12 shrink-0 items-center text-right text-secondary font-semibold text-basil underline underline-offset-4"
          >
            {totals.not_priced_text}
          </Link>
        ) : null}
      </div>
    </div>
  );
}
