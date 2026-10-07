/**
 * Finish trip (UX §4.13): "What did you pay? (optional)", then Finish trip. It works offline:
 * finishing is one more action in the outbox, sent when there's signal.
 */
import { useId, useState } from "react";

import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";

/** "34.20", "$34", "34" → cents; anything else → undefined (left out). */
export function paidCents(text: string): number | undefined | "invalid" {
  const value = text.trim().replace(/^\$/, "").replace(/,/g, "");
  if (!value) return undefined;
  const match = /^(\d{1,6})(?:\.(\d{1,2}))?$/.exec(value);
  if (!match) return "invalid";
  const dollars = Number(match[1]);
  const cents = Number((match[2] ?? "").padEnd(2, "0"));
  return dollars * 100 + cents;
}

export function FinishSheet({
  open,
  onClose,
  onFinish,
}: {
  open: boolean;
  onClose: () => void;
  onFinish: (actualTotalCents: number | undefined) => void;
}) {
  const inputId = useId();
  const [paid, setPaid] = useState("");
  const parsed = paidCents(paid);
  return (
    <Sheet
      open={open}
      title="Finish trip"
      onClose={onClose}
      footer={
        <Button
          block
          disabled={parsed === "invalid"}
          onClick={() => {
            if (parsed !== "invalid") onFinish(parsed);
          }}
        >
          Finish trip
        </Button>
      }
    >
      <label htmlFor={inputId} className="text-body font-semibold">
        What did you pay? (optional)
      </label>
      <div className="mt-2 flex items-center gap-2">
        <span className="text-row font-bold">$</span>
        <input
          id={inputId}
          inputMode="decimal"
          autoComplete="off"
          value={paid}
          placeholder="0.00"
          onChange={(event) => {
            setPaid(event.target.value.slice(0, 12));
          }}
          className="min-h-14 w-40 rounded-button border-2 border-rule bg-paper px-4 text-row"
        />
      </div>
      <p className="mt-2 min-h-7 text-secondary text-ink-soft" role="status">
        {parsed === "invalid" ? "Write it like 34.20" : "From the receipt, so Trips can compare."}
      </p>
    </Sheet>
  );
}
