import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Eye, EyeOff } from "lucide-react";
import { useId, useState } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { normalizeCode } from "../../lib/joinCode";
import { outbox } from "../../lib/outbox";
import { rememberSignedIn } from "../../lib/session";
import { BellMark } from "../../ui/BellMark";
import { Button } from "../../ui/Button";
import { useJoinWithCode } from "./useJoin";

function PasswordForm({ onUseCode }: { onUseCode: () => void }) {
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputId = useId();
  const errorId = useId();

  const signIn = useMutation({
    mutationFn: async (value: string) =>
      unwrap(await api.POST("/api/auth/login", { body: { password: value } })),
    onSuccess: async (session) => {
      rememberSignedIn(true);
      void outbox.resume(); // taps saved while signed out go out now
      queryClient.setQueryData(qk.session(), session);
      await navigate({ to: session.member ? "/" : "/who" });
    },
    onError: (failure) => {
      setError(errorMessage(failure));
    },
  });

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        setError(null);
        signIn.mutate(password);
      }}
    >
      <label htmlFor={inputId} className="text-body font-semibold">
        Household password
      </label>
      <div className="flex gap-2">
        <input
          id={inputId}
          type={visible ? "text" : "password"}
          autoComplete="current-password"
          autoCapitalize="none"
          spellCheck={false}
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
          }}
          aria-describedby={errorId}
          aria-invalid={error ? true : undefined}
          className="min-h-12 min-w-0 flex-1 rounded-button border-2 border-rule bg-paper px-4 text-body"
        />
        <Button
          variant="secondary"
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          onClick={() => {
            setVisible((v) => !v);
          }}
          className="min-h-12 w-12 px-0"
        >
          {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
        </Button>
      </div>
      <p id={errorId} role="alert" className="min-h-7 text-secondary font-semibold text-tomato">
        {error}
      </p>
      <Button type="submit" block pending={signIn.isPending} disabled={password.length === 0}>
        {signIn.isPending ? "Signing in…" : "Sign in"}
      </Button>
      <p className="mt-2 text-secondary text-ink-soft">
        Ask whoever set up Dinner Bell for the password.
      </p>
      <Button variant="quiet" className="-ml-5 self-start" onClick={onUseCode}>
        Use a code from another phone
      </Button>
    </form>
  );
}

function CodeForm({ onUsePassword }: { onUsePassword: () => void }) {
  const [code, setCode] = useState("");
  const join = useJoinWithCode();
  const inputId = useId();
  const errorId = useId();
  const hintId = useId();
  const valid = normalizeCode(code);

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) join.mutate(valid);
      }}
    >
      <label htmlFor={inputId} className="text-body font-semibold">
        Code from another phone
      </label>
      <input
        id={inputId}
        value={code}
        maxLength={12}
        autoComplete="one-time-code"
        autoCapitalize="characters"
        autoCorrect="off"
        spellCheck={false}
        onChange={(event) => {
          setCode(event.target.value);
        }}
        aria-describedby={`${hintId} ${errorId}`}
        aria-invalid={join.isError ? true : undefined}
        className="min-h-12 rounded-button border-2 border-rule bg-paper px-4 text-title font-extrabold tracking-widest uppercase"
      />
      <p id={hintId} className="text-secondary text-ink-soft">
        On a phone that’s already signed in, open More, then Settings, then Add a phone.
      </p>
      <p id={errorId} role="alert" className="min-h-7 text-secondary font-semibold text-tomato">
        {join.isError ? errorMessage(join.error) : null}
      </p>
      <Button type="submit" block pending={join.isPending} disabled={!valid}>
        {join.isPending ? "Signing in…" : "Sign in"}
      </Button>
      <Button variant="quiet" className="-ml-5 self-start" onClick={onUsePassword}>
        Use the password instead
      </Button>
    </form>
  );
}

export function SignInScreen() {
  const [mode, setMode] = useState<"password" | "code">("password");
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-center px-4 py-10">
      <div className="mb-10 flex flex-col items-center gap-4">
        <BellMark className="size-24" />
        <h1 className="text-title font-extrabold">Dinner Bell</h1>
      </div>
      {mode === "password" ? (
        <PasswordForm
          onUseCode={() => {
            setMode("code");
          }}
        />
      ) : (
        <CodeForm
          onUsePassword={() => {
            setMode("password");
          }}
        />
      )}
    </main>
  );
}
