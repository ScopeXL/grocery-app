/**
 * Choices shared by Add a meal and Change (UX §4.5, ADR 0026):
 * - what the meal is for (breakfast, lunch, dinner or a snack), chosen when planning it;
 * - which day, as Sunday-to-Saturday pills. Each pill is the next such day, today included;
 *   tapping the chosen one clears it, and with none chosen the meal is for any day.
 */
import { useId } from "react";

import { dayReadout, weekPills } from "../../lib/days";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";
import { OCCASIONS, type Occasion } from "./types";

export function OccasionPicker({
  occasion,
  onOccasion,
  disabled = false,
}: {
  occasion: Occasion;
  onOccasion: (occasion: Occasion) => void;
  disabled?: boolean;
}) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className="mb-5">
      <h3 id={headingId} className="mb-2 text-body font-bold">
        Eat it for
      </h3>
      <div role="group" aria-labelledby={headingId} className="flex flex-wrap gap-2">
        {OCCASIONS.map((choice) => (
          <Chip
            key={choice.value}
            on={occasion === choice.value}
            disabled={disabled}
            onClick={() => {
              onOccasion(choice.value);
            }}
          >
            {choice.label}
          </Chip>
        ))}
      </div>
    </section>
  );
}

const PILL =
  "flex min-h-12 flex-col items-center justify-center rounded-lg border-2 border-rule bg-paper text-secondary font-semibold leading-tight disabled:opacity-60 aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent";

export function DayPicker({
  day,
  today,
  onDay,
  disabled = false,
}: {
  day: string | null;
  today: string;
  onDay: (day: string | null) => void;
  disabled?: boolean;
}) {
  const headingId = useId();
  const helpId = useId();
  const pills = weekPills(today);
  const matched = day === null || pills.some((pill) => pill.value === day);
  return (
    <section aria-labelledby={headingId} className="mb-5">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <h3 id={headingId} className="text-body font-bold">
          Day
        </h3>
        <span aria-live="polite" className="text-secondary font-semibold">
          {dayReadout(day, today)}
        </span>
      </div>
      <p id={helpId} className="mb-2 text-secondary text-ink-soft">
        Optional: the day you’ll make it. Each day is the next one coming up, starting today. None
        picked means any day.
      </p>
      <div
        role="group"
        aria-labelledby={headingId}
        aria-describedby={helpId}
        className="grid grid-cols-7 gap-1"
      >
        {pills.map((pill) => (
          <button
            key={pill.value}
            type="button"
            aria-pressed={day === pill.value}
            disabled={disabled}
            onClick={() => {
              onDay(day === pill.value ? null : pill.value);
            }}
            className={PILL}
          >
            <span>{pill.label}</span>
            {pill.today ? (
              <span className="text-caption font-normal">
                <span className="sr-only">, </span>today
              </span>
            ) : null}
          </button>
        ))}
      </div>
      {matched ? null : (
        <Button
          variant="quiet"
          className="-ml-5"
          disabled={disabled}
          onClick={() => {
            onDay(null);
          }}
        >
          Any day
        </Button>
      )}
    </section>
  );
}
