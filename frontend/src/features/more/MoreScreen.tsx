import { Link, type LinkProps } from "@tanstack/react-router";
import { ChevronRight, Info, Settings, Smartphone, UserRound, type LucideIcon } from "lucide-react";

import { Screen } from "../../ui/Screen";

interface Row {
  label: string;
  icon: LucideIcon;
  to: NonNullable<LinkProps["to"]>;
  search?: { from: "more" };
}

const ROWS: Row[] = [
  { label: "Settings", icon: Settings, to: "/settings" },
  { label: "Who’s using this", icon: UserRound, to: "/who" },
  { label: "Install the app", icon: Smartphone, to: "/install", search: { from: "more" } },
  { label: "About & privacy", icon: Info, to: "/about" },
];

export function MoreScreen() {
  return (
    <Screen title="More">
      <ul className="rounded-tile border border-rule bg-paper">
        {ROWS.map(({ label, icon: Icon, to, search }) => (
          <li key={label} className="border-b border-rule last:border-b-0">
            <Link
              to={to}
              {...(search ? { search } : {})}
              className="flex min-h-16 items-center gap-4 px-4 text-body font-semibold"
            >
              <Icon aria-hidden="true" className="text-basil" />
              <span className="flex-1">{label}</span>
              <ChevronRight aria-hidden="true" className="text-ink-soft" />
            </Link>
          </li>
        ))}
      </ul>
    </Screen>
  );
}
