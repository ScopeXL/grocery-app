import { Check } from "lucide-react";

/** An on/off row (sides): the whole row is the target, 56 px tall. */
export function ToggleRow({
  on,
  label,
  onClick,
  disabled = false,
}: {
  on: boolean;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      disabled={disabled}
      onClick={onClick}
      className="flex min-h-14 w-full items-center gap-3 rounded-button border-2 border-rule bg-paper px-3 text-left text-body font-semibold disabled:opacity-60 aria-pressed:border-accent"
    >
      <span
        aria-hidden="true"
        className={`flex size-6 shrink-0 items-center justify-center rounded-md border-2 ${
          on ? "border-accent bg-accent text-on-accent" : "border-rule"
        }`}
      >
        {on ? <Check className="size-4" strokeWidth={3} /> : null}
      </span>
      {label}
    </button>
  );
}
