/**
 * Plan days are local calendar dates ("2026-10-07") in the household's time zone; the server
 * says which date is today. Arithmetic runs on UTC midnights so no device time zone leaks in.
 */
const DAY_MS = 86_400_000;
const AHEAD = 6; // Today plus the next six days (UX §4.5)

function toUtc(day: string): number {
  const [year, month, date] = day.split("-").map(Number);
  return Date.UTC(year ?? 1970, (month ?? 1) - 1, date ?? 1);
}

function fromUtc(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

export function addDays(day: string, count: number): string {
  return fromUtc(toUtc(day) + count * DAY_MS);
}

function weekday(day: string, style: "short" | "long"): string {
  return new Date(toUtc(day)).toLocaleDateString("en-US", { weekday: style, timeZone: "UTC" });
}

/** The chips for choosing a day: Any day, Today, then the next six days by name. */
export function dayChoices(today: string): { value: string | null; label: string }[] {
  const choices: { value: string | null; label: string }[] = [
    { value: null, label: "Any day" },
    { value: today, label: "Today" },
  ];
  for (let ahead = 1; ahead <= AHEAD; ahead++) {
    const day = addDays(today, ahead);
    choices.push({ value: day, label: weekday(day, "short") });
  }
  return choices;
}

/** A planned day as a chip says it: "Today", "Tue", or "Mon, Oct 5" when it's not this week. */
export function dayLabel(day: string, today: string): string {
  const offset = Math.round((toUtc(day) - toUtc(today)) / DAY_MS);
  if (offset === 0) return "Today";
  if (offset > 0 && offset <= AHEAD) return weekday(day, "short");
  return new Date(toUtc(day)).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
