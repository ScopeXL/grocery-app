import { describe, expect, it } from "vitest";

import { about, costLine, mealPrice } from "./money";

describe("money", () => {
  it("reads as an estimate", () => {
    expect(about(125)).toBe("about $1.25");
    expect(about(1449)).toBe("about $14");
    expect(about(1450)).toBe("about $15");
  });

  it("gives a meal card its line, and says what's missing", () => {
    expect(costLine({ about_dollars: 14, unpriced: 0 })).toEqual({
      total: "about $14",
      note: null,
    });
    expect(costLine({ about_dollars: 9, unpriced: 2 }).note).toBe("2 items have no price");
    expect(costLine({ about_dollars: null, unpriced: 3 }).total).toBe("No price yet");
  });

  it("puts a meal's price in a corner, read out as an estimate", () => {
    expect(mealPrice({ about_dollars: 12 })).toEqual({ shown: "$12", spoken: "about $12" });
    expect(mealPrice({ about_dollars: null })).toBeNull();
  });
});
