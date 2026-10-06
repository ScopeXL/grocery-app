import type { ReactNode } from "react";

/**
 * Empty screens teach: what goes here, and the one button that starts it (docs/UX.md §6).
 * The ruled lines below the copy echo the paper list on the fridge.
 */
export function EmptyState({
  message,
  note,
  action,
}: {
  message: string;
  note?: string;
  action?: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-tile border border-rule bg-paper">
      <div className="p-6">
        <p className="text-row font-semibold">{message}</p>
        {action ? <div className="mt-5">{action}</div> : null}
        {note ? <p className="mt-4 text-secondary text-ink-soft">{note}</p> : null}
      </div>
      <div aria-hidden="true" className="ruled-lines h-24 border-t border-rule" />
    </section>
  );
}
