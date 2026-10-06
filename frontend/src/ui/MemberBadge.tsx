/** A member's initial in their marker color. Color is never the only signal (docs/UX.md §7.2). */
export function MemberBadge({ name, color }: { name: string; color: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span
      aria-hidden="true"
      className={`marker-${color} inline-flex size-11 shrink-0 items-center justify-center rounded-full border-[3px] border-[var(--marker)] text-row font-extrabold text-[var(--marker)]`}
    >
      {initial}
    </span>
  );
}
