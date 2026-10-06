/** The signed-in session, and the rule that a phone signed in before may open offline. */
import { api, ApiError, unwrap } from "../api/client";
import type { components } from "../api/schema";

export type Session = components["schemas"]["SessionOut"];
export type Member = components["schemas"]["MemberOut"];

const SIGNED_IN_KEY = "db.signed-in";

export function rememberSignedIn(value: boolean): void {
  try {
    if (value) localStorage.setItem(SIGNED_IN_KEY, "1");
    else localStorage.removeItem(SIGNED_IN_KEY);
  } catch {
    // storage unavailable: offline start just won't be allowed
  }
}

export function signedInBefore(): boolean {
  try {
    return localStorage.getItem(SIGNED_IN_KEY) === "1";
  } catch {
    return false;
  }
}

/** The session, or null when signed out. Throws ApiError(0) when the server can't be reached. */
export async function fetchSession(): Promise<Session | null> {
  const result = await api.GET("/api/auth/session");
  if (result.response.status === 401) {
    rememberSignedIn(false);
    return null;
  }
  const session = unwrap(result);
  rememberSignedIn(true);
  return session;
}

export async function probeSession(): Promise<"ok" | "signed-out" | "offline"> {
  try {
    return (await fetchSession()) ? "ok" : "signed-out";
  } catch (error) {
    return error instanceof ApiError && error.status !== 0 ? "ok" : "offline";
  }
}
