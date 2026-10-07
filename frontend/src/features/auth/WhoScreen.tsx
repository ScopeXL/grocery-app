import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCanGoBack, useNavigate, useRouter } from "@tanstack/react-router";
import { UserPlus } from "lucide-react";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { fetchSession, type Session } from "../../lib/session";
import { Button } from "../../ui/Button";
import { MemberButton } from "./MemberButton";

/** Where Who's using this phone was opened from, so it can go back there. */
export type WhoFrom = "more" | "settings";

/**
 * "Who's using this phone?" — attribution for check-offs and extras (docs/UX.md §4.2). Whoever
 * uses this phone shows as "Using this phone". Opened from More or Settings, it goes back there
 * after a choice (or Back); right after signing in, on to the plan (or Skip for now).
 */
export function WhoScreen({ from }: { from?: WhoFrom | undefined }) {
  const navigate = useNavigate();
  const router = useRouter();
  const canGoBack = useCanGoBack();
  const queryClient = useQueryClient();
  const { data: session } = useQuery({ queryKey: qk.session(), queryFn: fetchSession });
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const nameId = useId();

  const leave = async () => {
    if (from && canGoBack) {
      router.history.back();
      return;
    }
    await navigate({ to: from === "settings" ? "/settings" : from === "more" ? "/more" : "/" });
  };

  const finish = async (updated: Session) => {
    queryClient.setQueryData(qk.session(), updated);
    await queryClient.invalidateQueries({ queryKey: qk.members() });
    await leave();
  };

  const choose = useMutation({
    mutationFn: async (memberId: string) =>
      unwrap(await api.PUT("/api/auth/member", { body: { member_id: memberId } })),
    onSuccess: finish,
    onError: (failure) => {
      setError(errorMessage(failure));
    },
  });

  const addMe = useMutation({
    mutationFn: async (value: string) => {
      const member = unwrap(await api.POST("/api/members", { body: { name: value } }));
      return unwrap(await api.PUT("/api/auth/member", { body: { member_id: member.id } }));
    },
    onSuccess: finish,
    onError: (failure) => {
      setError(errorMessage(failure));
    },
  });

  const members = session?.members ?? [];
  const current = session?.member ?? null;
  const showForm = adding || members.length === 0;

  return (
    <main className="mx-auto w-full max-w-md px-4 pt-[calc(env(safe-area-inset-top)+32px)] pb-12">
      <h1 className="text-title font-extrabold">Who’s using this phone?</h1>
      <p className="mt-2 mb-6 text-body text-ink-soft">
        Pick your name so everyone can see who added or checked off what.
      </p>
      <ul className="flex flex-col gap-3">
        {members.map((member) => (
          <li key={member.id}>
            <MemberButton
              member={member}
              chosen={member.id === current?.id}
              disabled={choose.isPending}
              onChoose={() => {
                if (member.id === current?.id) void leave();
                else choose.mutate(member.id);
              }}
            />
          </li>
        ))}
      </ul>
      {showForm ? (
        <form
          className="mt-6 flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) addMe.mutate(name.trim());
          }}
        >
          <label htmlFor={nameId} className="text-body font-semibold">
            Your name
          </label>
          <input
            id={nameId}
            value={name}
            maxLength={40}
            autoComplete="given-name"
            onChange={(event) => {
              setName(event.target.value);
            }}
            className="min-h-12 rounded-button border-2 border-rule bg-paper px-4 text-body"
          />
          <Button type="submit" block disabled={addMe.isPending || !name.trim()}>
            Add me
          </Button>
          {members.length > 0 ? (
            <Button
              variant="quiet"
              block
              onClick={() => {
                setAdding(false);
                setName("");
              }}
            >
              Cancel
            </Button>
          ) : null}
        </form>
      ) : (
        <Button
          variant="secondary"
          block
          className="mt-4"
          onClick={() => {
            setAdding(true);
          }}
        >
          <UserPlus aria-hidden="true" />
          Someone else
        </Button>
      )}
      <p role="alert" className="mt-3 min-h-7 text-secondary font-semibold text-tomato">
        {error}
      </p>
      {from || current ? (
        <Button
          variant="quiet"
          block
          onClick={() => {
            void leave();
          }}
        >
          Back
        </Button>
      ) : (
        <Button
          variant="quiet"
          block
          onClick={() => {
            void navigate({ to: "/" });
          }}
        >
          Skip for now
        </Button>
      )}
    </main>
  );
}
