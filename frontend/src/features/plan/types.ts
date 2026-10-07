import type { components } from "../../api/schema";

type Schemas = components["schemas"];

export type PlanOut = Schemas["PlanOut"];
export type PlannedMeal = Schemas["PlannedMealOut"];
export type DishRef = Schemas["DishRef"];
export type Line = Schemas["LineOut"];
export type Extra = Schemas["ExtraOut"];
export type Usual = Schemas["UsualOut"];
export type Totals = Schemas["TotalsOut"];
export type MemberRef = Schemas["MemberRef"];
export type Scale = PlannedMeal["scale"];
/** What a planned meal is for (ADR 0026): chosen when planning, not stored on the meal itself. */
export type Occasion = PlannedMeal["occasion"];
export type Alternative = Schemas["AlternativeOut"];
export type UsualSide = Schemas["UsualSideOut"];

export const SCALES: readonly { value: Scale; label: string }[] = [
  { value: "1/2", label: "×½" },
  { value: "1", label: "×1" },
  { value: "2", label: "×2" },
];

export const OCCASIONS: readonly { value: Occasion; label: string }[] = [
  { value: "breakfast", label: "Breakfast" },
  { value: "lunch", label: "Lunch" },
  { value: "dinner", label: "Dinner" },
  { value: "snack", label: "Snack" },
];

export function occasionLabel(value: Occasion): string {
  return OCCASIONS.find((occasion) => occasion.value === value)?.label ?? value;
}

export function scaleLabel(value: Scale): string {
  return SCALES.find((scale) => scale.value === value)?.label ?? value;
}

/** "Rice", "Rice and corn", "Rice, corn and salad" (no serial comma, UX §2). */
export function joinNames(names: readonly string[]): string {
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1] ?? ""}`;
}
