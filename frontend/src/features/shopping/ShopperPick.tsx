/**
 * Check-offs say who made them ("Checked off by Mia"), so shopping mode asks once, with one
 * tap, when this phone hasn't said who's using it (PLAN §9.2). Skipping is fine: check-offs
 * then just don't name anyone.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { fetchSession } from "../../lib/session";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { Sheet } from "../../ui/Sheet";
import { MemberButton } from "../auth/MemberButton";

export function ShopperPick() {
  const queryClient = useQueryClient();
  const session = useQuery({ queryKey: qk.session(), queryFn: fetchSession });
  const [skipped, setSkipped] = useState(false);
  const choose = useMutation({
    mutationFn: async (memberId: string) =>
      unwrap(await api.PUT("/api/auth/member", { body: { member_id: memberId } })),
    onSuccess: (updated) => {
      queryClient.setQueryData(qk.session(), updated);
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const data = session.data;
  const open = Boolean(data && !data.member && data.members.length > 0 && !skipped);
  return (
    <Sheet
      open={open}
      title="Who’s shopping?"
      onClose={() => {
        setSkipped(true);
      }}
    >
      <p className="mb-4 text-body">So everyone can see who checked off what.</p>
      <div className="flex flex-col gap-2">
        {(data?.members ?? []).map((member) => (
          <MemberButton
            key={member.id}
            member={member}
            disabled={choose.isPending}
            onChoose={() => {
              choose.mutate(member.id);
            }}
          />
        ))}
      </div>
      <Button
        variant="quiet"
        className="mt-3 -ml-5"
        onClick={() => {
          setSkipped(true);
        }}
      >
        Skip
      </Button>
    </Sheet>
  );
}
