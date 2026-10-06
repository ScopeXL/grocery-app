# ADR 0007: Package-relative amounts with exact units; `Fraction` quantities; integer cents

- **Status:** Accepted (the owner's answer to the open question, plus defaults adopted in planning)
- **Date:** 2026-10-06

## Context

Turning "how much a meal needs" into "how many packages to buy" drives the list, the total and the recommendations, so it must be right. Three options were weighed for how amounts are expressed:
1. **Package terms only:** ½ bag, 2 cans, 6 oz, 3 onions.
2. **Package terms plus exact units:** kitchen measures only where they convert exactly.
3. **Cups and tablespoons for anything,** using density tables. Rejected: a cup of shredded cheese has no fixed weight, so those conversions are estimates that would skew the list.

Floating-point arithmetic is a real trap here. For example, 3 × 1.1 oz of a 3.3 oz package buys 2 packages with floats, but 1 with exact arithmetic.

## Decision

**Amounts**
- An amount is one of three kinds, always relative to the linked product:
  - part of a package;
  - a count;
  - a weight or volume of the package size.
- Kitchen measures (tsp, tbsp, cup…) appear **only when the package is sold by volume**.
- Conversions are exact, within a dimension only. Weight and volume never convert into each other.

**Numbers**
- Quantities are `fractions.Fraction` everywhere, stored as canonical fraction text (`"3/8"`). Floats are rejected at every constructor.
- Money is integer cents. Rounding is half-up, in exactly two places: each weight-priced line, and the displayed "about $N".

**List building**
- Merge shares across all meals first, then round up once.
- Items sold by the pound round to whole pieces plus ¼ lb steps, never to whole packages.
- Amounts that can't be converted stay visible as "at least N" and count toward the "not priced" tally.

**Placement and tests**
- All of this lives in the pure `domain/` package (no I/O). A purity test enforces that.
- About 60 named example tests plus Hypothesis property tests ([PLAN §8](../PLAN.md#8-quantity-math-totals-and-recommendations)).

**Defaults adopted** (the owner can overrule any of them):
1. Quantity overrides are stored as deltas, so the list never silently under-buys after the plan grows.
2. Weight-sold items use whole pieces plus ¼ lb steps.
3. Kroger's per-each estimate is a fallback only when sane (1 oz–5 lb), with an "est." badge. Otherwise the household's "about how much one weighs" is used.
4. A promo counts only if it's above 0, below the regular price, and within its dates.
5. 3 recommendations, at least $1 of leftover value each, and items named only if worth ≥ 25¢.
6. "oz" always means weight; the household corrects juice sold as "64 oz".
7. A swap to a size that can't be compared buys the same share and is flagged "check amount".

## Consequences

- The amount picker offers only what the math can convert. There is never a free-text unit field.
- Recipe-style cups for flour or cheese aren't supported. The household picks "¼ bag" or a weight instead.
- Exact arithmetic makes the tests deterministic, and makes properties like "rounding never under-buys" provable by test.
