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
