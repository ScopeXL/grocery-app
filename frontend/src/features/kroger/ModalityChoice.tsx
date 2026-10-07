import { useId } from "react";

import { Chip } from "../../ui/Chip";

export type Modality = "PICKUP" | "DELIVERY";

/** Pickup or delivery? Two chips, one chosen (Settings and the Send to Kroger cart sheet). */
export function ModalityChoice({
  label,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  value: Modality | undefined;
  onChange: (value: Modality) => void;
  disabled?: boolean;
}) {
  const labelId = useId();
  return (
    <div role="group" aria-labelledby={labelId} className="flex flex-col gap-2">
      <p id={labelId} className="text-body font-semibold">
        {label}
      </p>
      <div className="flex gap-2">
        {(["PICKUP", "DELIVERY"] as const).map((choice) => (
          <Chip
            key={choice}
            on={value === choice}
            disabled={disabled}
            onClick={() => {
              onChange(choice);
            }}
          >
            {choice === "PICKUP" ? "Pickup" : "Delivery"}
          </Chip>
        ))}
      </div>
    </div>
  );
}
