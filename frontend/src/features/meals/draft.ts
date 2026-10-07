/**
 * A meal being made or edited, saved on this phone at every change, so closing the app loses
 * nothing (UX §1, §4.8).
 */
import type { AmountOut, DishOut, ItemOut, Role } from "./types";

export interface DraftLine {
  key: string;
  item: ItemOut;
  amount: AmountOut;
}

export interface Draft {
  name: string;
  role: Role | null;
  servings: string;
  notes: string;
  recipeUrl: string;
  photoId: string | null;
  lines: DraftLine[];
  step: number;
}

/** A new meal's guided steps, in order. */
export const STEP = { name: 0, role: 1, items: 2, extras: 3 } as const;
export const STEP_COUNT = 4;

export function emptyDraft(role: Role | undefined): Draft {
  return {
    name: "",
    role: role ?? null,
    servings: "",
    notes: "",
    recipeUrl: "",
    photoId: null,
    lines: [],
    step: STEP.name,
  };
}

export function fromDish(dish: DishOut): Draft {
  return {
    name: dish.name,
    role: dish.role,
    servings: dish.servings === null ? "" : String(dish.servings),
    notes: dish.notes ?? "",
    recipeUrl: dish.recipe_url ?? "",
    photoId: dish.photo_id,
    lines: dish.lines.map((line) => ({ key: line.id, item: line.item, amount: line.amount })),
    step: STEP.extras,
  };
}

/**
 * A saved draft, or null when it can't be trusted (corrupted, or too old). Drafts saved before
 * ADR 0026 had a "When do you eat it?" step at index 2 and an `occasions` field: their later
 * steps move back by one, so a half-made meal picks up where it was.
 */
export function asDraft(value: unknown): Draft | null {
  if (typeof value !== "object" || value === null) return null;
  const saved = value as Partial<Draft> & { occasions?: unknown };
  const valid =
    typeof saved.name === "string" &&
    (saved.role === null || saved.role === "main" || saved.role === "side") &&
    Array.isArray(saved.lines) &&
    typeof saved.step === "number" &&
    typeof saved.servings === "string" &&
    typeof saved.notes === "string" &&
    typeof saved.recipeUrl === "string";
  if (!valid) return null;
  const { occasions, ...rest } = saved;
  const savedStep = rest.step ?? 0;
  const step = occasions !== undefined && savedStep > STEP.items ? savedStep - 1 : savedStep;
  return { ...(rest as Draft), step: Math.min(Math.max(step, 0), STEP_COUNT - 1) };
}
