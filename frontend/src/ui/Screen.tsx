import type { ReactNode } from "react";

/** A tab screen: the title in the brand's heavy weight, content on the counter background. */
export function Screen({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 pt-[calc(env(safe-area-inset-top)+24px)] pb-36 lg:pb-16">
      <h1 className="mb-6 text-title font-extrabold">{title}</h1>
      {children}
    </main>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-row font-bold">{title}</h2>
      <div className="rounded-tile border border-rule bg-paper">{children}</div>
    </section>
  );
}
