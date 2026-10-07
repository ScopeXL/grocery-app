import { describe, expect, it } from "vitest";

import { addDays, dayLabel, dayReadout, weekPills } from "./days";

describe("plan days", () => {
  it("offers Sunday to Saturday, each the next such day, today included", () => {
    const pills = weekPills("2026-10-06"); // a Tuesday
    expect(pills.map((pill) => pill.label)).toEqual([
      "Sun",
      "Mon",
      "Tue",
      "Wed",
      "Thu",
      "Fri",
      "Sat",
    ]);
    expect(pills.map((pill) => pill.value)).toEqual([
      "2026-10-11",
      "2026-10-12",
      "2026-10-06",
      "2026-10-07",
      "2026-10-08",
      "2026-10-09",
      "2026-10-10",
    ]);
    expect(pills.filter((pill) => pill.today).map((pill) => pill.label)).toEqual(["Tue"]);
  });

  it("wraps around the week from a Sunday and from a Saturday", () => {
    expect(weekPills("2026-10-11")[0]).toEqual({ value: "2026-10-11", label: "Sun", today: true });
    expect(weekPills("2026-10-11")[6]?.value).toBe("2026-10-17");
    expect(weekPills("2026-10-10")[6]).toEqual({ value: "2026-10-10", label: "Sat", today: true });
    expect(weekPills("2026-10-10")[0]?.value).toBe("2026-10-11");
  });

  it("crosses a year and the end of daylight saving time", () => {
    expect(weekPills("2026-12-31")[0]?.value).toBe("2027-01-03"); // Thursday → Sunday
    expect(weekPills("2026-10-30")[0]?.value).toBe("2026-11-01"); // across the DST change
  });

  it("reads out the chosen day", () => {
    expect(dayReadout(null, "2026-10-06")).toBe("Any day");
    expect(dayReadout("2026-10-06", "2026-10-06")).toBe("Today");
    expect(dayReadout("2026-10-08", "2026-10-06")).toBe("Thu, Oct 8");
  });

  it("names a planned day the way a chip says it", () => {
    expect(dayLabel("2026-10-06", "2026-10-06")).toBe("Today");
    expect(dayLabel("2026-10-09", "2026-10-06")).toBe("Fri");
    expect(dayLabel("2026-10-05", "2026-10-06")).toBe("Mon, Oct 5");
    expect(dayLabel("2026-10-20", "2026-10-06")).toBe("Tue, Oct 20");
  });

  it("crosses months and the end of daylight saving time without drifting", () => {
    expect(addDays("2026-10-30", 3)).toBe("2026-11-02");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });
});
