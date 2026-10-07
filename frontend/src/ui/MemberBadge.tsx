/** A member's initial in their marker color. Color is never the only signal (docs/UX.md §7.2). */
const SIZES = {
  md: "size-10 border-[3px] text-row",
  sm: "size-6 border-2 text-caption",
} as const;

export function MemberBadge({
  name,
  color,
  size = "md",
}: {
  name: string;
  color: string;
  size?: keyof typeof SIZES;
}) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      aria-hidden="true"
      className={`marker-${color} inline-flex ${SIZES[size]} shrink-0 items-center justify-center rounded-full border-[var(--marker)] font-extrabold text-[var(--marker)]`}
    >
      {initial}
    </span>
  );
}
