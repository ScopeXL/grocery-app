/** Money always reads as an estimate (docs/UX.md §2); the server does the arithmetic. */
const exact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

/** "$1.25": for one item's share, where cents matter. */
export function cents(value: number): string {
  return exact.format(value / 100);
}

/** "about $1.25" for small shares, "about $14" once whole dollars are enough. */
export function about(valueCents: number): string {
  if (valueCents < 1000) return `about ${cents(valueCents)}`;
  return `about $${String(Math.floor(valueCents / 100 + 0.5))}`;
}

/** The meal card line: "about $14", or what's missing. */
export function costLine(cost: { about_dollars: number | null; unpriced: number }): {
  total: string;
  note: string | null;
} {
  const note =
    cost.unpriced === 0
      ? null
      : `${String(cost.unpriced)} item${cost.unpriced === 1 ? " has" : "s have"} no price`;
  if (cost.about_dollars === null) return { total: "No price yet", note: null };
  return { total: `about $${String(cost.about_dollars)}`, note };
}

/** A meal's price for a card's corner (UX §2): "$12" on screen, "about $12" when read out. */
export function mealPrice(cost: {
  about_dollars: number | null;
}): { shown: string; spoken: string } | null {
  if (cost.about_dollars === null) return null;
  const dollars = `$${String(cost.about_dollars)}`;
  return { shown: dollars, spoken: `about ${dollars}` };
}
