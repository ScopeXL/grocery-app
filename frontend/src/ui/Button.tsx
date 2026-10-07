import { LoaderCircle } from "lucide-react";
import type { ComponentPropsWithRef } from "react";

type Variant = "primary" | "secondary" | "quiet" | "danger" | "quiet-danger";

// Each press also shades the button (motion.css adds the dip).
const VARIANTS: Record<Variant, string> = {
  primary: "min-h-12 bg-accent text-on-accent active:opacity-85",
  secondary: "min-h-11 border-2 border-rule bg-paper text-ink active:bg-counter",
  // Quiet buttons are ink text, so the underline is what says "tap me" (ADR 0027).
  quiet:
    "min-h-11 text-accent underline decoration-ink-soft/60 decoration-2 underline-offset-4 active:opacity-70",
  danger: "min-h-11 border-2 border-rule bg-paper text-tomato active:bg-counter",
  "quiet-danger":
    "min-h-11 text-tomato underline decoration-tomato/40 decoration-2 underline-offset-4 active:opacity-70",
};

export interface ButtonProps extends ComponentPropsWithRef<"button"> {
  variant?: Variant;
  block?: boolean;
  /** Waiting on the server: the button is disabled, says it's busy, and shows a spinner. */
  pending?: boolean;
}

export function Button({
  variant = "primary",
  block = false,
  pending = false,
  className,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const classes = [
    "press inline-flex items-center justify-center gap-2 rounded-button px-5 text-body font-semibold",
    "disabled:cursor-not-allowed disabled:opacity-60",
    VARIANTS[variant],
    block ? "w-full" : "",
    className ?? "",
  ].join(" ");
  return (
    <button
      type="button"
      className={classes}
      disabled={disabled === true || pending}
      aria-busy={pending || undefined}
      {...props}
    >
      {pending ? (
        <LoaderCircle aria-hidden="true" className="size-5 shrink-0 animate-spin" />
      ) : null}
      {children}
    </button>
  );
}
