/**
 * Rename an item (docs/UX.md §4.10, §4.11): the new name shows wherever the item is used, in
 * meals and on this week's list. A Saved list keeps the name it was saved with. The toast offers
 * Undo, which puts the old name back.
 *
 * Goes in a two-column grid after the photo and the item's facts: the Rename button lines up
 * with the facts, and the field takes the full width below.
 */
import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";

async function saveName(queryClient: QueryClient, itemId: string, name: string) {
  const item = unwrap(
    await api.PATCH("/api/items/{item_id}", {
      params: { path: { item_id: itemId } },
      body: { name },
    }),
  );
  // Item names show in the item list, in meals and on the plan's lines.
  for (const queryKey of [qk.items(), qk.dishes(), qk.plan()]) {
    void queryClient.invalidateQueries({ queryKey });
  }
  return item;
}

export function RenameItem({ itemId, name }: { itemId: string; name: string }) {
  const queryClient = useQueryClient();
  const fieldId = useId();
  // null until Rename is tapped; then what's in the field.
  const [text, setText] = useState<string | null>(null);
  const field = useRef<HTMLInputElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const wasRenaming = useRef(false);
  const renaming = text !== null;

  useEffect(() => {
    if (renaming) field.current?.focus();
    else if (wasRenaming.current) opener.current?.focus();
    wasRenaming.current = renaming;
  }, [renaming]);

  const rename = useMutation({
    mutationFn: ({ next }: { next: string; before: string }) => saveName(queryClient, itemId, next),
    onSuccess: (item, { before }) => {
      setText(null);
      showToast(`Renamed to ${item.name}`, {
        label: "Undo",
        onAction: () => {
          saveName(queryClient, itemId, before).catch((failure: unknown) => {
            showToast(errorMessage(failure));
          });
        },
      });
    },
  });

  if (!renaming) {
    return (
      <Button
        ref={opener}
        variant="quiet"
        className="col-start-2 -ml-5 justify-self-start"
        aria-label={`Rename ${name}`}
        onClick={() => {
          rename.reset();
          setText(name);
        }}
      >
        Rename
      </Button>
    );
  }
  return (
    <form
      className="col-span-2 mt-3 flex flex-col"
      onSubmit={(event) => {
        event.preventDefault();
        const next = text.trim();
        if (!next) return;
        if (next === name) setText(null);
        else rename.mutate({ next, before: name });
      }}
    >
      <label htmlFor={fieldId} className="text-body font-semibold">
        What do you call it?
      </label>
      <input
        ref={field}
        id={fieldId}
        value={text}
        maxLength={80}
        autoComplete="off"
        enterKeyHint="done"
        aria-describedby={`${fieldId}-help`}
        onChange={(event) => {
          setText(event.target.value);
        }}
        className="mt-2 min-h-12 w-full rounded-button border-2 border-rule bg-paper px-4 text-body"
      />
      <p id={`${fieldId}-help`} className="mt-1 text-secondary text-ink-soft">
        This name shows on your list and in your meals.
      </p>
      <p role="alert" className="min-h-6 text-secondary font-semibold text-tomato">
        {rename.isError ? errorMessage(rename.error) : null}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" pending={rename.isPending} disabled={!text.trim()}>
          Save name
        </Button>
        <Button
          variant="quiet"
          onClick={() => {
            setText(null);
          }}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}
