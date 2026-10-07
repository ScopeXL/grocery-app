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

const WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

export interface DayPill {
  value: string;
  label: (typeof WEEK)[number];
  today: boolean;
}

/**
 * The day pills, Sunday to Saturday (UX §4.5, ADR 0026). Each is the next such day, today
 * included: on a Wednesday, "Wed" is today and "Mon" is the Monday five days ahead.
 */
export function weekPills(today: string): DayPill[] {
  const from = new Date(toUtc(today)).getUTCDay();
  return WEEK.map((label, index) => ({
    value: addDays(today, (index - from + 7) % 7),
    label,
    today: index === from,
  }));
}

/** What the day picker reads out: "Any day", "Today", or "Thu, Oct 8". */
export function dayReadout(day: string | null, today: string): string {
  if (day === null) return "Any day";
  if (day === today) return "Today";
  return new Date(toUtc(day)).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
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

/** A sale's last day as a tag says it: "Oct 14". */
export function shortDay(day: string): string {
  return new Date(toUtc(day)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
