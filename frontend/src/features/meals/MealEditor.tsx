/**
 * Create or edit a Main or a Side (docs/UX.md §4.8). A new meal is guided one step at a time;
 * an edit shows every part at once. Either way the draft is saved on this phone at every
 * change, so closing the app loses nothing (UX §1).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Camera, ChevronLeft, Plus } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { clearDraft, loadDraft, saveDraft } from "../../lib/drafts";
import { arrivals } from "../../lib/motion";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { Skeleton } from "../../ui/Skeleton";
import { underlined } from "../../ui/styles";
import { AddItemSheet } from "./AddItemSheet";
import { AmountPicker } from "./AmountPicker";
import {
  asDraft,
  emptyDraft,
  fromDish,
  STEP,
  STEP_COUNT,
  type Draft,
  type DraftLine,
} from "./draft";
import { uploadPhoto } from "./photos";
import type { ItemOut, Role } from "./types";

function lineBody(lines: DraftLine[]) {
  return lines.map((line) => ({
    item_id: line.item.id,
    amount: { kind: line.amount.kind, value: line.amount.value, unit: line.amount.unit },
  }));
}

export function NewMealScreen({
  role,
  first,
}: {
  role: Role | undefined;
  first: boolean | undefined;
}) {
  return <MealEditor draftKey="meal.new" initial={() => emptyDraft(role)} first={first ?? false} />;
}

export function EditMealScreen({ dishId }: { dishId: string }) {
  const dish = useQuery({
    queryKey: qk.dish(dishId),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes/{dish_id}", { params: { path: { dish_id: dishId } } })),
  });
  if (dish.isError) return <p className="p-6 text-body">{errorMessage(dish.error)}</p>;
  if (!dish.data) {
    return (
      <main className="mx-auto w-full max-w-2xl px-4 pt-12">
        <Skeleton rows={4} />
      </main>
    );
  }
  const loaded = dish.data;
  return (
    <MealEditor
      draftKey={`meal.edit.${dishId}`}
      dishId={dishId}
      initial={() => fromDish(loaded)}
      first={false}
    />
  );
}

function MealEditor({
  draftKey,
  dishId,
  initial,
  first,
}: {
  draftKey: string;
  dishId?: string;
  initial: () => Draft;
  first: boolean;
}) {
  const editing = dishId !== undefined;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [restored] = useState(() => asDraft(loadDraft(draftKey)));
  const [draft, setDraft] = useState<Draft>(() => restored ?? initial());
  const [adding, setAdding] = useState(false);
  const [picking, setPicking] = useState<{ item: ItemOut; line: DraftLine | null } | null>(null);
  // Lines keep a copy of their item; its name may have changed since (a rename, or another phone).
  const items = useQuery({
    queryKey: qk.items(),
    queryFn: async () => unwrap(await api.GET("/api/items")),
  });
  const names = new Map((items.data ?? []).map((item) => [item.id, item.name]));
  const nameOf = (line: DraftLine) => names.get(line.item.id) ?? line.item.name;

  useEffect(() => {
    saveDraft(draftKey, draft);
  }, [draftKey, draft]);

  const update = (changes: Partial<Draft>) => {
    setDraft((current) => ({ ...current, ...changes }));
  };

  const save = useMutation({
    mutationFn: async () => {
      const fields = {
        name: draft.name.trim(),
        servings: draft.servings ? Number(draft.servings) : null,
        notes: draft.notes.trim() || null,
        recipe_url: draft.recipeUrl.trim() || null,
        photo_id: draft.photoId,
      };
      if (!editing) {
        return unwrap(
          await api.POST("/api/dishes", {
            body: {
              ...fields,
              role: draft.role ?? "main",
              favorite: false,
              lines: lineBody(draft.lines),
            },
          }),
        );
      }
      const path = { params: { path: { dish_id: dishId } } };
      unwrap(
        await api.PATCH("/api/dishes/{dish_id}", {
          ...path,
          body: { ...fields, role: draft.role ?? "main" },
        }),
      );
      return unwrap(
        await api.PUT("/api/dishes/{dish_id}/lines", {
          ...path,
          body: { lines: lineBody(draft.lines) },
        }),
      );
    },
    onSuccess: async (dish) => {
      clearDraft(draftKey);
      queryClient.setQueryData(qk.dish(dish.id), dish);
      await queryClient.invalidateQueries({ queryKey: qk.dishes() });
      showToast("Meal saved");
      if (first) await navigate({ to: "/welcome", search: { step: "done" } });
      else await navigate({ to: "/meals/$dishId", params: { dishId: dish.id } });
    },
  });

  const canSave = draft.name.trim().length > 0 && draft.role !== null && !save.isPending;
  const step = editing ? STEP_COUNT : draft.step;
  const show = (index: number) => editing || step === index;
  const next = () => {
    update({ step: Math.min(draft.step + 1, STEP_COUNT - 1) });
  };

  const removeLine = (line: DraftLine) => {
    const at = draft.lines.indexOf(line);
    update({ lines: draft.lines.filter((other) => other !== line) });
    showToast(`Removed ${nameOf(line)}`, {
      label: "Undo",
      onAction: () => {
        setDraft((current) => {
          const lines = [...current.lines];
          lines.splice(Math.min(at, lines.length), 0, line);
          return { ...current, lines };
        });
      },
    });
  };

  return (
    <main className="mx-auto w-full max-w-2xl px-4 pt-[calc(env(safe-area-inset-top)+16px)] pb-40">
      <Link
        to={editing ? "/meals/$dishId" : "/meals"}
        params={editing ? { dishId } : {}}
        className="mb-2 inline-flex min-h-11 items-center gap-1 text-body font-semibold text-accent"
      >
        <ChevronLeft aria-hidden="true" />
        {editing ? "Back to the meal" : "Meals"}
      </Link>
      <h1 className={`text-title font-extrabold ${editing ? "mb-6" : "mb-1"}`}>
        {editing ? `Edit ${draft.name || "meal"}` : "New meal"}
      </h1>
      {!editing ? (
        <p className="mb-6 text-secondary text-ink-soft">
          Step {String(step + 1)} of {String(STEP_COUNT)}
        </p>
      ) : null}
      {restored && !editing ? (
        <p className="mb-4 rounded-tile bg-counter p-3 text-secondary">
          Picking up where you left off.{" "}
          <button
            type="button"
            className={`font-semibold text-accent ${underlined}`}
            onClick={() => {
              clearDraft(draftKey);
              setDraft(initial());
            }}
          >
            Start over
          </button>
        </p>
      ) : null}

      {show(STEP.name) ? (
        <Step title="What do you call it?">
          <NameField
            value={draft.name}
            onChange={(name) => {
              update({ name });
            }}
            onSubmit={editing ? undefined : next}
          />
        </Step>
      ) : null}

      {show(STEP.role) ? (
        <Step title="Is it a main or a side?">
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                ["main", "Main", "The center of a meal, like tacos or chili."],
                ["side", "Side", "Goes with a main, like rice or a salad."],
              ] as const
            ).map(([value, label, hint]) => (
              <button
                key={value}
                type="button"
                aria-pressed={draft.role === value}
                onClick={() => {
                  update({ role: value, step: editing ? draft.step : STEP.items });
                }}
                className="press-row flex min-h-16 flex-col items-start justify-center rounded-button border-2 border-rule bg-paper px-4 py-3 text-left aria-pressed:border-accent"
              >
                <span className="text-row font-bold">{label}</span>
                <span className="text-secondary text-ink-soft">{hint}</span>
              </button>
            ))}
          </div>
        </Step>
      ) : null}

      {show(STEP.items) ? (
        <Step title="What goes in it?">
          {draft.lines.length > 0 ? (
            <ul
              ref={arrivals}
              className="mb-3 overflow-hidden rounded-tile border border-rule bg-paper"
            >
              {draft.lines.map((line) => (
                <li key={line.key} className="border-b border-rule px-3 py-2 last:border-b-0">
                  <div className="flex items-center gap-3">
                    <ProductImage src={line.item.image_url} alt="" size={48} />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="text-body font-semibold">{nameOf(line)}</span>
                      <span className="text-secondary text-ink-soft">{line.amount.text}</span>
                    </span>
                  </div>
                  {/* Actions get their own line: at phone width they can't share one with the name. */}
                  <div className="flex gap-1 pl-12">
                    <Button
                      variant="quiet"
                      aria-label={`Change ${nameOf(line)}`}
                      onClick={() => {
                        setPicking({ item: line.item, line });
                      }}
                    >
                      Change
                    </Button>
                    <Button
                      variant="quiet-danger"
                      aria-label={`Remove ${nameOf(line)}`}
                      onClick={() => {
                        removeLine(line);
                      }}
                    >
                      Remove
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mb-3 text-secondary text-ink-soft">
              Add what you buy for it. Each item remembers its product for next time.
            </p>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              setAdding(true);
            }}
          >
            <Plus aria-hidden="true" />
            Add an item
          </Button>
        </Step>
      ) : null}

      {show(STEP.extras) ? (
        <Step title="Anything else? (optional)">
          <Extras draft={draft} update={update} />
        </Step>
      ) : null}

      <p role="alert" className="min-h-7 text-secondary font-semibold text-tomato">
        {save.isError ? errorMessage(save.error) : null}
      </p>

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-rule bg-paper px-4 pt-2 pb-[calc(env(safe-area-inset-bottom)+8px)]">
        <div className="mx-auto flex max-w-2xl gap-2">
          {!editing && step > 0 ? (
            <Button
              variant="secondary"
              onClick={() => {
                update({ step: step - 1 });
              }}
            >
              Back
            </Button>
          ) : null}
          {!editing && step < STEP_COUNT - 1 ? (
            <Button
              block
              className="flex-1"
              disabled={
                (step === STEP.name && !draft.name.trim()) ||
                (step === STEP.role && draft.role === null)
              }
              onClick={next}
            >
              Next
            </Button>
          ) : (
            <Button
              block
              className="flex-1"
              disabled={!canSave}
              pending={save.isPending}
              onClick={() => {
                save.mutate();
              }}
            >
              {save.isPending ? "Saving…" : "Save meal"}
            </Button>
          )}
        </div>
      </div>

      <AddItemSheet
        open={adding}
        onClose={() => {
          setAdding(false);
        }}
        onPicked={(item) => {
          setAdding(false);
          setPicking({ item, line: null });
        }}
      />
      {picking ? (
        <AmountPicker
          key={picking.item.id + (picking.line?.key ?? "")}
          open
          item={picking.item}
          initial={picking.line?.amount ?? null}
          onClose={() => {
            setPicking(null);
          }}
          onDone={(amount) => {
            const { item, line } = picking;
            setDraft((current) => ({
              ...current,
              lines: line
                ? current.lines.map((other) =>
                    other.key === line.key ? { ...other, amount } : other,
                  )
                : [...current.lines, { key: crypto.randomUUID(), item, amount }],
            }));
            setPicking(null);
          }}
        />
      ) : null}
    </main>
  );
}

function Step({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-row font-bold">{title}</h2>
      {children}
    </section>
  );
}

function NameField({
  value,
  onChange,
  onSubmit,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (() => void) | undefined;
}) {
  const id = useId();
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (value.trim()) onSubmit?.();
      }}
    >
      <label htmlFor={id} className="sr-only">
        Meal name
      </label>
      <input
        id={id}
        value={value}
        maxLength={80}
        autoComplete="off"
        enterKeyHint="next"
        placeholder="For example, Tacos"
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="min-h-12 w-full rounded-button border-2 border-rule bg-paper px-4 text-row"
      />
    </form>
  );
}

function Extras({ draft, update }: { draft: Draft; update: (changes: Partial<Draft>) => void }) {
  const file = useRef<HTMLInputElement>(null);
  const ids = { servings: useId(), notes: useId(), recipe: useId() };
  const upload = useMutation({
    mutationFn: uploadPhoto,
    onSuccess: (photo) => {
      update({ photoId: photo.id });
    },
  });
  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="mb-2 text-body font-semibold">Photo</p>
        {draft.photoId ? (
          <img
            src={`/api/photos/${draft.photoId}/thumb`}
            alt="The meal"
            className="mb-2 aspect-[4/3] w-full max-w-sm rounded-tile border border-rule object-cover"
          />
        ) : null}
        <input
          ref={file}
          type="file"
          accept="image/*"
          className="sr-only"
          aria-label="Choose a photo"
          onChange={(event) => {
            const chosen = event.target.files?.[0];
            if (chosen) upload.mutate(chosen);
            event.target.value = "";
          }}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={upload.isPending}
            onClick={() => {
              file.current?.click();
            }}
          >
            <Camera aria-hidden="true" />
            {upload.isPending ? "Saving photo…" : draft.photoId ? "Change photo" : "Add a photo"}
          </Button>
          {draft.photoId ? (
            <Button
              variant="quiet-danger"
              onClick={() => {
                update({ photoId: null });
              }}
            >
              Remove photo
            </Button>
          ) : null}
        </div>
        {upload.isError ? (
          <p className="mt-2 text-secondary text-tomato">{errorMessage(upload.error)}</p>
        ) : null}
      </div>
      <label htmlFor={ids.servings} className="flex flex-col gap-1 text-body font-semibold">
        Servings
        <input
          id={ids.servings}
          value={draft.servings}
          inputMode="numeric"
          onChange={(event) => {
            update({ servings: event.target.value.replace(/\D/g, "").slice(0, 2) });
          }}
          className="min-h-12 w-24 rounded-button border-2 border-rule bg-paper px-3 font-normal"
        />
      </label>
      <label htmlFor={ids.notes} className="flex flex-col gap-1 text-body font-semibold">
        Notes
        <textarea
          id={ids.notes}
          value={draft.notes}
          rows={3}
          maxLength={2000}
          onChange={(event) => {
            update({ notes: event.target.value });
          }}
          className="rounded-button border-2 border-rule bg-paper px-3 py-2 font-normal"
        />
      </label>
      <label htmlFor={ids.recipe} className="flex flex-col gap-1 text-body font-semibold">
        Recipe link
        <input
          id={ids.recipe}
          value={draft.recipeUrl}
          type="url"
          inputMode="url"
          placeholder="https://"
          onChange={(event) => {
            update({ recipeUrl: event.target.value.slice(0, 500) });
          }}
          className="min-h-12 rounded-button border-2 border-rule bg-paper px-3 font-normal"
        />
      </label>
    </div>
  );
}
