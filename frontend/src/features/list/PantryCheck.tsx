/**
 * The pantry check (UX §4.11): staples on the list wait here until someone answers Have it or
 * Need it. Have-it lines leave the total; both answers can be changed from the line's sheet.
 */
import { api, unwrap } from "../../api/client";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import type { Line } from "../plan/types";
import { usePlanChange } from "../plan/usePlan";

export function PantryCheck({ lines }: { lines: Line[] }) {
  const answer = usePlanChange(async ({ itemId, have }: { itemId: string; have: boolean }) =>
    unwrap(
      await api.PUT("/api/plan/items/{item_id}", {
        params: { path: { item_id: itemId } },
        body: { have_it: have, always: false },
      }),
    ),
  );
  if (lines.length === 0) return null;
  return (
    <section
      aria-label="Check the pantry"
      className="mb-6 overflow-hidden rounded-tile border-2 border-lemon bg-paper"
    >
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-row font-bold">
          Check the pantry: {lines.length} staple{lines.length === 1 ? "" : "s"}
        </h2>
        <p className="text-secondary text-ink-soft">
          Already have it? It stays on the list but leaves the total.
        </p>
      </div>
      <ul>
        {lines.map((line) => {
          const itemId = line.item_id;
          if (!itemId) return null;
          return (
            <li
              key={line.key}
              className="flex flex-wrap items-center gap-3 border-t border-rule px-4 py-3"
            >
              <ProductImage src={line.image_url} alt="" size={48} />
              <span className="min-w-40 flex-1 text-body font-semibold">{line.name}</span>
              <span className="flex w-full gap-2 sm:w-auto [&>button]:flex-1">
                <Button
                  variant="secondary"
                  disabled={answer.isPending}
                  aria-label={`Have ${line.name}`}
                  onClick={() => {
                    answer.mutate({ itemId, have: true });
                  }}
                >
                  Have it
                </Button>
                <Button
                  variant="secondary"
                  disabled={answer.isPending}
                  aria-label={`Need ${line.name}`}
                  onClick={() => {
                    answer.mutate({ itemId, have: false });
                  }}
                >
                  Need it
                </Button>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
