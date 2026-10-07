/**
 * Where Connect Kroger ends when the sign-in finished outside Dinner Bell's own browser, as an
 * iPhone's home-screen app can (PLAN §7.5). Nothing to do here but say how it went.
 */
import { BellMark } from "../../ui/BellMark";
import type { ConnectResult } from "./account";

const TEXT: Record<ConnectResult, { title: string; body: string }> = {
  connected: {
    title: "Kroger is connected",
    body: "Go back to Dinner Bell to send your saved lists to your Kroger cart. You can close this page.",
  },
  denied: {
    title: "Kroger wasn’t connected",
    body: "You chose not to allow it. You can connect it any time from Settings in Dinner Bell.",
  },
  expired: {
    title: "That sign-in took too long",
    body: "Go back to Dinner Bell and tap Connect Kroger again.",
  },
  failed: {
    title: "Kroger couldn’t be connected",
    body: "Go back to Dinner Bell and tap Connect Kroger again.",
  },
};

export function KrogerDoneScreen({ result }: { result: ConnectResult }) {
  const text = TEXT[result];
  return (
    <main className="mx-auto w-full max-w-md px-4 pt-[calc(env(safe-area-inset-top)+48px)] pb-12">
      <BellMark className="mb-6 size-16" />
      <h1 className="mb-3 text-title font-extrabold">{text.title}</h1>
      <p className="text-body text-ink-soft">{text.body}</p>
    </main>
  );
}
