import { memo, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { Button } from "./Button";
import { ToastAnchor } from "./ToastAnchor";

/**
 * Keeps showing what it last showed while `frozen`. Callers clear their state when a sheet
 * closes, so without this a closing sheet would slide away empty.
 */
const Frozen = memo(
  function Frozen({ children }: { children: ReactNode; frozen: boolean }) {
    return children;
  },
  (_previous, next) => next.frozen,
);

/** Back to a plain open dialog: no longer sliding away. */
function stopClosing(dialog: HTMLDialogElement): void {
  delete dialog.dataset.closing;
  dialog.inert = false;
  dialog.removeAttribute("aria-hidden");
}

/**
 * A bottom sheet on the native <dialog> (docs/UX.md §3): the browser handles focus, Escape and
 * the inert background, and nothing injects styles (ADR 0023). It closes with its visible
 * Close button; Escape and a tap on the backdrop are only shortcuts.
 *
 * It slides up when it opens and back down when it closes (styles/motion.css, ADR 0027). While
 * it slides away it stays modal, marked `data-closing`, inert and hidden from screen readers,
 * still showing what it showed; the script closes it once its animation ends. Opening it again
 * meanwhile just keeps it open.
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
  // Sliding away: `open` went false, but the dialog is still on screen until its animation ends.
  const [closing, setClosing] = useState(false);
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    setClosing(!open);
  }

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
    if (open) {
      stopClosing(dialog);
      if (!dialog.open) {
        dialog.showModal();
        // The sheet itself takes focus, not its first button, so Close doesn't look pressed.
        dialog.focus();
      }
      return;
    }
    if (!dialog.open) return;
    dialog.dataset.closing = "";
    dialog.inert = true;
    dialog.setAttribute("aria-hidden", "true");
    let reopened = false;
    void Promise.allSettled(dialog.getAnimations().map((animation) => animation.finished)).then(
      () => {
        if (reopened) return;
        stopClosing(dialog);
        dialog.close();
        setClosing(false);
      },
    );
    return () => {
      reopened = true;
    };
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="sheet"
      tabIndex={-1}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      {open || closing ? (
        <div className="flex max-h-[88dvh] flex-col">
          <Frozen frozen={!open}>
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
          </Frozen>
          {/* Toasts (and their Undo) show here, since the page behind an open sheet can't be
              tapped. In the layout, not over it, so they never cover the sheet's buttons. Gone as
              soon as the sheet starts closing, so a new toast lands on the page. */}
          {open ? <ToastAnchor className="not-empty:pb-3" /> : null}
          <Frozen frozen={!open}>
            {footer ? <footer className="border-t border-rule px-4 py-3">{footer}</footer> : null}
          </Frozen>
        </div>
      ) : null}
    </dialog>
  );
}
