import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "quiet" | "danger" | "quiet-danger";

const VARIANTS: Record<Variant, string> = {
  primary: "min-h-12 bg-accent text-on-accent",
  secondary: "min-h-11 border-2 border-rule bg-paper text-ink",
  // Quiet buttons are ink text, so the underline is what says "tap me" (ADR 0027).
  quiet: "min-h-11 text-accent underline decoration-ink-soft/60 decoration-2 underline-offset-4",
  danger: "min-h-11 border-2 border-rule bg-paper text-tomato",
  "quiet-danger":
    "min-h-11 text-tomato underline decoration-tomato/40 decoration-2 underline-offset-4",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  block?: boolean;
}

export function Button({ variant = "primary", block = false, className, ...props }: ButtonProps) {
  const classes = [
    "inline-flex items-center justify-center gap-2 rounded-button px-5 text-body font-semibold",
    "transition-colors disabled:cursor-not-allowed disabled:opacity-60",
    VARIANTS[variant],
    block ? "w-full" : "",
    className ?? "",
  ].join(" ");
  return <button type="button" className={classes} {...props} />;
}
