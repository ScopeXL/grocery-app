import { mealPrice } from "../../lib/money";

/** A meal's price in a card's corner (UX §2): "$12" on screen, "about $12" when read out. */
export function MealPrice({ cost }: { cost: { about_dollars: number | null } }) {
  const price = mealPrice(cost);
  if (!price) return null;
  return (
    <span className="shrink-0 text-body font-bold tabular-nums">
      <span aria-hidden="true">{price.shown}</span>
      <span className="sr-only">{price.spoken}</span>
    </span>
  );
}
