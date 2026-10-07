/**
 * Trips (UX §4.15): saved lists still being shopped, then finished trips, newest first, each
 * with its date, store, how many items, and the estimate against what was paid.
 */
import { useInfiniteQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import type { components } from "../../api/schema";
import { about, cents } from "../../lib/money";
import { usePendingOps } from "../../lib/outbox";
import { useLocalTrips } from "../../lib/trips";
import { Button } from "../../ui/Button";
import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";
import { Skeleton } from "../../ui/Skeleton";

type TripHeader = components["schemas"]["TripHeader"];

export function tripDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function TripsScreen() {
  const pages = useInfiniteQuery({
    queryKey: qk.tripHistory(null),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/trips", {
          params: { query: pageParam ? { before: pageParam } : {} },
        }),
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.more ? (last.finished.at(-1)?.finished_at ?? null) : null),
  });
  const local = useLocalTrips();
  const pending = usePendingOps();
  // Offline, the lists saved on this phone stand in for the server's (never an error wall).
  const offline = pages.isError;
  const first = pages.data?.pages[0];
  const serverActive = offline
    ? local.filter((t) => t.header.status === "active").map((t) => t.header)
    : (first?.active ?? []);
  const serverFinished = offline
    ? local.filter((t) => t.header.status === "finished").map((t) => t.header)
    : (pages.data?.pages.flatMap((page) => page.finished) ?? []);
  // A finish or reopen tapped on this phone shows at once, marked until it's sent.
  const latestStatus = new Map<string, "trip.finish" | "trip.reopen">();
  for (const op of pending) {
    if (op.kind === "trip.finish" || op.kind === "trip.reopen")
      latestStatus.set(op.trip_id, op.kind);
  }
  const willSync = new Set(latestStatus.keys());
  const all = [...serverActive, ...serverFinished];
  const active = all.filter((trip) => statusOf(trip, latestStatus) === "active");
  const finished = all.filter((trip) => statusOf(trip, latestStatus) === "finished");

  return (
    <Screen title="Trips">
      {offline && all.length > 0 ? (
        <p className="mb-4 text-secondary text-ink-soft">Showing what’s saved on this phone.</p>
      ) : null}
      {pages.isPending && !offline ? (
        <Skeleton shape="lines" rows={3} />
      ) : all.length === 0 ? (
        offline ? (
          <p className="text-body">{errorMessage(pages.error)}</p>
        ) : (
          <EmptyState message="Saved lists show up here after you shop." />
        )
      ) : (
        <>
          {active.length > 0 ? (
            <section aria-label="Saved lists" className="mb-8">
              <h2 className="mb-2 text-row font-bold">Saved lists</h2>
              <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
                {active.map((trip) => (
                  <TripRow key={trip.id} trip={trip} active willSync={willSync.has(trip.id)} />
                ))}
              </ul>
            </section>
          ) : null}
          {finished.length > 0 ? (
            <section aria-label="Finished trips">
              <h2 className="mb-2 text-row font-bold">Finished</h2>
              <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
                {finished.map((trip) => (
                  <TripRow
                    key={trip.id}
                    trip={trip}
                    active={false}
                    willSync={willSync.has(trip.id)}
                  />
                ))}
              </ul>
              {pages.hasNextPage ? (
                <Button
                  variant="quiet"
                  className="mt-3 -ml-5"
                  disabled={pages.isFetchingNextPage}
                  onClick={() => void pages.fetchNextPage()}
                >
                  Show older trips
                </Button>
              ) : null}
            </section>
          ) : null}
        </>
      )}
    </Screen>
  );
}

function statusOf(
  trip: TripHeader,
  latest: Map<string, "trip.finish" | "trip.reopen">,
): "active" | "finished" {
  const op = latest.get(trip.id);
  if (op === "trip.finish") return "finished";
  if (op === "trip.reopen") return "active";
  return trip.status;
}

function TripRow({
  trip,
  active,
  willSync,
}: {
  trip: TripHeader;
  active: boolean;
  willSync: boolean;
}) {
  const handled = trip.done_count + trip.missed_count;
  return (
    <li className="border-b border-rule last:border-b-0">
      <Link
        to={active ? "/shop/$tripId" : "/trips/$tripId"}
        params={{ tripId: trip.id }}
        className="flex min-h-14 items-center gap-3 px-4 py-3"
      >
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-body font-semibold">
            {active
              ? `Saved ${tripDate(trip.created_at)}`
              : tripDate(trip.finished_at ?? trip.created_at)}
          </span>
          {trip.store_name ? (
            <span className="text-secondary text-ink-soft">{trip.store_name}</span>
          ) : null}
          <span className="text-secondary text-ink-soft">
            {active
              ? `${String(handled)} of ${String(trip.item_count)} done`
              : `${String(trip.item_count)} item${trip.item_count === 1 ? "" : "s"}`}
          </span>
        </span>
        <span className="flex shrink-0 flex-col items-end text-secondary">
          <span>{about(trip.estimate_cents)}</span>
          {trip.actual_total_cents !== null ? (
            <span className="font-semibold">{cents(trip.actual_total_cents)} paid</span>
          ) : null}
          {willSync ? <span className="text-caption text-ink-soft">Will sync</span> : null}
        </span>
        <ChevronRight aria-hidden="true" className="text-ink-soft" />
      </Link>
    </li>
  );
}
