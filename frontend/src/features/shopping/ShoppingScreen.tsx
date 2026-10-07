/**
 * Shopping mode (UX §4.12): full screen, from Start shopping. It works with no signal: the saved
 * list lives on this phone, every tap goes into the outbox, and the screen shows the server's
 * state with this phone's unsent taps laid on top (lib/tripView). Other phones' check-offs
 * arrive live.
 */
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronDown, ChevronLeft } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { qk } from "../../api/keys";
import type { components } from "../../api/schema";
import { useStore } from "../../lib/store";
import { connection } from "../../lib/connection";
import { about } from "../../lib/money";
import { outbox, useOutboxStatus } from "../../lib/outbox";
import { fetchSession } from "../../lib/session";
import { clearToasts, showToast } from "../../lib/toast";
import { downloadTrip } from "../../lib/trips";
import { useTripView, type Grouping, type TripView } from "../../lib/tripView";
import { useChangeCount } from "../../lib/motion";
import { useKeepAwake, wakeLockState } from "../../lib/wakeLock";
import { Button } from "../../ui/Button";
import { Segmented, segmentOption } from "../../ui/Segmented";
import { ToastAnchor } from "../../ui/ToastAnchor";
import { underlined } from "../../ui/styles";
import { FinishedElsewhere } from "./FinishedElsewhere";
import { FinishSheet } from "./FinishSheet";
import { ItemSheet } from "./ItemSheet";
import { ReadyCard } from "./ReadyCard";
import { ShopperPick } from "./ShopperPick";
import { ShopRow } from "./ShopRow";

type TripItem = components["schemas"]["TripItemOut"];
const GROUPING_KEY = "dinnerbell.shop.grouping";
// A row just checked here stays while its stroke draws, then folds away (styles/motion.css's
// exit time) and moves to Done.
const STRIKE_MS = 250;
const FOLD_MS = 180;

/** A row just checked off on this phone: which check-off, and whether it's folding away yet. */
interface Linger {
  checkOff: number;
  folding: boolean;
}
const SLOW_SYNC_MS = 1500;

function savedGrouping(): Grouping {
  try {
    return localStorage.getItem(GROUPING_KEY) === "meal" ? "meal" : "aisle";
  } catch {
    return "aisle";
  }
}

export function ShoppingScreen({ tripId }: { tripId: string }) {
  const navigate = useNavigate();
  const [grouping, setGrouping] = useState<Grouping>(savedGrouping);
  const session = useQuery({ queryKey: qk.session(), queryFn: fetchSession });
  const me = session.data?.member ?? null;
  const [lingering, setLingering] = useState<Record<string, Linger>>({});
  const checkOffs = useRef(0);
  const lingeringIds = useMemo(() => new Set(Object.keys(lingering)), [lingering]);
  // Unsent check-offs are this phone's, so they draw in this person's color.
  const view = useTripView(tripId, grouping, { me: me?.id ?? null, lingering: lingeringIds });
  const reachable = useStore(connection).server !== "unreachable";
  const [openId, setOpenId] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [downloaded, setDownloaded] = useState<"pending" | "ok" | "failed">("pending");
  useKeepAwake(view?.status === "active");
  // "18 of 31" pops once when it changes (styles/motion.css); hooks come before the early return.
  const progressChanges = useChangeCount(view ? view.doneCount + view.missed.length : null);
  // Check-off toasts (with their Undo) belong to this screen.
  useEffect(() => clearToasts, []);

  useEffect(() => {
    let cancelled = false;
    void downloadTrip(tripId)
      .then((trip) => {
        if (!cancelled) setDownloaded(trip ? "ok" : "failed");
      })
      .catch(() => {
        if (!cancelled) setDownloaded("failed");
      });
    return () => {
      cancelled = true;
    };
  }, [tripId]);

  const [finishedHere, setFinishedHere] = useState(false);
  const memberOf = useMemo(() => {
    const members = new Map((view?.trip.members ?? []).map((m) => [m.id, m]));
    return (id: string | null) => (id ? (members.get(id) ?? null) : null);
  }, [view?.trip.members]);

  if (!view) {
    return (
      <Shell onBack={() => void navigate({ to: "/list" })}>
        <p className="text-body">
          {downloaded === "pending"
            ? "Getting the list…"
            : reachable
              ? "That saved list couldn't be found."
              : "Open this trip once with signal to save it on this phone."}
        </p>
      </Shell>
    );
  }

  const items = view.trip.items;
  const open = openId ? (items[openId] ?? null) : null;
  const handled = view.doneCount + view.missed.length;
  const checker = (item: TripItem) => {
    if (item.state !== "done") return null;
    const member = memberOf(item.state_by) ?? (pendingFor(view, item.id) ? me : null);
    return member ? { color: member.marker_color, name: member.name } : null;
  };

  const setState = (item: TripItem, state: TripItem["state"]) => {
    const before = item.state;
    void outbox.setState(tripId, item.id, state);
    setOpenId(null);
    if (state === "done") {
      // Each step checks it's still this check-off: an uncheck and a new check start over.
      const checkOff = ++checkOffs.current;
      setLingering((current) => ({ ...current, [item.id]: { checkOff, folding: false } }));
      setTimeout(() => {
        setLingering((current) =>
          current[item.id]?.checkOff === checkOff
            ? { ...current, [item.id]: { checkOff, folding: true } }
            : current,
        );
      }, STRIKE_MS);
      setTimeout(() => {
        setLingering((current) =>
          current[item.id]?.checkOff === checkOff
            ? Object.fromEntries(Object.entries(current).filter(([id]) => id !== item.id))
            : current,
        );
      }, STRIKE_MS + FOLD_MS);
    }
    const message =
      state === "done"
        ? `Checked off ${item.name}`
        : state === "missed"
          ? `${item.name}: couldn’t find`
          : `${item.name} is back on the list`;
    showToast(message, {
      label: "Undo",
      onAction: () => {
        void outbox.setState(tripId, item.id, before);
      },
    });
  };

  const groups = view.groups;

  return (
    <main className="mx-auto min-h-dvh w-full max-w-3xl pb-44">
      <header className="sticky top-0 z-10 border-b border-rule bg-paper px-4 pt-[calc(env(safe-area-inset-top)+8px)] pb-3">
        <div className="flex items-center justify-between gap-3">
          <Button variant="quiet" className="-ml-5" onClick={() => void navigate({ to: "/list" })}>
            <ChevronLeft aria-hidden="true" />
            Done shopping
          </Button>
          <span
            key={progressChanges}
            className={`text-row font-bold${progressChanges > 0 ? " pop" : ""}`}
            data-testid="progress"
          >
            {String(handled)} of {String(view.total)}
          </span>
        </div>
        <progress
          aria-label="Progress"
          className="trip-progress my-2"
          value={handled}
          max={Math.max(view.total, 1)}
        />
        <div className="flex items-center justify-between gap-3">
          <Segmented label="Group the list">
            {(["aisle", "meal"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={grouping === value}
                onClick={() => {
                  setGrouping(value);
                  try {
                    localStorage.setItem(GROUPING_KEY, value);
                  } catch {
                    // A private window may refuse storage; the choice just isn't remembered.
                  }
                }}
                className={segmentOption}
              >
                {value === "aisle" ? "By aisle" : "By meal"}
              </button>
            ))}
          </Segmented>
          <StatusNote />
        </div>
      </header>

      <div className="px-4 pt-4">
        <ReadyCard tripId={tripId} view={view} downloaded={downloaded} />
        {groups.map((group) => (
          <section key={group.key} aria-label={group.label} className="mb-6">
            <h2 className="mb-2 text-row font-bold">{group.label}</h2>
            <ul className="overflow-hidden rounded-tile border border-rule bg-paper">
              {group.items.map((item) => (
                <ShopRow
                  key={item.id}
                  item={item}
                  checkedBy={checker(item)}
                  striking={item.id in lingering}
                  folding={item.state === "done" && lingering[item.id]?.folding === true}
                  onCheck={() => {
                    setState(item, item.state === "done" ? "todo" : "done");
                  }}
                  onOpen={() => {
                    setOpenId(item.id);
                  }}
                />
              ))}
            </ul>
          </section>
        ))}
        {groups.length === 0 && view.status === "active" ? (
          <p className="mb-6 text-body">
            Everything is checked off. Finish the trip when you’re done.
          </p>
        ) : null}
        <Collapsed label="Done" count={view.done.length}>
          {view.done.map((item) => (
            <ShopRow
              key={item.id}
              item={item}
              checkedBy={checker(item)}
              striking={false}
              onCheck={() => {
                setState(item, "todo");
              }}
              onOpen={() => {
                setOpenId(item.id);
              }}
            />
          ))}
        </Collapsed>
        <Collapsed label="Couldn’t find" count={view.missed.length} open>
          {view.missed.map((item) => (
            <ShopRow
              key={item.id}
              item={item}
              checkedBy={null}
              striking={false}
              onCheck={() => {
                setState(item, "done");
              }}
              onOpen={() => {
                setOpenId(item.id);
              }}
            />
          ))}
        </Collapsed>
      </div>

      <footer className="fixed inset-x-0 bottom-0 z-10 border-t border-rule bg-paper px-4 pt-2 pb-[calc(env(safe-area-inset-bottom)+8px)]">
        <ToastAnchor />
        <div className="mx-auto flex max-w-3xl flex-col gap-2">
          <p className="text-body" data-testid="in-cart">
            {view.inCartCents > 0
              ? `In cart ${about(view.inCartCents)} of ${about(view.estimateCents)}`
              : `Nothing in the cart yet, ${about(view.estimateCents)} in all`}
          </p>
          <Button
            block
            disabled={view.status !== "active"}
            onClick={() => {
              setFinishing(true);
            }}
          >
            Finish trip
          </Button>
        </div>
      </footer>

      <ItemSheet
        item={open}
        onClose={() => {
          setOpenId(null);
        }}
        onState={setState}
        onNote={(item, note) => {
          void outbox.setNote(tripId, item.id, note);
          setOpenId(null);
          showToast(note ? "Note saved" : "Note removed");
        }}
      />
      <FinishSheet
        open={finishing}
        onClose={() => {
          setFinishing(false);
        }}
        onFinish={(paid) => {
          setFinishedHere(true);
          void outbox.finish(tripId, paid);
          setFinishing(false);
          void navigate({ to: "/trips" }).then(() => showToast("Trip finished"));
        }}
      />
      <ShopperPick />
      <FinishedElsewhere
        view={view}
        me={me?.id ?? null}
        finishedByMe={finishedHere}
        memberName={(id) => memberOf(id)?.name ?? "Someone"}
        onDone={() => void navigate({ to: "/trips" })}
        onReopen={() => {
          void outbox.reopen(tripId);
        }}
      />
    </main>
  );
}

function pendingFor(view: TripView, itemId: string): boolean {
  // A row checked a moment ago is still in its group (lingering), not in Done yet.
  const shown = [...view.done, ...view.groups.flatMap((group) => group.items)];
  return (
    view.trip.items[itemId] !== undefined &&
    shown.some((i) => i.id === itemId && i.state === "done" && i.pending)
  );
}

/**
 * The header's quiet status (UX §4.12): offline (with what's saved here), syncing (only if it
 * takes a moment, so taps don't flicker it), sign in to sync, or that the screen stays on.
 */
function StatusNote() {
  const wake = useStore(wakeLockState);
  const { showOffline } = useStore(connection);
  const { pending, signedOut } = useOutboxStatus();
  // "Syncing" only once the same taps have waited a moment.
  const [waitedFor, setWaitedFor] = useState<number | null>(null);
  useEffect(() => {
    if (pending === 0) return;
    const timer = setTimeout(() => {
      setWaitedFor(pending);
    }, SLOW_SYNC_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [pending]);
  const slow = pending > 0 && waitedFor === pending;
  let note: ReactNode = wake.active ? "Screen stays on" : null;
  if (signedOut && pending > 0) {
    note = (
      <Link
        to="/sign-in"
        className={`inline-flex min-h-11 items-center font-semibold text-accent ${underlined}`}
      >
        Sign in to sync
      </Link>
    );
  } else if (showOffline) {
    note = pending > 0 ? "Offline, saved on this phone" : "Offline";
  } else if (pending > 0 && slow) {
    note = `Syncing ${String(pending)}…`;
  }
  return (
    <span role="status" aria-live="polite" className="text-caption text-ink-soft">
      {note}
    </span>
  );
}

function Collapsed({
  label,
  count,
  open = false,
  children,
}: {
  label: string;
  count: number;
  open?: boolean;
  children: ReactNode;
}) {
  if (count === 0) return null;
  return (
    <details open={open} className="group mb-6">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-row font-bold">
        <ChevronDown aria-hidden="true" className="transition-transform group-open:rotate-180" />
        {label} ({String(count)})
      </summary>
      <ul className="mt-2 overflow-hidden rounded-tile border border-rule bg-paper">{children}</ul>
    </details>
  );
}

function Shell({ children, onBack }: { children: ReactNode; onBack: () => void }) {
  return (
    <main className="mx-auto max-w-3xl px-4 pt-[calc(env(safe-area-inset-top)+16px)]">
      <Button variant="quiet" className="-ml-5 mb-4" onClick={onBack}>
        <ChevronLeft aria-hidden="true" />
        Back to the list
      </Button>
      {children}
    </main>
  );
}
