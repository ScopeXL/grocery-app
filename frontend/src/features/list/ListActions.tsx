/**
 * The List's bottom bar (UX §4.11): Save list freezes the list into a saved list; then Start
 * shopping. When the plan changes after saving, Update saved list brings the saved list up to
 * date (what's checked off stays). On a computer, Print sits beside them.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Printer } from "lucide-react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { rememberTrip } from "../../lib/trips";
import { enable as enableWakeLock } from "../../lib/wakeLock";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { TotalFooter } from "../plan/TotalFooter";
import type { PlanOut } from "../plan/types";

export function ListActions({ plan }: { plan: PlanOut }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const trip = plan.trip;
  const save = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/trips")),
    onSuccess: async (saved) => {
      await rememberTrip(saved);
      showToast(trip ? "Saved list updated" : "List saved");
      await queryClient.invalidateQueries({ queryKey: qk.plan() });
      void queryClient.invalidateQueries({ queryKey: qk.trips() });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const print = (
    // A wrapper, because Button's own inline-flex would beat "hidden" (CSS order).
    <div className="hidden lg:block">
      <Button
        variant="secondary"
        onClick={() => {
          window.print();
        }}
      >
        <Printer aria-hidden="true" />
        Print
      </Button>
    </div>
  );

  return (
    <div className="flex w-full flex-col gap-2">
      <TotalFooter plan={plan} compact />
      {trip?.stale ? (
        <p className="text-caption text-ink-soft">The list changed since you saved it.</p>
      ) : null}
      <div className="flex gap-2">
        {trip ? (
          <>
            <Button
              className="flex-1"
              onClick={() => {
                enableWakeLock(); // from the tap itself: browsers want a user gesture
                void navigate({ to: "/shop/$tripId", params: { tripId: trip.id } });
              }}
            >
              Start shopping
            </Button>
            {trip.stale ? (
              <Button
                variant="secondary"
                disabled={save.isPending}
                onClick={() => {
                  save.mutate();
                }}
              >
                Update saved list
              </Button>
            ) : null}
          </>
        ) : (
          <Button
            className="flex-1"
            disabled={save.isPending || plan.lines.length === 0}
            onClick={() => {
              save.mutate();
            }}
          >
            Save list
          </Button>
        )}
        {print}
      </div>
    </div>
  );
}
