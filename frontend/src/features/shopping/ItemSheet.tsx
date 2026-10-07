/**
 * A row's big buttons in shopping mode (UX §4.12): Got it, Couldn't find (or Try again), Add a
 * note, Open in Kroger. Every choice goes into the outbox, so it works with no signal.
 */
import { ExternalLink } from "lucide-react";
import { useId, useState } from "react";

import type { components } from "../../api/schema";
import { cents } from "../../lib/money";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { Sheet } from "../../ui/Sheet";
import { underlined } from "../../ui/styles";

type TripItem = components["schemas"]["TripItemOut"];
type ItemState = TripItem["state"];

export function ItemSheet({
  item,
  onClose,
  onState,
  onNote,
}: {
  item: TripItem | null;
  onClose: () => void;
  onState: (item: TripItem, state: ItemState) => void;
  onNote: (item: TripItem, note: string | null) => void;
}) {
  return (
    <Sheet open={item !== null} title={item?.name ?? "Item"} onClose={onClose}>
      {item ? (
        // A new item (or a note changed elsewhere) starts the note editor afresh.
        <Choices
          key={`${item.id} ${item.note ?? ""}`}
          item={item}
          onState={onState}
          onNote={onNote}
        />
      ) : null}
    </Sheet>
  );
}

function Choices({
  item,
  onState,
  onNote,
}: {
  item: TripItem;
  onState: (item: TripItem, state: ItemState) => void;
  onNote: (item: TripItem, note: string | null) => void;
}) {
  const noteId = useId();
  const [writing, setWriting] = useState(false);
  const [note, setNote] = useState(item.note ?? "");
  return (
    <>
      <div className="mb-5 flex items-start gap-3">
        <ProductImage src={item.image_url} alt="" size={96} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-body">{item.qty_text}</span>
          {item.line_cents !== null ? (
            <span className="text-body font-semibold">about {cents(item.line_cents)}</span>
          ) : null}
          {item.section_label ? (
            <span className="text-secondary text-ink-soft">{item.section_label}</span>
          ) : null}
          {item.used_by.length > 0 ? (
            <span className="text-secondary text-ink-soft">
              for {[...new Set(item.used_by.map((use) => use.name))].join(", ")}
            </span>
          ) : null}
          {item.warnings.map((warning) => (
            <span key={warning} className="text-secondary font-semibold text-tomato">
              {warning}
            </span>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {item.state === "done" ? (
          <Button
            variant="secondary"
            block
            onClick={() => {
              onState(item, "todo");
            }}
          >
            Not in the cart yet
          </Button>
        ) : (
          <Button
            block
            onClick={() => {
              onState(item, "done");
            }}
          >
            Got it
          </Button>
        )}
        {item.state === "missed" ? (
          <Button
            variant="secondary"
            block
            onClick={() => {
              onState(item, "todo");
            }}
          >
            Try again
          </Button>
        ) : (
          <Button
            variant="danger"
            block
            onClick={() => {
              onState(item, "missed");
            }}
          >
            Couldn’t find
          </Button>
        )}
        {writing ? (
          <div className="flex flex-col gap-2 rounded-tile border border-rule p-3">
            <label htmlFor={noteId} className="text-body font-semibold">
              Note for the shopper
            </label>
            <input
              id={noteId}
              value={note}
              maxLength={200}
              placeholder="For example, ripe ones"
              onChange={(event) => {
                setNote(event.target.value);
              }}
              className="min-h-12 rounded-button border-2 border-rule bg-paper px-4 text-body"
            />
            <div className="flex gap-2">
              <Button
                className="flex-1"
                onClick={() => {
                  onNote(item, note.trim() || null);
                  setWriting(false);
                }}
              >
                Save note
              </Button>
              {item.note ? (
                <Button
                  variant="quiet-danger"
                  onClick={() => {
                    onNote(item, null);
                    setWriting(false);
                  }}
                >
                  Remove note
                </Button>
              ) : null}
            </div>
          </div>
        ) : (
          <Button
            variant="secondary"
            block
            onClick={() => {
              setWriting(true);
            }}
          >
            {item.note ? "Change the note" : "Add a note"}
          </Button>
        )}
        {item.product_url ? (
          <a
            href={item.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`inline-flex min-h-12 items-center justify-center gap-2 text-body font-semibold text-accent ${underlined}`}
          >
            Open in Kroger
            <ExternalLink aria-hidden="true" className="size-5" />
          </a>
        ) : null}
      </div>
    </>
  );
}
