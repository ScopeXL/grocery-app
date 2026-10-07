import type { ReactNode } from "react";

/**
 * Two choices side by side, one chosen: By aisle / By meal, Mains / Sides (ADR 0027 sizes).
 * Options are buttons (`aria-pressed`) or links (`aria-current="page"`) styled with
 * `segmentOption`; the chosen one fills with the accent.
 */
export const segmentOption =
  "flex min-h-10 items-center justify-center rounded-lg px-3 text-secondary font-semibold aria-pressed:bg-accent aria-pressed:text-on-accent aria-[current=page]:bg-accent aria-[current=page]:text-on-accent";

export function Segmented({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={`segmented grid grid-cols-2 rounded-button border-2 border-rule bg-paper p-1 ${className}`}
    >
      {children}
    </div>
  );
}
