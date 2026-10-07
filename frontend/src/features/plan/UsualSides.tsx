/**
 * A Main's usual sides (UX §4.7): learned from what gets planned with it, and editable. Saving
 * keeps exactly the sides chosen; any others stay out however often they're picked.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";
import { ToggleRow } from "./ToggleRow";
import { joinNames } from "./types";

export function UsualSides({ mainId }: { mainId: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [chosen, setChosen] = useState<string[]>([]);
  const usual = useQuery({
    queryKey: qk.usualSides(mainId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/dishes/{dish_id}/usual-sides", {
          params: { path: { dish_id: mainId } },
        }),
      ),
  });
  const sides = useQuery({
    queryKey: qk.dishList("side", false),
    queryFn: async () =>
      unwrap(await api.GET("/api/dishes", { params: { query: { role: "side" } } })),
    enabled: editing,
  });
  const save = useMutation({
    mutationFn: async (ids: string[]) =>
      unwrap(
        await api.PUT("/api/dishes/{dish_id}/usual-sides", {
          params: { path: { dish_id: mainId } },
          body: { side_ids: ids },
        }),
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData(qk.usualSides(mainId), saved);
      setEditing(false);
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const names = (usual.data ?? []).map((side) => side.name);

  return (
    <section className="mb-6">
      <h2 className="mb-2 text-row font-bold">Usual sides</h2>
      <p className={names.length > 0 ? "text-body" : "text-secondary text-ink-soft"}>
        {names.length > 0
          ? joinNames(names)
          : "None yet. Sides you plan with this meal show up here."}
      </p>
      <Button
        variant="quiet"
        className="-ml-5"
        onClick={() => {
          setChosen((usual.data ?? []).map((side) => side.id));
          setEditing(true);
        }}
      >
        Change usual sides
      </Button>
      <Sheet
        open={editing}
        title="Usual sides"
        onClose={() => {
          setEditing(false);
        }}
        footer={
          <Button
            block
            disabled={save.isPending}
            onClick={() => {
              save.mutate(chosen);
            }}
          >
            Save
          </Button>
        }
      >
        <p className="mb-4 text-secondary text-ink-soft">
          These come first when you add this meal to the plan.
        </p>
        {sides.data?.length === 0 ? (
          <p className="text-body">No sides yet. Make one in Meals first.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {(sides.data ?? []).map((side) => (
              <ToggleRow
                key={side.id}
                on={chosen.includes(side.id)}
                label={side.name}
                onClick={() => {
                  setChosen(
                    chosen.includes(side.id)
                      ? chosen.filter((id) => id !== side.id)
                      : [...chosen, side.id],
                  );
                }}
              />
            ))}
          </div>
        )}
      </Sheet>
    </section>
  );
}
