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
  step,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  /** For a sheet with steps: when it changes, the new step starts at the top, with focus. */
  step?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const shownStep = useRef(step);
  const titleId = useId();

  useEffect(() => {
    if (step === shownStep.current) return;
    shownStep.current = step;
    const body = bodyRef.current;
    if (!body) return;
    // What had focus (the choice just tapped) is gone with the old step.
    body.scrollTop = 0;
    body.focus({ preventScroll: true });
  }, [step]);

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
          <header className="flex items-center justify-between gap-3 border-b border-rule py-1.5 pr-2 pl-4">
            <h2 id={titleId} className="text-row font-bold">
              {title}
            </h2>
            <Button variant="quiet" onClick={onClose}>
              Close
            </Button>
          </header>
          {/* Focusable, so a keyboard can scroll it even when nothing inside takes focus. */}
          <div
            ref={bodyRef}
            role="region"
            aria-labelledby={titleId}
            tabIndex={0}
            className="flex-1 overflow-y-auto px-4 py-4"
          >
            {children}
          </div>
          {footer ? <footer className="border-t border-rule px-4 py-3">{footer}</footer> : null}
        </div>
      ) : null}
    </dialog>
  );
}
