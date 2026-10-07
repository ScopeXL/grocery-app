import { anchorToasts } from "../lib/toast";

// One function for every render: a new one each time would make React re-run it, putting a
// re-rendered bar back on top of an open sheet's anchor.
function register(node: HTMLDivElement | null) {
  return node ? anchorToasts(node) : undefined;
}

/**
 * Where toasts appear (lib/toast.ts). Inside a fixed bottom bar they float just above it; a sheet
 * passes its own placement. The newest anchor on screen wins.
 */
export function ToastAnchor({
  className = "absolute inset-x-0 bottom-full mb-2",
}: {
  className?: string;
}) {
  return (
    <div
      ref={register}
      role="status"
      aria-live="polite"
      className={`pointer-events-none flex flex-col items-center gap-2 px-4 print:hidden ${className}`}
    />
  );
}
