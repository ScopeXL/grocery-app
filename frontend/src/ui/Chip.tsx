import type { ReactNode } from "react";

/** A toggle chip (occasions, days, filters): a 48 px target; pressed state in basil. */
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
      className="inline-flex min-h-12 items-center gap-1 rounded-full border-2 border-rule bg-paper px-4 text-secondary font-semibold disabled:opacity-60 aria-pressed:border-basil aria-pressed:bg-basil aria-pressed:text-on-basil"
    >
      {children}
    </button>
  );
}
