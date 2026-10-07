/**
 * "Uses what you're buying" (UX §4.4): Mains that would use up leftovers of what this week's
 * list already buys, each with the reason in plain words ("Taco salad uses your leftover
 * lettuce, cheese and ground beef. Adds about $4.") and an Add button. Adding puts the Main on
 * the plan on its own, so the total moves by what the reason says.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { MealThumb } from "./MealThumb";
import { usePlanChange } from "./usePlan";

export function Suggestions() {
  const queryClient = useQueryClient();
  const found = useQuery({
    queryKey: qk.suggestions(),
    queryFn: async () => unwrap(await api.GET("/api/plan/recommendations")),
    staleTime: 60_000,
  });
  const undo = usePlanChange(async (mealId: string) =>
    unwrap(
      await api.DELETE("/api/plan/meals/{meal_id}", { params: { path: { meal_id: mealId } } }),
    ),
  );
  const add = usePlanChange(
    async ({ dishId }: { dishId: string; name: string }) =>
      unwrap(
        await api.POST("/api/plan/meals", {
          // No occasion: the server uses what this main was last planned for (ADR 0026).
          body: { main_id: dishId, side_ids: [], day: null, scale: "1" },
        }),
      ),
    (plan, { name }) => {
      void queryClient.invalidateQueries({ queryKey: qk.suggestions() });
      const mealId = plan.changed;
      showToast(
        `${name} added`,
        mealId
          ? {
              label: "Undo",
              onAction: () => {
                undo.mutate(mealId);
              },
            }
          : undefined,
      );
    },
  );
  const items = found.data ?? [];
  if (items.length === 0) return null;

  return (
    <section aria-label="Uses what you're buying" className="mt-6">
      <h2 className="mb-2 text-row font-bold">Uses what you’re buying</h2>
      <ul className="flex flex-col gap-3">
        {items.map((item) => (
          <li
            key={item.dish_id}
            className="flex items-start gap-3 rounded-tile border border-rule bg-paper p-3"
          >
            <MealThumb
              dish={{
                id: item.dish_id,
                name: item.name,
                photo_url: item.photo_url,
                item_images: item.item_images,
                archived: false,
              }}
            />
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <p className="text-body">{item.text}</p>
              <Button
                variant="secondary"
                className="self-start"
                aria-label={`Add ${item.name}`}
                disabled={add.isPending}
                onClick={() => {
                  add.mutate({ dishId: item.dish_id, name: item.name });
                }}
              >
                Add
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
