/**
 * Change a person (docs/UX.md §4.16): their name and their marker color. Each color shows the
 * person's initial in it, with a color word, so color is never the only cue (UX §7.2). Saving
 * says "Changes saved" with Undo, which puts both back. Removing them is here too, with Undo.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import type { Member } from "../../lib/session";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { MemberBadge } from "../../ui/MemberBadge";
import { Sheet } from "../../ui/Sheet";

type Color = Member["marker_color"];

const COLORS: readonly { value: Color; word: string }[] = [
  { value: "basil", word: "Green" },
  { value: "tomato", word: "Red" },
  { value: "carrot", word: "Orange" },
  { value: "eggplant", word: "Purple" },
  { value: "beet", word: "Pink" },
  { value: "olive", word: "Olive" },
  { value: "cocoa", word: "Brown" },
  { value: "plum", word: "Plum" },
];

export function MemberSheet({
  member,
  onClose,
  onRemove,
}: {
  member: Member | null;
  onClose: () => void;
  onRemove: (member: Member) => void;
}) {
  return (
    <Sheet
      open={member !== null}
      title={member ? `Change ${member.name}` : "Change"}
      onClose={onClose}
    >
      {/* Keyed, so each person's sheet starts from their own name and color. */}
      {member ? (
        <MemberForm
          key={member.id}
          member={member}
          onDone={onClose}
          onRemove={() => {
            onClose();
            onRemove(member);
          }}
        />
      ) : null}
    </Sheet>
  );
}

function MemberForm({
  member,
  onDone,
  onRemove,
}: {
  member: Member;
  onDone: () => void;
  onRemove: () => void;
}) {
  const queryClient = useQueryClient();
  const nameId = useId();
  const [name, setName] = useState(member.name);
  const [color, setColor] = useState<Color>(member.marker_color);

  const save = async (body: { name: string; marker_color: Color }) => {
    const saved = unwrap(
      await api.PATCH("/api/members/{member_id}", {
        params: { path: { member_id: member.id } },
        body,
      }),
    );
    await queryClient.invalidateQueries({ queryKey: qk.session() });
    void queryClient.invalidateQueries({ queryKey: qk.members() });
    return saved;
  };
  const change = useMutation({
    mutationFn: save,
    onSuccess: () => {
      onDone();
      showToast("Changes saved", {
        label: "Undo",
        onAction: () => {
          save({ name: member.name, marker_color: member.marker_color }).catch(
            (failure: unknown) => {
              showToast(errorMessage(failure));
            },
          );
        },
      });
    },
  });

  const trimmed = name.trim();
  const changed = trimmed !== member.name || color !== member.marker_color;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!trimmed) return;
        if (changed) change.mutate({ name: trimmed, marker_color: color });
        else onDone();
      }}
    >
      <label htmlFor={nameId} className="text-body font-semibold">
        Name
      </label>
      <input
        id={nameId}
        value={name}
        maxLength={40}
        autoComplete="off"
        onChange={(event) => {
          setName(event.target.value);
        }}
        className="mt-2 mb-5 min-h-12 w-full rounded-button border-2 border-rule bg-paper px-4 text-body"
      />
      <fieldset>
        <legend className="mb-2 text-body font-semibold">Color</legend>
        <div className="grid grid-cols-2 gap-2">
          {COLORS.map(({ value, word }) => (
            <label
              key={value}
              className="flex min-h-12 items-center gap-3 rounded-button border-2 border-rule bg-paper px-3 has-checked:border-accent"
            >
              <input
                type="radio"
                name={`${nameId}-color`}
                value={value}
                checked={color === value}
                onChange={() => {
                  setColor(value);
                }}
                className="size-5 shrink-0 accent-accent"
              />
              <MemberBadge name={trimmed || member.name} color={value} size="sm" />
              <span className="text-body">{word}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <p role="alert" className="mt-3 min-h-7 text-secondary font-semibold text-tomato">
        {change.isError ? errorMessage(change.error) : null}
      </p>
      <Button type="submit" block disabled={change.isPending || !trimmed}>
        Save changes
      </Button>
      <Button variant="quiet-danger" block className="mt-3" onClick={onRemove}>
        Remove {member.name}
      </Button>
    </form>
  );
}
