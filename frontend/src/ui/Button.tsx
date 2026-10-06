import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "quiet" | "danger" | "quiet-danger";

const VARIANTS: Record<Variant, string> = {
  primary: "min-h-14 bg-basil text-on-basil",
  secondary: "min-h-12 border-2 border-rule bg-paper text-ink",
  quiet: "min-h-12 text-basil underline-offset-4 hover:underline",
  danger: "min-h-12 border-2 border-rule bg-paper text-tomato",
  "quiet-danger": "min-h-12 text-tomato underline-offset-4 hover:underline",
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
