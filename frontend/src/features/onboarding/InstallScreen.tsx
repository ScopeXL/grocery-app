import { useNavigate, useSearch } from "@tanstack/react-router";
import { EllipsisVertical, Share, SquarePlus } from "lucide-react";
import type { ReactNode } from "react";

import { isAndroid, isIOS, skipInstallGuide } from "../../lib/platform";
import { BellMark } from "../../ui/BellMark";
import { Button } from "../../ui/Button";

function Step({ children }: { children: ReactNode }) {
  return (
    <li className="flex min-h-16 items-center gap-4 border-b border-rule px-4 py-3 text-body last:border-b-0">
      {children}
    </li>
  );
}

/** "Put Dinner Bell on your home screen" (docs/UX.md §4 Install the app, §5.1). */
export function InstallScreen() {
  const navigate = useNavigate();
  const { from } = useSearch({ from: "/install" });
  const beforeSignIn = from !== "more";

  return (
    <main className="mx-auto w-full max-w-md px-4 pt-[calc(env(safe-area-inset-top)+32px)] pb-12">
      <BellMark className="mb-6 size-16" />
      <h1 className="text-title font-extrabold">Put Dinner Bell on your home screen</h1>
      <p className="mt-2 mb-6 text-body text-ink-soft">
        It opens like an app, works in the store without signal, and keeps the screen awake while
        you shop.
      </p>

      {isIOS() ? (
        <>
          <ol className="rounded-tile border border-rule bg-paper">
            <Step>
              <Share aria-hidden="true" className="shrink-0 text-basil" />
              <span>
                Tap the <strong>Share</strong> button in Safari.
              </span>
            </Step>
            <Step>
              <SquarePlus aria-hidden="true" className="shrink-0 text-basil" />
              <span>
                Scroll down and tap <strong>Add to Home Screen</strong>, then <strong>Add</strong>.
              </span>
            </Step>
            <Step>
              <BellMark className="size-6 shrink-0" />
              <span>Open Dinner Bell from your home screen.</span>
            </Step>
          </ol>
          <p className="mt-4 text-secondary text-ink-soft">
            On iPhone, the home-screen app keeps its own sign-in, so you’ll sign in once more there.
          </p>
        </>
      ) : isAndroid() ? (
        <ol className="rounded-tile border border-rule bg-paper">
          <Step>
            <EllipsisVertical aria-hidden="true" className="shrink-0 text-basil" />
            <span>
              Tap the <strong>menu</strong> in Chrome.
            </span>
          </Step>
          <Step>
            <SquarePlus aria-hidden="true" className="shrink-0 text-basil" />
            <span>
              Tap <strong>Install app</strong> (or <strong>Add to Home screen</strong>).
            </span>
          </Step>
          <Step>
            <BellMark className="size-6 shrink-0" />
            <span>Open Dinner Bell from your home screen.</span>
          </Step>
        </ol>
      ) : (
        <p className="rounded-tile border border-rule bg-paper p-4 text-body">
          On a phone, open this page in Safari (iPhone) or Chrome (Android) to install it.
        </p>
      )}

      <div className="mt-8">
        {beforeSignIn ? (
          <Button
            variant="secondary"
            block
            onClick={() => {
              skipInstallGuide();
              void navigate({ to: "/sign-in" });
            }}
          >
            Continue in Safari
          </Button>
        ) : (
          <Button
            variant="secondary"
            block
            onClick={() => {
              void navigate({ to: "/more" });
            }}
          >
            Back
          </Button>
        )}
      </div>
    </main>
  );
}
