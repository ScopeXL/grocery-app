import type { components } from "../../api/schema";

type Schemas = components["schemas"];

export type DishCard = Schemas["DishCard"];
export type DishOut = Schemas["DishOut"];
export type DishLineOut = Schemas["DishLineOut"];
export type ItemOut = Schemas["ItemOut"];
export type AmountIn = Schemas["AmountIn"];
export type AmountOut = Schemas["AmountOut"];
export type ProductResult = Schemas["ProductResult"];
export type PickerOut = Schemas["PickerOut"];
export type KindOption = Schemas["KindOptionOut"];
export type PreviewOut = Schemas["PreviewOut"];
export type Role = DishOut["role"];
export type Occasion = DishOut["occasions"][number];

export const OCCASIONS: readonly { value: Occasion; label: string }[] = [
  { value: "breakfast", label: "Breakfast" },
  { value: "lunch", label: "Lunch" },
  { value: "dinner", label: "Dinner" },
  { value: "snack", label: "Snack" },
];

export function occasionLabel(value: Occasion): string {
  return OCCASIONS.find((occasion) => occasion.value === value)?.label ?? value;
}
