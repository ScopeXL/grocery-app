import { describe, expect, it } from "vitest";

import { asDraft, emptyDraft, STEP, STEP_COUNT } from "./draft";

const base = { name: "Tacos", role: "main", servings: "", notes: "", recipeUrl: "", lines: [] };

describe("meal drafts", () => {
  it("has four steps: name, main or side, items, anything else", () => {
    expect(STEP_COUNT).toBe(4);
    expect(Object.values(STEP)).toEqual([0, 1, 2, 3]);
    expect(emptyDraft("side")).toMatchObject({ role: "side", step: STEP.name });
  });

  it("keeps a current draft as it is", () => {
    expect(asDraft({ ...base, photoId: null, step: STEP.items })).toMatchObject({ step: 2 });
  });

  it("moves an older five-step draft back past the step that asked when you eat it", () => {
    const old = { ...base, photoId: null, occasions: ["dinner"] };
    expect(asDraft({ ...old, step: 1 })?.step).toBe(STEP.role);
    expect(asDraft({ ...old, step: 2 })?.step).toBe(STEP.items); // was "When do you eat it?"
    expect(asDraft({ ...old, step: 3 })?.step).toBe(STEP.items); // was items
    expect(asDraft({ ...old, step: 4 })?.step).toBe(STEP.extras);
    expect(asDraft({ ...old, step: 4 })).not.toHaveProperty("occasions");
  });

  it("drops what it can't trust", () => {
    expect(asDraft(null)).toBeNull();
    expect(asDraft({ ...base, step: "two" })).toBeNull();
    expect(asDraft({ ...base, role: "dessert", step: 0 })).toBeNull();
  });
});
