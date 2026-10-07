import { Link, type LinkProps } from "@tanstack/react-router";
import { CalendarDays, ChefHat, ListChecks, Menu, type LucideIcon } from "lucide-react";

import { BellMark } from "./BellMark";

interface Tab {
  to: NonNullable<LinkProps["to"]>;
  label: string;
  icon: LucideIcon;
}

const TABS: Tab[] = [
  { to: "/", label: "Plan", icon: CalendarDays },
  { to: "/meals", label: "Meals", icon: ChefHat },
  { to: "/list", label: "List", icon: ListChecks },
  { to: "/more", label: "More", icon: Menu },
];

/** Bottom tabs on phones; a left rail from 1024 px (docs/UX.md §3). */
export function TabBar() {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-paper pb-[env(safe-area-inset-bottom)] print:hidden lg:inset-y-0 lg:right-auto lg:w-60 lg:border-t-0 lg:border-r lg:pb-0"
    >
      <div className="hidden items-center gap-3 px-6 pt-8 pb-6 lg:flex">
        <BellMark className="size-10" />
        <span className="text-row font-extrabold">Dinner Bell</span>
      </div>
      <ul className="mx-auto flex max-w-xl lg:flex-col lg:gap-1 lg:px-3">
        {TABS.map(({ to, label, icon: Icon }) => (
          <li key={label} className="flex-1 lg:flex-none">
            <Link
              to={to}
              activeOptions={{ exact: to === "/" }}
              // data-status="active" is set by the router; the variant always beats the base color.
              className="flex min-h-(--tabbar-h) flex-col items-center justify-center gap-1 text-secondary font-semibold text-ink-soft data-[status=active]:text-basil lg:min-h-14 lg:flex-row lg:justify-start lg:gap-3 lg:rounded-button lg:px-4 lg:text-body lg:data-[status=active]:bg-counter"
            >
              <Icon aria-hidden="true" size={26} strokeWidth={2.25} />
              <span>{label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
