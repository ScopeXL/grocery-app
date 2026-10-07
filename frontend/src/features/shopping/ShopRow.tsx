/**
 * One row in shopping mode (UX §4.12): a 64 px photo tile, the name in bold, the quantity and
 * size, and a 56 px checkbox at the right edge. Tapping the checkbox checks it off (with the
 * marker stroke); tapping anywhere else opens the row's big buttons.
 */
import { Check } from "lucide-react";

import type { components } from "../../api/schema";
import { ProductImage } from "../../ui/ProductImage";
import { MarkerStrike } from "./MarkerStrike";

type TripItem = components["schemas"]["TripItemOut"];

export function ShopRow({
  item,
  checkedBy,
  striking,
  onCheck,
  onOpen,
}: {
  item: TripItem;
  /** The checker's marker color and name, when the row is checked off. */
  checkedBy: { color: string; name: string } | null;
  /** Draw the stroke now (it was just checked on this phone). */
  striking: boolean;
  onCheck: () => void;
  onOpen: () => void;
}) {
  const done = item.state === "done";
  return (
    <li className="flex items-stretch border-b border-rule last:border-b-0">
      <button
        type="button"
        onClick={onOpen}
        className="press-row flex min-h-20 min-w-0 flex-1 items-center gap-3 py-2 pl-3 text-left"
      >
        <ProductImage src={item.image_url} alt="" size={64} />
        <span className="flex min-w-0 flex-col">
          <span className="relative self-start text-row leading-tight font-bold">
            <span className={done ? "text-ink-soft" : ""}>{item.name}</span>
            {done && checkedBy ? (
              <MarkerStrike seed={item.id} color={checkedBy.color} animate={striking} />
            ) : null}
          </span>
          <span className="text-body">{item.qty_text}</span>
          {done && checkedBy ? (
            <span className="text-secondary text-ink-soft">Checked off by {checkedBy.name}</span>
          ) : null}
          {item.note ? (
            <span className="text-secondary text-ink-soft">Note: {item.note}</span>
          ) : null}
        </span>
      </button>
      <button
        type="button"
        role="checkbox"
        aria-checked={done}
        aria-label={done ? `Uncheck ${item.name}` : `Check off ${item.name}`}
        onClick={onCheck}
        className="flex w-18 shrink-0 items-center justify-center"
      >
        <span
          className={`flex size-12 items-center justify-center rounded-button border-[3px] ${
            done ? "border-accent bg-accent text-on-accent" : "border-ink-soft bg-paper"
          }`}
        >
          {done ? <Check aria-hidden="true" className="size-7" strokeWidth={3} /> : null}
        </span>
      </button>
    </li>
  );
}
