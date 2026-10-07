import { useQuery } from "@tanstack/react-query";
import { Link, type LinkProps } from "@tanstack/react-router";
import {
  ChevronRight,
  History,
  Info,
  Settings,
  Smartphone,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import { qk } from "../../api/keys";
import { fetchSession } from "../../lib/session";
import { Screen } from "../../ui/Screen";

interface Row {
  label: string;
  icon: LucideIcon;
  to: NonNullable<LinkProps["to"]>;
  search?: { from: "more" };
}

const ROWS: Row[] = [
  { label: "Trips", icon: History, to: "/trips" },
  { label: "Settings", icon: Settings, to: "/settings" },
  { label: "Who’s using this", icon: UserRound, to: "/who", search: { from: "more" } },
  { label: "Install the app", icon: Smartphone, to: "/install", search: { from: "more" } },
  { label: "About & privacy", icon: Info, to: "/about" },
];

export function MoreScreen() {
  const { data: session } = useQuery({ queryKey: qk.session(), queryFn: fetchSession });
  const member = session?.member;
  return (
    <Screen title="More">
      <ul className="rounded-tile border border-rule bg-paper">
        {ROWS.map(({ label, icon: Icon, to, search }) => (
          <li key={label} className="border-b border-rule last:border-b-0">
            <Link
              to={to}
              {...(search ? { search } : {})}
              className="press-row flex min-h-14 items-center gap-4 px-4 text-body font-semibold"
            >
              <Icon aria-hidden="true" className="text-accent" />
              <span className="flex-1">{label}</span>
              {to === "/who" && member ? (
                <span className="max-w-[45%] truncate text-secondary font-normal text-ink-soft">
                  {member.name}
                </span>
              ) : null}
              <ChevronRight aria-hidden="true" className="text-ink-soft" />
            </Link>
          </li>
        ))}
      </ul>
    </Screen>
  );
}
