/**
 * What shopping mode shows (docs/PLAN.md §9.4, docs/UX.md §4.12): the trip as the server last
 * told us, with this phone's unsent actions laid on top. Pure, so it's cheap to recompute and
 * easy to test. When an op leaves the outbox its overlay goes with it, so rollback needs no code.
 *
 * An unsent action shows only where the server will accept it: the server keeps the newest
 * action per field (PLAN §9.2), so one older than what's already there would be superseded,
 * and showing it would only make the row flicker.
 */
import { useMemo } from "react";

import { usePendingOps, type PendingOp } from "./outbox";
import {
  useLocalTrip,
  type LocalTrip,
  type TripHeader,
  type TripItemOut,
  type TripStatus,
} from "./trips";

export type Grouping = "aisle" | "meal";

/** An item as the screen shows it; `pending` when this phone has an unsent change for it. */
export type ViewItem = TripItemOut & { pending: boolean };

export interface ViewGroup {
  key: string;
  label: string;
  items: ViewItem[];
}

export interface TripView {
  /** The trip as the server last confirmed it (members, items by id, the plain header). */
  trip: LocalTrip;
  /** The header, with an unsent finish or reopen laid on top. */
  header: TripHeader;
  status: TripStatus;
  /** A finish or reopen is waiting to be sent ("will sync"). */
  statusPending: boolean;
  /** To-do items (and any lingering ones): sections in walking order, or meals. */
  groups: ViewGroup[];
  /** Checked off, the most recent first; a lingering row joins once it has folded away. */
  done: ViewItem[];
  /** Couldn't find, in walking order. */
  missed: ViewItem[];
  /** "18 of 31" is doneCount of total. */
  doneCount: number;
  missedCount: number;
  /** Done plus couldn't find: both count as handled for progress. */
  handledCount: number;
  /** Items on the list; removed ones don't count. */
  total: number;
  /** What the checked items cost: "In cart about $64". */
  inCartCents: number;
  estimateCents: number;
  /** Actions this phone hasn't sent yet, for this trip. */
  pendingCount: number;
}

export interface ViewOptions {
  /** The member using this phone: unsent check-offs are drawn as theirs. */
  me?: string | null | undefined;
  /**
   * Rows checked off on this phone a moment ago: they keep their place in their section or meal
   * while the marker stroke draws and the row folds away (UX §7.6), and join Done after.
   */
  lingering?: ReadonlySet<string> | undefined;
}

export const OTHER_SECTION = { key: "cat:other", label: "Other" } as const;
export const OTHER_MEAL = { key: "meal:none", label: "Other things" } as const;

function compareText(a: string, b: string): number {
  const x = a.toLowerCase();
  const y = b.toLowerCase();
  if (x === y) return 0;
  return x < y ? -1 : 1;
}

/** The household's walk through the store: section, then shelf, then name. */
export function walkingOrder(a: TripItemOut, b: TripItemOut): number {
  return (
    a.section_order - b.section_order ||
    a.bay - b.bay ||
    compareText(a.name, b.name) ||
    compareText(a.id, b.id)
  );
}

function listOrder(a: TripItemOut, b: TripItemOut): number {
  return a.position - b.position || compareText(a.id, b.id);
}

function mostRecentFirst(a: TripItemOut, b: TripItemOut): number {
  return b.state_ts - a.state_ts || walkingOrder(a, b);
}

function byAisle(todo: readonly ViewItem[]): ViewGroup[] {
  const groups = new Map<string, ViewGroup>();
  for (const item of [...todo].sort(walkingOrder)) {
    const key = item.section_key ?? OTHER_SECTION.key;
    let group = groups.get(key);
    if (!group) {
      group = { key, label: item.section_label ?? OTHER_SECTION.label, items: [] };
      groups.set(key, group);
    }
    group.items.push(item);
  }
  return [...groups.values()];
}

/** Each item under its first meal; meals in the order they first appear down the list. */
function byMeal(todo: readonly ViewItem[], everything: readonly ViewItem[]): ViewGroup[] {
  const order = new Map<string, number>();
  for (const item of [...everything].sort(listOrder)) {
    for (const use of item.used_by) if (!order.has(use.meal_id)) order.set(use.meal_id, order.size);
  }
  const groups = new Map<string, ViewGroup & { rank: number }>();
  const other: ViewItem[] = [];
  for (const item of [...todo].sort(walkingOrder)) {
    const meal = item.used_by[0];
    if (!meal) {
      other.push(item);
      continue;
    }
    let group = groups.get(meal.meal_id);
    if (!group) {
      const rank = order.get(meal.meal_id) ?? order.size;
      group = { key: `meal:${meal.meal_id}`, label: meal.name, items: [], rank };
      groups.set(meal.meal_id, group);
    }
    group.items.push(item);
  }
  const ordered: ViewGroup[] = [...groups.values()]
    .sort((a, b) => a.rank - b.rank)
    .map(({ key, label, items }) => ({ key, label, items }));
  if (other.length > 0) ordered.push({ ...OTHER_MEAL, items: other });
  return ordered;
}

export function deriveView(
  trip: LocalTrip,
  pending: readonly PendingOp[],
  grouping: Grouping,
  options: ViewOptions = {},
): TripView {
  const me = options.me ?? null;
  const items = new Map<string, ViewItem>();
  for (const item of Object.values(trip.items)) {
    if (!item.removed) items.set(item.id, { ...item, pending: false });
  }

  let { status, status_ts: statusTs, actual_total_cents: actualTotal } = trip.header;
  let statusPending = false;
  const mine = pending
    .filter((op) => op.trip_id === trip.header.id)
    .sort((a, b) => a.client_seq - b.client_seq);
  for (const op of mine) {
    switch (op.kind) {
      case "item.set_state": {
        const item = items.get(op.item_id);
        if (item && op.client_ts >= item.state_ts) {
          items.set(item.id, {
            ...item,
            state: op.state,
            state_ts: op.client_ts,
            state_by: me,
            pending: true,
          });
        }
        break;
      }
      case "item.set_note": {
        const item = items.get(op.item_id);
        if (item && op.client_ts >= item.note_ts) {
          items.set(item.id, {
            ...item,
            note: op.note,
            note_ts: op.client_ts,
            note_by: me,
            pending: true,
          });
        }
        break;
      }
      case "trip.finish":
        if (status === "finished") {
          // Finished already: the first finish stands, but it can still learn what was paid.
          if (actualTotal === null && op.actual_total_cents !== null) {
            actualTotal = op.actual_total_cents;
            statusPending = true;
          }
        } else if (op.client_ts >= statusTs) {
          status = "finished";
          statusTs = op.client_ts;
          actualTotal = op.actual_total_cents ?? actualTotal;
          statusPending = true;
        }
        break;
      case "trip.reopen":
        if (status === "finished" && op.client_ts >= statusTs) {
          status = "active";
          statusTs = op.client_ts;
          statusPending = true;
        }
        break;
    }
  }

  const lingering = options.lingering ?? new Set<string>();
  const everything = [...items.values()];
  const checked = everything.filter((item) => item.state === "done");
  const listed = everything.filter(
    (item) => item.state === "todo" || (item.state === "done" && lingering.has(item.id)),
  );
  const done = checked.filter((item) => !lingering.has(item.id)).sort(mostRecentFirst);
  const missed = everything.filter((item) => item.state === "missed").sort(walkingOrder);
  const header: TripHeader = statusPending
    ? { ...trip.header, status, status_ts: statusTs, actual_total_cents: actualTotal }
    : trip.header;

  return {
    trip,
    header,
    status,
    statusPending,
    groups: grouping === "aisle" ? byAisle(listed) : byMeal(listed, everything),
    done,
    missed,
    doneCount: checked.length,
    missedCount: missed.length,
    handledCount: checked.length + missed.length,
    total: everything.length,
    inCartCents: checked.reduce((sum, item) => sum + (item.line_cents ?? 0), 0),
    estimateCents: trip.header.estimate_cents,
    pendingCount: mine.length,
  };
}

/** The trip as shopping mode shows it, or undefined while it isn't on this phone. */
export function useTripView(
  tripId: string,
  grouping: Grouping,
  options: ViewOptions = {},
): TripView | undefined {
  const trip = useLocalTrip(tripId);
  const pending = usePendingOps(tripId);
  const me = options.me ?? null;
  const lingering = options.lingering;
  return useMemo(
    () => (trip ? deriveView(trip, pending, grouping, { me, lingering }) : undefined),
    [trip, pending, grouping, me, lingering],
  );
}
