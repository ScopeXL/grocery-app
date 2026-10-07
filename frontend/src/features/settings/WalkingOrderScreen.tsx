/**
 * Store walking order (UX §4.16): the sections of the store in the order the household walks
 * them. Up and down buttons on every row; each move saves at once, and lists being shopped
 * re-sort on every phone.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowDown, ArrowUp, ChevronLeft } from "lucide-react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import type { components } from "../../api/schema";
import { showToast } from "../../lib/toast";
import { Screen } from "../../ui/Screen";

type Section = components["schemas"]["StoreSectionOut"];

export function WalkingOrderScreen() {
  const queryClient = useQueryClient();
  const sections = useQuery({
    queryKey: qk.sections(),
    queryFn: async () => unwrap(await api.GET("/api/stores/active/sections")),
  });
  const save = useMutation({
    mutationFn: async (order: Section[]) =>
      unwrap(
        await api.PUT("/api/stores/active/sections", {
          body: { ids: order.map((section) => section.id) },
        }),
      ),
    onMutate: async (order) => {
      await queryClient.cancelQueries({ queryKey: qk.sections() });
      const before = queryClient.getQueryData<Section[]>(qk.sections());
      queryClient.setQueryData(qk.sections(), order);
      return { before };
    },
    onError: (failure, _order, context) => {
      queryClient.setQueryData(qk.sections(), context?.before);
      showToast(errorMessage(failure));
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(qk.sections(), saved);
      void queryClient.invalidateQueries({ queryKey: qk.plan() });
    },
  });

  const order = sections.data ?? [];
  const move = (index: number, by: -1 | 1) => {
    const next = [...order];
    const [section] = next.splice(index, 1);
    if (!section) return;
    next.splice(index + by, 0, section);
    save.mutate(next);
  };

  return (
    <Screen title="Store walking order">
      <Link
        to="/settings"
        className="-mt-4 mb-4 inline-flex min-h-12 items-center gap-1 text-body font-semibold text-accent"
      >
        <ChevronLeft aria-hidden="true" />
        Settings
      </Link>
      <p className="mb-5 text-body">
        The list and shopping follow this order. Move a section up or down to match how you walk
        your store.
      </p>
      {sections.isError ? (
        <p className="text-body">{errorMessage(sections.error)}</p>
      ) : (
        <ol
          aria-label="Sections"
          className="overflow-hidden rounded-tile border border-rule bg-paper"
        >
          {order.map((section, index) => (
            <li
              key={section.id}
              className="flex min-h-16 items-center gap-2 border-b border-rule py-2 pr-2 pl-4 last:border-b-0"
            >
              <span className="w-8 text-secondary text-ink-soft">{String(index + 1)}</span>
              <span className="flex-1 text-body font-semibold">{section.label}</span>
              <button
                type="button"
                aria-label={`Move ${section.label} up`}
                disabled={index === 0 || save.isPending}
                onClick={() => {
                  move(index, -1);
                }}
                className="flex size-12 items-center justify-center rounded-button border-2 border-rule disabled:opacity-40"
              >
                <ArrowUp aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label={`Move ${section.label} down`}
                disabled={index === order.length - 1 || save.isPending}
                onClick={() => {
                  move(index, 1);
                }}
                className="flex size-12 items-center justify-center rounded-button border-2 border-rule disabled:opacity-40"
              >
                <ArrowDown aria-hidden="true" />
              </button>
            </li>
          ))}
        </ol>
      )}
    </Screen>
  );
}
