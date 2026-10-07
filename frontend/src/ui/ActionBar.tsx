import type { ReactNode } from "react";

import { ToastAnchor } from "./ToastAnchor";

/** The bottom action bar above the tabs (docs/UX.md §1): primary actions in the thumb zone. */
export function ActionBar({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+var(--tabbar-h)+1px)] z-10 border-t border-rule bg-paper px-4 py-2 print:hidden lg:bottom-0 lg:left-60">
      <ToastAnchor />
      <div className="mx-auto flex max-w-3xl gap-2">{children}</div>
    </div>
  );
}
