/**
 * One trip (UX §4.15): what was bought, what couldn't be found and what was left, with the
 * estimate against what was paid. Shop this again makes a new saved list of the same items at
 * today's prices; Plan these meals again adds that week's meals to this week; Reopen goes back
 * to shopping it; Share as text sends the list to anyone without the app.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, ShoppingCart } from "lucide-react";
import { useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import type { components } from "../../api/schema";
import { about, cents } from "../../lib/money";
import { outbox } from "../../lib/outbox";
import { shareText, tripText } from "../../lib/shareText";
import { showToast } from "../../lib/toast";
import { rememberTrip } from "../../lib/trips";
import { useTripView } from "../../lib/tripView";
import { Button } from "../../ui/Button";
import { Screen } from "../../ui/Screen";
import { Skeleton } from "../../ui/Skeleton";
import { SendToCartSheet } from "../cart/SendToCartSheet";
import { useKrogerAccount } from "../kroger/account";
import { tripDate } from "./TripsScreen";

type TripItem = components["schemas"]["TripItemOut"];

export function TripDetailScreen({ tripId }: { tripId: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sending, setSending] = useState(false);
  const account = useKrogerAccount();
  const trip = useQuery({
    queryKey: qk.trip(tripId),
    queryFn: async () =>
      unwrap(await api.GET("/api/trips/{trip_id}", { params: { path: { trip_id: tripId } } })),
  });
  // The trip as this phone has it, with a finish or reopen still being sent on top: the server
  // can lag behind on a weak signal, and its answer mustn't swap the buttons under a finger.
  const local = useTripView(tripId, "aisle");
  const again = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/trips/{trip_id}/shop-again", {
          params: { path: { trip_id: tripId } },
        }),
      ),
    onSuccess: async (fresh) => {
      await rememberTrip(fresh);
      void queryClient.invalidateQueries({ queryKey: qk.trips() });
      showToast("New saved list ready");
      await navigate({ to: "/shop/$tripId", params: { tripId: fresh.id } });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const replan = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/plan/repeat", { body: { trip_id: tripId } })),
    onSuccess: async (plan) => {
      queryClient.setQueryData(qk.plan(), plan);
      showToast("Those meals are on this week's plan");
      await navigate({ to: "/" });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });

  if (!trip.data) {
    return (
      <Screen title="Trip">
        {trip.isError ? (
          <p className="text-body">{errorMessage(trip.error)}</p>
        ) : (
          <Skeleton rows={5} />
        )}
      </Screen>
    );
  }
  const data = trip.data;
  const finished = (local?.status ?? data.status) === "finished";
  const title = `Shopping list, ${tripDate(data.created_at)}`;
  const items = data.items.filter((item) => !item.removed);
  const groups: [string, TripItem[]][] = [
    ["Bought", items.filter((item) => item.state === "done")],
    ["Couldn't find", items.filter((item) => item.state === "missed")],
    [finished ? "Not bought" : "Still to get", items.filter((item) => item.state === "todo")],
  ];

  return (
    <Screen title={finished ? tripDate(data.finished_at ?? data.created_at) : title}>
      <Link
        to="/trips"
        className="-mt-4 mb-3 inline-flex min-h-11 items-center gap-1 text-body font-semibold text-accent"
      >
        <ChevronLeft aria-hidden="true" />
        Trips
      </Link>
      <div className="mb-5 flex flex-col text-body">
        {data.store_name ? <span className="text-ink-soft">{data.store_name}</span> : null}
        <span>Estimate: {about(data.estimate_cents)}</span>
        {data.actual_total_cents !== null ? (
          <span className="font-semibold">Paid {cents(data.actual_total_cents)}</span>
        ) : null}
      </div>

      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {finished ? (
          <>
            <Button
              disabled={again.isPending}
              onClick={() => {
                again.mutate();
              }}
            >
              Shop this again
            </Button>
            {data.plan_id ? (
              <Button
                variant="secondary"
                disabled={replan.isPending}
                onClick={() => {
                  replan.mutate();
                }}
              >
                Plan these meals again
              </Button>
            ) : null}
            <Button
              variant="secondary"
              onClick={() => {
                void rememberTrip(data)
                  .then(() => outbox.reopen(tripId))
                  .then(() => navigate({ to: "/shop/$tripId", params: { tripId } }));
              }}
            >
              Reopen
            </Button>
          </>
        ) : (
          <>
            <Button onClick={() => void navigate({ to: "/shop/$tripId", params: { tripId } })}>
              Start shopping
            </Button>
            {account.data &&
            (account.data.status !== "disconnected" || account.data.can_connect) ? (
              <Button
                variant="secondary"
                onClick={() => {
                  setSending(true);
                }}
              >
                <ShoppingCart aria-hidden="true" />
                Send to Kroger cart
              </Button>
            ) : null}
          </>
        )}
        <Button
          variant="quiet"
          onClick={() => {
            void shareText(title, tripText(title, items)).then((how) => {
              if (how === "copied") showToast("List copied");
            });
          }}
        >
          Share as text
        </Button>
      </div>

      {!finished ? (
        <SendToCartSheet
          tripId={tripId}
          open={sending}
          onClose={() => {
            setSending(false);
          }}
        />
      ) : null}
      {groups.map(([label, group]) =>
        group.length > 0 ? (
          <section key={label} aria-label={label} className="mb-6">
            <h2 className="mb-2 text-row font-bold">
              {label} ({String(group.length)})
            </h2>
            <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
              {group.map((item) => (
                <li
                  key={item.id}
                  className="flex min-h-14 items-baseline gap-3 border-b border-rule px-4 py-2 last:border-b-0"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-body font-semibold">{item.name}</span>
                    <span className="text-secondary text-ink-soft">{item.qty_text}</span>
                    {item.note ? (
                      <span className="text-secondary text-ink-soft">“{item.note}”</span>
                    ) : null}
                  </span>
                  <span className="shrink-0 text-secondary">
                    {item.line_cents !== null ? about(item.line_cents) : "no price"}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null,
      )}
    </Screen>
  );
}
