/**
 * Extras (UX §4.11): what was added outside meals, with who added it; the Usuals row for
 * one-tap re-adds; and Add something else (the household's items, Kroger's products, or plain
 * text, through the same sheet meals use).
 */
import { Plus } from "lucide-react";
import { useState } from "react";

import { api, unwrap } from "../../api/client";
import { arrivals } from "../../lib/motion";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { Chip } from "../../ui/Chip";
import { MemberBadge } from "../../ui/MemberBadge";
import { AddItemSheet } from "../meals/AddItemSheet";
import type { Line, PlanOut } from "../plan/types";
import { usePlanChange } from "../plan/usePlan";
import { LineRow } from "./LineRow";

export function ExtrasSection({
  plan,
  lines,
  onOpen,
}: {
  plan: PlanOut;
  lines: Line[];
  onOpen: (key: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const addExtra = usePlanChange(
    async (body: { item_id?: string; text?: string; name: string }) =>
      unwrap(
        await api.POST("/api/plan/extras", {
          body: body.item_id
            ? { item_id: body.item_id, quantity: "1" }
            : { text: body.text ?? body.name, quantity: "1" },
        }),
      ),
    (_plan, { name }) => showToast(`${name} added`),
  );

  return (
    <section aria-label="Extras" className="mb-8">
      <h2 className="mb-3 text-row font-bold">Extras</h2>
      {lines.length > 0 ? (
        <ul
          ref={arrivals}
          className="mb-4 overflow-hidden rounded-tile border border-rule bg-paper"
        >
          {lines.map((line) => (
            <ExtraLine key={line.key} line={line} onOpen={onOpen} />
          ))}
        </ul>
      ) : (
        <p className="mb-4 text-secondary text-ink-soft">
          Things like milk or paper towels, added outside meals.
        </p>
      )}

      {plan.usuals.length > 0 ? (
        <div className="mb-4">
          <h3 className="mb-2 text-body font-bold">Usuals</h3>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Usuals">
            {plan.usuals.map((usual) => (
              <Chip
                key={usual.item_id ?? `text:${usual.name}`}
                disabled={addExtra.isPending}
                onClick={() => {
                  addExtra.mutate(
                    usual.item_id
                      ? { item_id: usual.item_id, name: usual.name }
                      : { text: usual.text ?? usual.name, name: usual.name },
                  );
                }}
              >
                <Plus aria-hidden="true" className="size-4" />
                {usual.name}
              </Chip>
            ))}
          </div>
        </div>
      ) : null}

      <Button
        variant="secondary"
        block
        onClick={() => {
          setAdding(true);
        }}
      >
        <Plus aria-hidden="true" />
        Add something else
      </Button>
      <AddItemSheet
        open={adding}
        title="Add something else"
        confirmLabel="Add to list"
        onClose={() => {
          setAdding(false);
        }}
        onPicked={(item) => {
          setAdding(false);
          addExtra.mutate({ item_id: item.id, name: item.name });
        }}
      />
    </section>
  );
}

/** An extra's line: like any line, plus who added it. */
function ExtraLine({ line, onOpen }: { line: Line; onOpen: (key: string) => void }) {
  const people = line.extras.flatMap((extra) => (extra.added_by ? [extra.added_by] : []));
  const first = people[0];
  return (
    <LineRow
      line={line}
      onOpen={onOpen}
      note={
        first ? (
          <span className="mt-1 flex items-center gap-2 text-secondary text-ink-soft">
            <MemberBadge name={first.name} color={first.marker_color} size="sm" />
            Added by {first.name}
          </span>
        ) : null
      }
    />
  );
}
