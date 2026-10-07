/**
 * The meal library (docs/UX.md §4.6): Mains or Sides, search, occasion chips and Favorites.
 * Cards show the household's photo (cropped 4:3) or a strip of uncropped product photos.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Plus, Star } from "lucide-react";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { costLine } from "../../lib/money";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";
import { EmptyState } from "../../ui/EmptyState";
import { ProductImage } from "../../ui/ProductImage";
import { Screen } from "../../ui/Screen";
import { OCCASIONS, type DishCard, type Occasion, type Role } from "./types";

export function MealsScreen({ role }: { role: Role }) {
  const navigate = useNavigate();
  const searchId = useId();
  const [query, setQuery] = useState("");
  const [occasion, setOccasion] = useState<Occasion | null>(null);
  const [favorites, setFavorites] = useState(false);
  const [archived, setArchived] = useState(false);

  const dishes = useQuery({
    queryKey: qk.dishList(role, archived),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes", { params: { query: { role, archived } } })),
  });

  const needle = query.trim().toLowerCase();
  const all = dishes.data ?? [];
  const shown = all.filter(
    (card) =>
      (!needle || card.name.toLowerCase().includes(needle)) &&
      (!occasion || card.occasions.includes(occasion)) &&
      (!favorites || card.favorite),
  );
  const noun = role === "main" ? "meal" : "side";

  return (
    <Screen
      title={archived ? "Archived" : "Meals"}
      actions={
        all.length > 0 && !archived ? (
          <Button block onClick={() => void navigate({ to: "/meals/new", search: { role } })}>
            <Plus aria-hidden="true" />
            New {noun}
          </Button>
        ) : undefined
      }
    >
      <div
        role="group"
        aria-label="Mains or sides"
        className="mb-4 grid grid-cols-2 rounded-button border-2 border-rule bg-paper p-1"
      >
        {(["main", "side"] as const).map((value) => (
          <Link
            key={value}
            to="/meals"
            search={{ role: value }}
            aria-pressed={role === value}
            className="flex min-h-12 items-center justify-center rounded-button text-body font-semibold aria-pressed:bg-basil aria-pressed:text-on-basil"
          >
            {value === "main" ? "Mains" : "Sides"}
          </Link>
        ))}
      </div>

      {all.length > 0 || archived ? (
        <>
          <label htmlFor={searchId} className="sr-only">
            Search {role === "main" ? "mains" : "sides"}
          </label>
          <input
            id={searchId}
            type="search"
            value={query}
            placeholder={role === "main" ? "Search mains" : "Search sides"}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            className="mb-3 min-h-12 w-full rounded-button border-2 border-rule bg-paper px-4 text-body"
          />
          <div className="mb-5 flex flex-wrap gap-2">
            {OCCASIONS.map((item) => (
              <Chip
                key={item.value}
                on={occasion === item.value}
                onClick={() => {
                  setOccasion(occasion === item.value ? null : item.value);
                }}
              >
                {item.label}
              </Chip>
            ))}
            <Chip
              on={favorites}
              onClick={() => {
                setFavorites(!favorites);
              }}
            >
              <Star aria-hidden="true" className="size-4" />
              Favorites
            </Chip>
          </div>
        </>
      ) : null}

      {dishes.isError ? (
        <p className="text-body">{errorMessage(dishes.error)}</p>
      ) : dishes.isPending ? null : shown.length > 0 ? (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {shown.map((card) => (
            <MealCard key={card.id} card={card} />
          ))}
        </ul>
      ) : all.length > 0 ? (
        <p className="text-body">Nothing matches. Try another word or clear a filter.</p>
      ) : archived ? (
        <p className="text-body">Nothing archived.</p>
      ) : role === "main" ? (
        <EmptyState
          message="Your meals live here. Start with a dinner you make often."
          action={
            <Button onClick={() => void navigate({ to: "/meals/new", search: { role: "main" } })}>
              New meal
            </Button>
          }
        />
      ) : (
        <EmptyState
          message="Sides go with any main. Add rice, a salad, anything you serve alongside."
          action={
            <Button onClick={() => void navigate({ to: "/meals/new", search: { role: "side" } })}>
              New side
            </Button>
          }
        />
      )}

      <div className="mt-6">
        <Button
          variant="quiet"
          onClick={() => {
            setArchived(!archived);
          }}
        >
          {archived ? `Back to ${role === "main" ? "mains" : "sides"}` : "Show archived"}
        </Button>
      </div>
    </Screen>
  );
}

/**
 * The household's own photo may be cropped to 4:3; Kroger's photos never are, so they sit as
 * small whole tiles that wrap rather than clip. The star sits beside the text, never on a photo.
 */
export function MealCard({ card }: { card: DishCard }) {
  const cost = costLine(card.cost);
  return (
    <li className="relative flex flex-col overflow-hidden rounded-tile border border-rule bg-paper">
      <Link to="/meals/$dishId" params={{ dishId: card.id }} className="flex flex-1 flex-col">
        {card.photo_url ? (
          <img src={card.photo_url} alt="" className="aspect-[4/3] w-full object-cover" />
        ) : (
          <div className="flex aspect-[4/3] w-full flex-wrap content-center items-center justify-center gap-1 bg-counter p-2">
            {card.item_images.length > 0 ? (
              card.item_images.map((src) => <ProductImage key={src} src={src} alt="" size={40} />)
            ) : (
              <ProductImage src={null} alt="" size={40} />
            )}
          </div>
        )}
        <div className="flex flex-1 flex-col py-2 pr-12 pl-3">
          <span className="text-body leading-tight font-semibold">{card.name}</span>
          <span className="text-secondary text-ink-soft">{cost.total}</span>
        </div>
      </Link>
      <div className="absolute right-0 bottom-0">
        <FavoriteButton id={card.id} name={card.name} favorite={card.favorite} />
      </div>
    </li>
  );
}

export function FavoriteButton({
  id,
  name,
  favorite,
}: {
  id: string;
  name: string;
  favorite: boolean;
}) {
  const queryClient = useQueryClient();
  const toggle = useMutation({
    mutationFn: async (next: boolean) =>
      unwrap(
        await api.PATCH("/api/dishes/{dish_id}", {
          params: { path: { dish_id: id } },
          body: { favorite: next },
        }),
      ),
    onSuccess: async (dish) => {
      queryClient.setQueryData(qk.dish(id), dish);
      await queryClient.invalidateQueries({ queryKey: qk.dishes() });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const on = toggle.isPending ? toggle.variables : favorite;
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={on ? `${name} is a favorite` : `Make ${name} a favorite`}
      onClick={() => {
        toggle.mutate(!on);
      }}
      className="marker-carrot flex size-12 items-center justify-center rounded-button text-ink-soft aria-pressed:text-[var(--marker)]"
    >
      <Star aria-hidden="true" className={on ? "fill-current" : ""} />
    </button>
  );
}
