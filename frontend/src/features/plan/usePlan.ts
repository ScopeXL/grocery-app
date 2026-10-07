/**
 * This week's plan, and changes to it. Every change answers with the whole fresh plan, so the
 * Plan and List screens update from the response; other phones hear `plan.changed`.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { showToast } from "../../lib/toast";
import type { PlanOut } from "./types";

export function usePlan() {
  return useQuery({
    queryKey: qk.plan(),
    queryFn: async () => unwrap(await api.GET("/api/plan")),
  });
}

export function usePlanChange<V>(
  run: (variables: V) => Promise<PlanOut>,
  onDone?: (plan: PlanOut, variables: V) => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (plan, variables) => {
      queryClient.setQueryData(qk.plan(), plan);
      onDone?.(plan, variables);
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
}

/** Removing a meal or an extra offers Undo, never a confirmation (UX §1). */
export function useRemoveMeal() {
  const restore = usePlanChange(async (mealId: string) =>
    unwrap(
      await api.POST("/api/plan/meals/{meal_id}/restore", {
        params: { path: { meal_id: mealId } },
      }),
    ),
  );
  return usePlanChange(
    async ({ id }: { id: string; name: string }) =>
      unwrap(await api.DELETE("/api/plan/meals/{meal_id}", { params: { path: { meal_id: id } } })),
    (_plan, { id, name }) => {
      showToast(`${name} removed`, {
        label: "Undo",
        onAction: () => {
          restore.mutate(id);
        },
      });
    },
  );
}

export function useRemoveExtra() {
  const restore = usePlanChange(async (extraId: string) =>
    unwrap(
      await api.POST("/api/plan/extras/{extra_id}/restore", {
        params: { path: { extra_id: extraId } },
      }),
    ),
  );
  return usePlanChange(
    async ({ id }: { id: string; name: string }) =>
      unwrap(
        await api.DELETE("/api/plan/extras/{extra_id}", { params: { path: { extra_id: id } } }),
      ),
    (_plan, { id, name }) => {
      showToast(`${name} removed`, {
        label: "Undo",
        onAction: () => {
          restore.mutate(id);
        },
      });
    },
  );
}
