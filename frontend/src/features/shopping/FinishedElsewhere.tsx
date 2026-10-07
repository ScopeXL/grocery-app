/**
 * Another phone finished this trip (UX §4.12): a calm sheet, never an error. This phone's
 * check-offs were saved, since late ones still count for a day.
 */
import { useState } from "react";

import type { TripView } from "../../lib/tripView";
import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";

export function FinishedElsewhere({
  view,
  me,
  finishedByMe,
  memberName,
  onDone,
  onReopen,
}: {
  view: TripView;
  me: string | null;
  finishedByMe: boolean;
  memberName: (id: string | null) => string;
  onDone: () => void;
  onReopen: () => void;
}) {
  const [dismissedAt, setDismissedAt] = useState<number | null>(null);
  const header = view.trip.header;
  const show =
    view.status === "finished" &&
    !finishedByMe &&
    header.status_by !== me &&
    dismissedAt !== header.status_ts;
  const mine = Object.values(view.trip.items).filter(
    (item) => item.state === "done" && me !== null && item.state_by === me,
  ).length;
  return (
    <Sheet
      open={show}
      title="Trip finished"
      onClose={() => {
        setDismissedAt(header.status_ts);
        onDone();
      }}
      footer={
        <div className="flex gap-2">
          <Button
            className="flex-1"
            onClick={() => {
              setDismissedAt(header.status_ts);
              onDone();
            }}
          >
            Done
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setDismissedAt(header.status_ts);
              onReopen();
            }}
          >
            Reopen
          </Button>
        </div>
      }
    >
      <p className="text-body">{memberName(header.status_by)} finished this trip.</p>
      {mine > 0 ? (
        <p className="mt-2 text-body">
          Your {String(mine)} check-off{mine === 1 ? " was" : "s were"} saved.
        </p>
      ) : null}
    </Sheet>
  );
}
