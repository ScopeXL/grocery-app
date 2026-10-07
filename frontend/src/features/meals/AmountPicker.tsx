/**
 * How much of an item a meal uses (docs/UX.md §4.10). The server decides what's offered
 * (PLAN §8.7: never anything it can't convert) and writes the live preview; this sheet only
 * collects a choice. There is never a free-text unit field.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { add, isPositive, parseFraction, toMixed, toText } from "../../lib/fraction";
import { about } from "../../lib/money";
import { useDebounced } from "../../lib/useDebounced";
import { Button } from "../../ui/Button";
import { ProductImage } from "../../ui/ProductImage";
import { Sheet } from "../../ui/Sheet";
import type { AmountIn, AmountOut, ItemOut, KindOption, PickerOut } from "./types";

const WEIGHT_UNITS = new Set(["oz", "lb", "g", "kg"]);
const UNIT_NAMES: Record<string, string> = { fl_oz: "fl oz" };
const EACH_WEIGHT_NAMES: Record<string, string> = {
  "1/4": "Small, about 4 oz",
  "1/2": "Medium, about 8 oz",
  "3/4": "Large, about 12 oz",
  "1": "1 lb",
};

function kindLabel(option: KindOption): string {
  if (option.kind === "packages") return "Part of the package";
  if (option.kind === "count") return "How many";
  return option.units.some((unit) => WEIGHT_UNITS.has(unit)) ? "By weight" : "Kitchen measure";
}

function same(a: AmountIn | null, b: AmountOut | AmountIn): boolean {
  return (
    a !== null && a.kind === b.kind && a.value === b.value && (a.unit ?? null) === (b.unit ?? null)
  );
}

export function AmountPicker({
  item,
  initial,
  open,
  onClose,
  onDone,
}: {
  item: ItemOut;
  initial: AmountOut | null;
  open: boolean;
  onClose: () => void;
  onDone: (amount: AmountOut) => void;
}) {
  const [choice, setChoice] = useState<AmountIn | null>(
    initial ? { kind: initial.kind, value: initial.value, unit: initial.unit } : null,
  );
  const settled = useDebounced(choice, 200);
  const picker = useQuery({
    queryKey: qk.picker(item.id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/items/{item_id}/picker", { params: { path: { item_id: item.id } } }),
      ),
    enabled: open,
  });
  const preview = useQuery({
    queryKey: [...qk.picker(item.id), "preview", settled, picker.dataUpdatedAt],
    queryFn: async () => {
      if (settled === null) throw new Error("nothing chosen yet");
      return unwrap(
        await api.POST("/api/items/{item_id}/preview", {
          params: { path: { item_id: item.id } },
          body: { amount: settled },
        }),
      );
    },
    enabled: open && settled !== null && picker.isSuccess,
    staleTime: 30_000,
  });

  const data = picker.data;
  const current = choice !== null && same(settled, choice) ? preview.data : undefined;
  const ready = current?.valid === true && current.amount !== null;

  return (
    <Sheet
      open={open}
      title="How much?"
      onClose={onClose}
      footer={
        <Button
          block
          disabled={!ready}
          onClick={() => {
            if (current?.amount) onDone(current.amount);
          }}
        >
          Done
        </Button>
      }
    >
      <header className="mb-4 flex items-center gap-3">
        <ProductImage src={data?.item.image_url ?? item.image_url} alt="" size={64} />
        <div className="flex flex-col">
          <span className="text-row font-semibold">{item.name}</span>
          {data?.product ? (
            <span className="text-secondary text-ink-soft">{data.product.description}</span>
          ) : null}
          {(data?.item.size_text ?? item.size_text) ? (
            <span className="text-secondary text-ink-soft">
              {data?.item.size_text ?? item.size_text}
            </span>
          ) : null}
        </div>
      </header>

      {picker.isError ? (
        <p className="text-body text-tomato">{errorMessage(picker.error)}</p>
      ) : !data ? (
        <p className="text-secondary text-ink-soft">Loading…</p>
      ) : (
        <>
          {data.fix_size ? <FixSize picker={data} /> : null}
          <h3 className="mb-3 text-body font-bold">How much does this meal use?</h3>
          {data.kinds.map((option) => (
            <KindSection
              key={option.kind + option.units.join()}
              option={option}
              choice={choice}
              onChoose={setChoice}
            >
              {option.kind === "count" ? <EachWeight picker={data} /> : null}
            </KindSection>
          ))}
          <div aria-live="polite" className="mt-2 min-h-16 rounded-tile bg-counter p-3">
            {choice === null ? (
              <p className="text-secondary text-ink-soft">Choose an amount above.</p>
            ) : current === undefined ? (
              <p className="text-secondary text-ink-soft">Working it out…</p>
            ) : current.valid ? (
              <>
                <p className="text-body font-semibold">{current.share_text}</p>
                <p className="text-secondary text-ink-soft">
                  {current.cost_cents !== null
                    ? about(current.cost_cents)
                    : "No price for this yet"}
                </p>
              </>
            ) : (
              <p className="text-body font-semibold text-tomato">{current.message}</p>
            )}
          </div>
        </>
      )}
    </Sheet>
  );
}

function KindSection({
  option,
  choice,
  onChoose,
  children,
}: {
  option: KindOption;
  choice: AmountIn | null;
  onChoose: (amount: AmountIn) => void;
  children?: ReactNode;
}) {
  const unitId = useId();
  const mine = choice?.kind === option.kind ? choice : null;
  const unit = mine?.unit ?? option.units[0] ?? null;
  const value = mine ? parseFraction(mine.value) : null;
  const step = parseFraction(option.step ?? "1") ?? { n: 1, d: 1 };
  const stepper = option.kind !== "packages";
  // While typing, show exactly what was typed; the buttons show the tidy value again.
  const [typed, setTyped] = useState<string | null>(null);

  const set = (next: { n: number; d: number }) => {
    if (isPositive(next))
      onChoose({
        kind: option.kind,
        value: toText(next),
        unit: option.kind === "measure" ? unit : null,
      });
  };

  return (
    <section className="mb-5">
      <h4 className="mb-2 text-secondary font-semibold text-ink-soft">{kindLabel(option)}</h4>
      {option.presets.length > 0 ? (
        <div className="mb-3 flex flex-wrap gap-2">
          {option.presets.map((preset) => (
            <button
              key={preset.value + (preset.unit ?? "")}
              type="button"
              aria-pressed={same(choice, preset)}
              onClick={() => {
                onChoose({ kind: preset.kind, value: preset.value, unit: preset.unit });
              }}
              className="min-h-12 rounded-full border-2 border-rule bg-paper px-4 text-body font-semibold aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
            >
              {preset.text}
            </button>
          ))}
        </div>
      ) : null}
      {stepper ? (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-label="Less"
            disabled={!value}
            onClick={() => {
              setTyped(null);
              if (value) set(add(value, { n: -step.n, d: step.d }));
            }}
            className="flex size-12 items-center justify-center rounded-button border-2 border-rule bg-paper disabled:opacity-50"
          >
            <Minus aria-hidden="true" />
          </button>
          <input
            aria-label={kindLabel(option)}
            inputMode="decimal"
            autoComplete="off"
            placeholder="0"
            value={typed ?? (value ? toMixed(value) : "")}
            onChange={(event) => {
              const text = event.target.value.slice(0, 8);
              setTyped(text);
              const parsed = parseFraction(text);
              if (parsed) set(parsed);
            }}
            onBlur={() => {
              setTyped(null);
            }}
            className="min-h-12 w-20 rounded-button border-2 border-rule bg-paper text-center text-row font-semibold"
          />
          <button
            type="button"
            aria-label="More"
            onClick={() => {
              setTyped(null);
              // Counting starts at one whole piece; after that it steps by the option's step.
              set(value ? add(value, step) : { n: 1, d: 1 });
            }}
            className="flex size-12 items-center justify-center rounded-button border-2 border-rule bg-paper"
          >
            <Plus aria-hidden="true" />
          </button>
          {option.kind === "measure" && option.units.length > 0 ? (
            <>
              <label htmlFor={unitId} className="sr-only">
                Unit
              </label>
              <select
                id={unitId}
                value={unit ?? ""}
                onChange={(event) => {
                  onChoose({
                    kind: "measure",
                    value: mine?.value ?? "1",
                    unit: event.target.value,
                  });
                }}
                className="min-h-12 rounded-button border-2 border-rule bg-paper px-3 text-body"
              >
                {option.units.map((name) => (
                  <option key={name} value={name}>
                    {UNIT_NAMES[name] ?? name}
                  </option>
                ))}
              </select>
            </>
          ) : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

function EachWeight({ picker }: { picker: PickerOut }) {
  const queryClient = useQueryClient();
  const [other, setOther] = useState("");
  const otherId = useId();
  const save = useMutation({
    mutationFn: async (pounds: string) =>
      unwrap(
        await api.PATCH("/api/items/{item_id}", {
          params: { path: { item_id: picker.item.id } },
          body: { each_weight_lb: pounds },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.picker(picker.item.id) }),
  });
  const known = picker.item.each_weight_lb;
  const question = picker.each_weight;
  if (!question && !known) return null;
  const chosen = known ?? question?.prefill ?? null;
  const presets = question?.presets ?? ["1/4", "1/2", "3/4", "1"];
  return (
    <div className="mt-3 rounded-tile border border-rule p-3">
      <p className="mb-2 text-body font-semibold">About how much does one weigh?</p>
      <div className="flex flex-wrap gap-2">
        {presets.map((pounds) => (
          <button
            key={pounds}
            type="button"
            aria-pressed={chosen === pounds}
            disabled={save.isPending}
            onClick={() => {
              save.mutate(pounds);
            }}
            className="min-h-12 rounded-full border-2 border-rule bg-paper px-4 text-secondary font-semibold aria-pressed:border-accent aria-pressed:bg-accent aria-pressed:text-on-accent"
          >
            {EACH_WEIGHT_NAMES[pounds] ?? `${pounds} lb`}
          </button>
        ))}
      </div>
      <form
        className="mt-3 flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const ounces = parseFraction(other);
          if (ounces && isPositive(ounces)) save.mutate(toText({ n: ounces.n, d: ounces.d * 16 }));
        }}
      >
        <label htmlFor={otherId} className="flex flex-col text-secondary">
          Other, in ounces
          <input
            id={otherId}
            value={other}
            inputMode="decimal"
            onChange={(event) => {
              setOther(event.target.value.slice(0, 8));
            }}
            className="mt-1 min-h-12 w-28 rounded-button border-2 border-rule bg-paper px-3 text-body"
          />
        </label>
        <Button
          type="submit"
          variant="secondary"
          disabled={!parseFraction(other) || save.isPending}
        >
          Use
        </Button>
      </form>
      {save.isError ? (
        <p className="mt-2 text-secondary text-tomato">{errorMessage(save.error)}</p>
      ) : null}
    </div>
  );
}

function FixSize({ picker }: { picker: PickerOut }) {
  const queryClient = useQueryClient();
  const [size, setSize] = useState("");
  const sizeId = useId();
  const save = useMutation({
    mutationFn: async (text: string) =>
      unwrap(
        await api.PATCH("/api/items/{item_id}", {
          params: { path: { item_id: picker.item.id } },
          body: { size_text: text },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.picker(picker.item.id) }),
  });
  return (
    <form
      className="mb-5 rounded-tile border border-rule p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (size.trim()) save.mutate(size.trim());
      }}
    >
      <p className="text-body font-semibold">The package size couldn't be read.</p>
      <label htmlFor={sizeId} className="mt-2 block text-secondary">
        What does the package say? For example, 16 oz or 12 ct.
      </label>
      <div className="mt-1 flex gap-2">
        <input
          id={sizeId}
          value={size}
          onChange={(event) => {
            setSize(event.target.value.slice(0, 40));
          }}
          className="min-h-12 flex-1 rounded-button border-2 border-rule bg-paper px-3 text-body"
        />
        <Button type="submit" variant="secondary" disabled={!size.trim() || save.isPending}>
          Fix size
        </Button>
      </div>
      {save.isError ? (
        <p className="mt-2 text-secondary text-tomato">{errorMessage(save.error)}</p>
      ) : null}
    </form>
  );
}
