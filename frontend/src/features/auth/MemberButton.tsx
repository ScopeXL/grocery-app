import { Check } from "lucide-react";

import type { Member } from "../../lib/session";
import { MemberBadge } from "../../ui/MemberBadge";

/**
 * A person to pick, with their badge (Who's using this phone?, Who's shopping?). Whoever already
 * uses this phone is pressed: an ink border, a check and "Using this phone", so it's clear
 * without opening Settings (docs/UX.md §4.2).
 */
export function MemberButton({
  member,
  chosen,
  disabled,
  onChoose,
}: {
  member: Pick<Member, "name" | "marker_color">;
  /** Whether this person uses this phone; left out where nobody is picked yet. */
  chosen?: boolean;
  disabled?: boolean;
  onChoose: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={chosen}
      disabled={disabled}
      onClick={onChoose}
      className="press-row flex min-h-14 w-full items-center gap-4 rounded-button border-2 border-rule bg-paper px-4 py-2 text-left disabled:opacity-60 aria-pressed:border-accent"
    >
      <MemberBadge name={member.name} color={member.marker_color} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-row font-semibold">{member.name}</span>
        {chosen ? <span className="text-secondary text-ink-soft">Using this phone</span> : null}
      </span>
      {chosen ? <Check aria-hidden="true" className="size-6 shrink-0 text-accent" /> : null}
    </button>
  );
}
