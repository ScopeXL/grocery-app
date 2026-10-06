import { useEffect, useId, useRef, type ReactNode } from "react";

import { Button } from "./Button";

/**
 * A bottom sheet on the native <dialog> (docs/UX.md §3): the browser handles focus, Escape and
 * the inert background, and nothing injects styles (ADR 0023). It closes with its visible
 * Close button; Escape and a tap on the backdrop are only shortcuts.
 */
export function Sheet({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="sheet"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      {open ? (
        <div className="flex max-h-[88dvh] flex-col">
          <header className="flex items-center justify-between gap-3 border-b border-rule py-2 pr-2 pl-4">
            <h2 id={titleId} className="text-row font-bold">
              {title}
            </h2>
            <Button variant="quiet" onClick={onClose}>
              Close
            </Button>
          </header>
          <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
          {footer ? <footer className="border-t border-rule px-4 py-3">{footer}</footer> : null}
        </div>
      ) : null}
    </dialog>
  );
}
