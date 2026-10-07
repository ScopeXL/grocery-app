import { describe, expect, it } from "vitest";

import type { Line, PlanOut } from "../plan/types";
import { byAisle, byMeal, isUnpriced } from "./ListScreen";

function line(name: string, section: string, extra: Partial<Line> = {}): Line {
  return {
    key: name,
    item_id: name,
    name,
    image_url: null,
    product_url: null,
    quantity: "1",
    quantity_text: "1 package",
    unit: "package",
    computed: "1",
    extra: "0",
    at_least: false,
    needed_text: null,
    size_text: null,
    cost_cents: 100,
    regular_cents: 100,
    sale: null,
    estimated_weight: false,
    used_by: [],
    extras: [],
    have_it: null,
    staple: false,
    swapped: false,
    warnings: [],
    flags: [],
    section: { key: section, label: section, order: 0 },
    ...extra,
  };
}

const use = (meal_id: string) => ({ meal_id, name: meal_id, dish_names: [meal_id] });

describe("list grouping", () => {
  it("groups lines in walking order by section", () => {
    const groups = byAisle([
      line("Onion", "Produce"),
      line("Lime", "Produce"),
      line("Beans", "Aisle 9"),
    ]);
    expect(groups.map((group) => [group.label, group.lines.map((l) => l.name)])).toEqual([
      ["Produce", ["Onion", "Lime"]],
      ["Aisle 9", ["Beans"]],
    ]);
  });

  it("puts a shared line under the first meal on the plan that uses it", () => {
    const plan = {
      meals: [
        { id: "tacos", main: { name: "Tacos" } },
        { id: "chili", main: { name: "Chili" } },
      ],
    } as unknown as PlanOut;
    const beef = line("Beef", "Meat", { used_by: [use("chili"), use("tacos")] });
    const beans = line("Beans", "Aisle 9", { used_by: [use("chili")] });
    expect(byMeal(plan, [beef, beans]).map((g) => [g.label, g.lines.map((l) => l.name)])).toEqual([
      ["Tacos", ["Beef"]],
      ["Chili", ["Beans"]],
    ]);
  });

  it("counts lines without a full price, but never ones the household has", () => {
    expect(isUnpriced(line("Candles", "Other", { cost_cents: null }))).toBe(true);
    expect(isUnpriced(line("Onions", "Produce", { at_least: true }))).toBe(true);
    expect(isUnpriced(line("Oil", "Aisle 12", { cost_cents: null, have_it: true }))).toBe(false);
    expect(isUnpriced(line("Milk", "Dairy"))).toBe(false);
  });
});
