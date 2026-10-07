import { useNavigate, useSearch } from "@tanstack/react-router";
import { EllipsisVertical } from "lucide-react";
import type { ReactNode } from "react";

import { isAndroid, isIOS, skipInstallGuide } from "../../lib/platform";
import { BellMark } from "../../ui/BellMark";
import { Button } from "../../ui/Button";
import {
  ChromeBarArt,
  ChromeMenuArt,
  HomeScreenArt,
  SafariBarArt,
  ShareSheetArt,
} from "./InstallArt";

/** The steps, in order. Safari stops announcing a list once its markers are hidden, so
 * role="list" keeps it one for VoiceOver. */
function Steps({ children }: { children: ReactNode }) {
  return (
    <ol role="list" className="rounded-tile border border-rule bg-paper">
      {children}
    </ol>
  );
}

/** One step: the drawing (decorative), its number, and what to do. */
function Step({ number, art, children }: { number: number; art: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-center gap-4 border-b border-rule p-4 last:border-b-0">
      {art}
      <div className="min-w-0 text-body">
        <p className="text-row font-extrabold text-basil">{number}</p>
        <p className="mt-1">{children}</p>
      </div>
    </li>
  );
}

/** A button that is only dots on screen: shown as the dots, read aloud as words. */
function Dots({ shown, spoken }: { shown: ReactNode; spoken: string }) {
  return (
    <>
      <strong aria-hidden="true">{shown}</strong>
      <span className="sr-only">{spoken}</span>
    </>
  );
}

/** "Put Dinner Bell on your home screen" (docs/UX.md §3 Installed app, §5.1). */
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
          <Steps>
            <Step number={1} art={<SafariBarArt />}>
              Tap <strong>Share</strong>. On newer iPhones, tap{" "}
              <Dots shown="•••" spoken="the three dots" /> next to the address first.
            </Step>
            <Step number={2} art={<ShareSheetArt />}>
              Tap <strong>Add to Home Screen</strong> (scroll down, or tap{" "}
              <strong>View More</strong>, if you don’t see it), then <strong>Add</strong>.
            </Step>
            <Step number={3} art={<HomeScreenArt kind="iphone" />}>
              Open Dinner Bell from your home screen.
            </Step>
          </Steps>
          <p className="mt-4 text-secondary text-ink-soft">
            On iPhone, the home-screen app keeps its own sign-in. Sign in there once more: with the
            household password, or with a code from a phone that’s already signed in (More, then
            Settings, then Add a phone).
          </p>
        </>
      ) : isAndroid() ? (
        <Steps>
          <Step number={1} art={<ChromeBarArt />}>
            Tap the{" "}
            <Dots
              // The ⋮ character isn't in the app's font, and fallback fonts draw it thin. The
              // icon's box is wider than its dots, so the margins pull the words back in.
              shown={
                <EllipsisVertical
                  strokeWidth={3}
                  className="-mx-[0.3em] inline size-[1em] align-[-0.125em]"
                />
              }
              spoken="three dots"
            />{" "}
            menu in Chrome.
          </Step>
          <Step number={2} art={<ChromeMenuArt />}>
            Tap <strong>Install app</strong> (or <strong>Add to Home screen</strong>), then{" "}
            <strong>Install</strong>.
          </Step>
          <Step number={3} art={<HomeScreenArt kind="android" />}>
            Open Dinner Bell from your home screen.
          </Step>
        </Steps>
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
