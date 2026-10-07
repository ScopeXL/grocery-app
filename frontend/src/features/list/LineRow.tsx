/**
 * One list line (UX §4.11): the photo and name, the quantity in plain words with the size, the
 * price with a Sale tag beside it, which meals use it, and any warnings. Have-it lines stay,
 * lightly marked, without a price.
 */
import type { ReactNode } from "react";

import { shortDay } from "../../lib/days";
import { about } from "../../lib/money";
import { ProductImage } from "../../ui/ProductImage";
import { joinNames, type Line } from "../plan/types";

export function usedByText(line: Line): string | null {
  const names = [...new Set(line.used_by.map((use) => use.name))];
  return names.length > 0 ? `for ${joinNames(names)}` : null;
}

/** "Sample Parent added 1 more": extras on a line the meals also use. */
export function addedText(line: Line): string {
  const people = [...new Set(line.extras.map((extra) => extra.added_by?.name ?? "Someone"))];
  return `${joinNames(people)} added ${line.extra} more`;
}

const QUIET_WARNINGS = new Set(["Low stock", "No price"]);

export function LineRow({
  line,
  onOpen,
  note,
}: {
  line: Line;
  onOpen: (key: string) => void;
  note?: ReactNode;
}) {
  const had = line.have_it === true;
  const usedBy = usedByText(line);
  return (
    <li className="border-b border-rule last:border-b-0">
      <button
        type="button"
        onClick={() => {
          onOpen(line.key);
        }}
        className="flex min-h-16 w-full items-start gap-3 px-3 py-2.5 text-left"
      >
        <span className={had ? "opacity-50" : ""}>
          <ProductImage src={line.image_url} alt="" size={48} />
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span
            className={`text-row leading-tight font-bold ${had ? "text-ink-soft line-through decoration-2" : ""}`}
          >
            {line.name}
          </span>
          <span className="text-body">{line.amount_text}</span>
          {line.needed_text ? (
            <span className="text-secondary text-ink-soft">{line.needed_text}</span>
          ) : null}
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {had ? (
              <span className="rounded-full border-2 border-ink-soft px-2 text-caption font-bold text-ink-soft">
                Have it
              </span>
            ) : line.cost_cents !== null ? (
              <span className="text-secondary font-semibold">
                {line.at_least ? "at least " : ""}
                {about(line.cost_cents)}
              </span>
            ) : null}
            {!had && line.sale ? (
              <span className="flex items-center gap-1 text-caption text-ink-soft">
                <span className="rounded-full bg-lemon px-2 font-bold text-on-lemon">Sale</span>
                {line.sale.ends ? `until ${shortDay(line.sale.ends)}` : null}
              </span>
            ) : null}
            {!had && line.estimated_weight ? (
              <span className="text-caption text-ink-soft">est.</span>
            ) : null}
            {usedBy ? <span className="text-secondary text-ink-soft">{usedBy}</span> : null}
          </span>
          {line.used_by.length > 0 && line.extras.length > 0 ? (
            <span className="text-secondary text-ink-soft">{addedText(line)}</span>
          ) : null}
          {line.warnings.map((warning) => (
            <span
              key={warning}
              className={`text-secondary font-semibold ${QUIET_WARNINGS.has(warning) ? "text-ink-soft" : "text-tomato"}`}
            >
              {warning}
            </span>
          ))}
          {note}
        </span>
      </button>
    </li>
  );
}
