import { describe, expect, it } from "vitest";

import { addDays, dayChoices, dayLabel } from "./days";

describe("plan days", () => {
  it("offers Any day, Today and the next six days by name", () => {
    expect(dayChoices("2026-10-06").map((choice) => choice.label)).toEqual([
      "Any day",
      "Today",
      "Wed",
      "Thu",
      "Fri",
      "Sat",
      "Sun",
      "Mon",
    ]);
    expect(dayChoices("2026-10-06")[2]?.value).toBe("2026-10-07");
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
