import type { ReactNode } from "react";

/** A toggle chip (occasions, days, filters); pressed, it fills with the accent (ink, ADR 0027). */
export function Chip({
  on,
  onClick,
  children,
  disabled = false,
}: {
  on: boolean;
  onClick: () => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex min-h-12 items-center gap-1 rounded-full border-2 border-rule bg-paper px-4 text-secondary font-semibold disabled:opacity-60 aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
    >
      {children}
    </button>
  );
}
