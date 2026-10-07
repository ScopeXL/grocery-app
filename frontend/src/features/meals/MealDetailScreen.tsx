/**
 * One meal (docs/UX.md §4.7): photo, occasions, servings, notes or recipe link, the item lines
 * with their amounts and shares of the cost, and a Main's usual sides. Add to plan opens the
 * same sheet as the Plan screen, at the sides step. Archive offers Undo, never a confirmation.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, ExternalLink } from "lucide-react";
import { useState, type ReactNode } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { about, costLine } from "../../lib/money";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { AddMealSheet } from "../plan/AddMealSheet";
import { usePlan } from "../plan/usePlan";
import { UsualSides } from "../plan/UsualSides";
import { FavoriteButton } from "./MealsScreen";
import { occasionLabel, type DishOut } from "./types";

export function MealDetailScreen({ dishId }: { dishId: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const plan = usePlan();
  const [planning, setPlanning] = useState(false);
  const dish = useQuery({
    queryKey: qk.dish(dishId),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes/{dish_id}", { params: { path: { dish_id: dishId } } })),
  });

  const changed = async (updated: DishOut) => {
    queryClient.setQueryData(qk.dish(updated.id), updated);
    await queryClient.invalidateQueries({ queryKey: qk.dishes() });
  };
  const path = { params: { path: { dish_id: dishId } } };
  const restore = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/dishes/{dish_id}/restore", path)),
    onSuccess: changed,
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const archive = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/dishes/{dish_id}/archive", path)),
    onSuccess: async (updated) => {
      await changed(updated);
      showToast(`${updated.name} archived`, {
        label: "Undo",
        onAction: () => {
          restore.mutate();
        },
      });
      await navigate({ to: "/meals", search: { role: updated.role } });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const duplicate = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/dishes/{dish_id}/duplicate", path)),
    onSuccess: async (copy) => {
      await changed(copy);
      showToast(`Made ${copy.name}`);
      await navigate({ to: "/meals/$dishId/edit", params: { dishId: copy.id } });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });

  if (dish.isError) return <Shell>{errorMessage(dish.error)}</Shell>;
  if (!dish.data) return <Shell>Loading…</Shell>;
  const meal = dish.data;
  const cost = costLine(meal.cost);

  return (
    <main className="mx-auto w-full max-w-2xl px-4 pt-[calc(env(safe-area-inset-top)+16px)] pb-36 lg:pb-16">
      <Link
        to="/meals"
        search={{ role: meal.role }}
        className="mb-2 inline-flex min-h-12 items-center gap-1 text-body font-semibold text-basil"
      >
        <ChevronLeft aria-hidden="true" />
        {meal.role === "main" ? "Meals" : "Sides"}
      </Link>

      {meal.photo_url ? (
        <img
          src={meal.photo_url}
          alt=""
          className="mb-4 aspect-[4/3] w-full rounded-tile object-cover"
        />
      ) : null}

      <div className="mb-2 flex items-start gap-2">
        <h1 className="flex-1 text-title font-extrabold">{meal.name}</h1>
        <FavoriteButton id={meal.id} name={meal.name} favorite={meal.favorite} />
      </div>

      {meal.archived ? (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-tile bg-counter p-3">
          <p className="flex-1 text-body">This meal is archived.</p>
          <Button
            variant="secondary"
            disabled={restore.isPending}
            onClick={() => {
              restore.mutate();
            }}
          >
            Restore
          </Button>
        </div>
      ) : null}

      <div className="mb-5 flex flex-col gap-1 text-secondary text-ink-soft">
        <span>{meal.role === "main" ? "Main" : "Side"}</span>
        <span>{meal.occasions.map(occasionLabel).join(", ")}</span>
        {meal.servings ? <span>Serves {String(meal.servings)}</span> : null}
      </div>

      {meal.notes ? <p className="mb-4 text-body whitespace-pre-line">{meal.notes}</p> : null}
      {meal.recipe_url ? (
        <a
          href={meal.recipe_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mb-5 inline-flex min-h-12 items-center gap-2 text-body font-semibold text-basil"
        >
          Open the recipe
          <ExternalLink aria-hidden="true" className="size-5" />
        </a>
      ) : null}

      <section className="mb-6">
        <h2 className="mb-3 text-row font-bold">Items</h2>
        {meal.lines.length === 0 ? (
          <p className="text-body">No items yet. Edit the meal to add what you buy for it.</p>
        ) : (
          <ul
            aria-label="Items in this meal"
            className="overflow-hidden rounded-tile border border-rule bg-paper"
          >
            {meal.lines.map((line) => (
              <li
                key={line.id}
                className="flex min-h-16 items-center gap-3 border-b border-rule px-3 py-2 last:border-b-0"
              >
                <ProductImage src={line.item.image_url} alt="" size={48} />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-body font-semibold">{line.item.name}</span>
                  <span className="text-secondary text-ink-soft">{line.amount.text}</span>
                  {line.check_amount ? (
                    <span className="text-secondary text-tomato">
                      Check amount: {line.check_amount}
                    </span>
                  ) : null}
                </span>
                <span className="text-secondary text-ink-soft">
                  {line.cost_cents !== null ? about(line.cost_cents) : "no price"}
                </span>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-3 flex flex-col">
          <span className="text-row font-bold">{cost.total}</span>
          {cost.note ? <span className="text-secondary text-ink-soft">{cost.note}</span> : null}
          <span className="text-caption text-ink-soft">Today's prices for what this meal uses</span>
        </div>
      </section>

      {meal.role === "main" && !meal.archived ? <UsualSides mainId={meal.id} /> : null}

      <div className="flex flex-wrap gap-2">
        {meal.role === "main" && !meal.archived ? (
          <Button
            disabled={!plan.data}
            onClick={() => {
              setPlanning(true);
            }}
          >
            Add to plan
          </Button>
        ) : null}
        <Button
          variant={meal.role === "main" && !meal.archived ? "secondary" : "primary"}
          onClick={() => void navigate({ to: "/meals/$dishId/edit", params: { dishId: meal.id } })}
        >
          Edit
        </Button>
        <Button
          variant="secondary"
          disabled={duplicate.isPending}
          onClick={() => {
            duplicate.mutate();
          }}
        >
          Duplicate
        </Button>
        {!meal.archived ? (
          <Button
            variant="quiet-danger"
            disabled={archive.isPending}
            onClick={() => {
              archive.mutate();
            }}
          >
            Archive
          </Button>
        ) : null}
      </div>
      {plan.data ? (
        <AddMealSheet
          open={planning}
          today={plan.data.today}
          preset={{ id: meal.id, name: meal.name }}
          onClose={() => {
            setPlanning(false);
          }}
        />
      ) : null}
    </main>
  );
}

function Shell({ children }: { children: ReactNode }) {
  return <main className="mx-auto max-w-2xl px-4 pt-12 text-body">{children}</main>;
}
