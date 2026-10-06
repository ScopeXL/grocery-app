/**
 * The only way the app talks to the API: a typed openapi-fetch client (docs/adr/0018).
 *
 * * Mutations carry the CSRF header `X-Dinner-Bell: 1` (docs/PLAN.md §10.3).
 * * Every response feeds the clock offset and the reachability store.
 * * A non-JSON reply (e.g. a proxy's 502 HTML page) counts as "server unreachable".
 */
import createClient, { type Middleware } from "openapi-fetch";

import { recordClockSample } from "../lib/clock";
import { markReachable, markUnreachable } from "../lib/connection";
import type { paths } from "./schema";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const OFFLINE_MESSAGE = "You're offline. Try again when you have signal.";
const sentAt = new WeakMap<Request, number>();

const middleware: Middleware = {
  onRequest({ request }) {
    sentAt.set(request, Date.now());
    if (request.method !== "GET" && request.method !== "HEAD") {
      request.headers.set("X-Dinner-Bell", "1");
    }
    return request;
  },
  onResponse({ request, response }) {
    const serverTime = Number(response.headers.get("X-Server-Time-Ms"));
    const started = sentAt.get(request);
    if (started !== undefined && serverTime) recordClockSample(started, Date.now(), serverTime);
    const isJson = (response.headers.get("content-type") ?? "").includes("application/json");
    if (response.status >= 502 && !isJson) {
      markUnreachable();
    } else {
      markReachable();
    }
    return response;
  },
  onError() {
    markUnreachable();
    return new ApiError(0, "offline", OFFLINE_MESSAGE);
  },
};

export const api = createClient<paths>({ baseUrl: "" });
api.use(middleware);

interface ErrorEnvelope {
  error?: { code?: string; message?: string };
}

/** Unwrap an openapi-fetch result: return data, or throw an ApiError with the server's message. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || !result.response.ok) {
    const envelope = (result.error ?? {}) as ErrorEnvelope;
    throw new ApiError(
      result.response.status,
      envelope.error?.code ?? "error",
      envelope.error?.message ?? "Something went wrong. Try again.",
    );
  }
  return result.data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return OFFLINE_MESSAGE;
}
