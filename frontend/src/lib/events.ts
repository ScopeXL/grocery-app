/**
 * Live updates over server-sent events (docs/PLAN.md §9.3, docs/adr/0014).
 *
 * * One household-wide stream. Every frame carries a position `epoch:seq`; we reconnect with
 *   `?since=` so the server can replay what we missed (a fresh EventSource never sends
 *   Last-Event-ID itself).
 * * The server's `ping` is a real data event every 15 s; with nothing for 40 s we assume the
 *   connection is dead (common on mobile) and reconnect.
 * * Closed while the app is hidden, reopened when visible.
 * * After an error we probe the session before reconnecting, so an expired sign-in can't turn
 *   into an endless 401 loop.
 * * If a proxy appears to buffer the stream, we quietly fall back to polling.
 */
import { createStore } from "./store";

export type LiveStatus = "connecting" | "live" | "polling" | "offline" | "signed-out";

export interface ServerEvent {
  type: string;
  [key: string]: unknown;
}

export type SessionProbe = () => Promise<"ok" | "signed-out" | "offline">;

export interface LiveUpdatesOptions {
  url?: string;
  onEvent: (event: ServerEvent) => void;
  onPoll: () => void;
  probeSession: SessionProbe;
  createSource?: (url: string) => EventSource;
  random?: () => number;
  now?: () => number;
  document?: Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
}

export const liveStatus = createStore<LiveStatus>("connecting");

export const WATCHDOG_MS = 40_000;
export const HELLO_TIMEOUT_MS = 5_000;
const BACKOFF_START_MS = 500;
const BACKOFF_MAX_MS = 5_000;
const POLL_EVERY_MS = 30_000;
const RETRY_STREAM_WHILE_POLLING_MS = 60_000;
const FAILURE_WINDOW_MS = 60_000;
const FAILURES_BEFORE_POLLING = 3;

export class LiveUpdates {
  private source: EventSource | null = null;
  private position: string | null = null;
  private lastSeq: number | null = null;
  private attempt = 0;
  private failures: number[] = [];
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private watchdog: ReturnType<typeof setTimeout> | undefined;
  private helloTimer: ReturnType<typeof setTimeout> | undefined;
  private pollTimer: ReturnType<typeof setInterval> | undefined;
  private running = false;
  private readonly url: string;
  private readonly createSource: (url: string) => EventSource;
  private readonly random: () => number;
  private readonly now: () => number;
  private readonly doc: NonNullable<LiveUpdatesOptions["document"]>;

  constructor(private readonly options: LiveUpdatesOptions) {
    this.url = options.url ?? "/api/events";
    this.createSource = options.createSource ?? ((url) => new EventSource(url));
    this.random = options.random ?? Math.random;
    this.now = options.now ?? Date.now;
    this.doc = options.document ?? document;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.doc.addEventListener("visibilitychange", this.onVisibility);
    if (this.doc.visibilityState !== "hidden") this.open();
  }

  stop(): void {
    this.running = false;
    this.doc.removeEventListener("visibilitychange", this.onVisibility);
    this.close();
    this.stopPolling();
    clearTimeout(this.retryTimer);
  }

  private readonly onVisibility = (): void => {
    if (!this.running) return;
    if (this.doc.visibilityState === "hidden") {
      this.close();
    } else if (!this.source) {
      this.attempt = 0;
      this.open();
    }
  };

  private open(): void {
    this.close();
    liveStatus.set((status) => (status === "polling" ? status : "connecting"));
    const url = this.position ? `${this.url}?since=${encodeURIComponent(this.position)}` : this.url;
    const source = this.createSource(url);
    this.source = source;
    source.onmessage = (message: MessageEvent<string>) => {
      this.handleMessage(message);
    };
    source.onerror = () => {
      this.handleError();
    };
    this.armWatchdog();
    clearTimeout(this.helloTimer);
    this.helloTimer = setTimeout(() => {
      // Connected but no hello: something between us and the server is buffering the stream.
      this.startPolling();
    }, HELLO_TIMEOUT_MS);
  }

  private close(): void {
    clearTimeout(this.watchdog);
    clearTimeout(this.helloTimer);
    if (this.source) {
      this.source.onmessage = null;
      this.source.onerror = null;
      this.source.close();
      this.source = null;
    }
  }

  private armWatchdog(): void {
    clearTimeout(this.watchdog);
    this.watchdog = setTimeout(() => {
      this.reconnect();
    }, WATCHDOG_MS);
  }

  private handleMessage(message: MessageEvent<string>): void {
    this.armWatchdog();
    let event: ServerEvent;
    try {
      event = JSON.parse(message.data) as ServerEvent;
    } catch {
      return;
    }
    if (event.type === "hello") {
      clearTimeout(this.helloTimer);
      this.attempt = 0;
      this.failures = [];
      this.stopPolling();
      const epoch = String(event.epoch);
      const seq = Number(event.seq);
      this.position = `${epoch}:${seq}`;
      this.lastSeq = seq;
      liveStatus.set("live");
    } else if (message.lastEventId) {
      const seq = Number(message.lastEventId.split(":").pop());
      if (this.lastSeq !== null && seq !== this.lastSeq + 1) {
        // A gap: reconnect from the last frame we did see, and let the server replay or resync.
        this.reconnect();
        return;
      }
      this.position = message.lastEventId;
      this.lastSeq = seq;
    }
    this.options.onEvent(event);
    if (event.type === "session.expired") {
      liveStatus.set("signed-out");
      this.stop();
    }
  }

  private reconnect(): void {
    this.close();
    this.open();
  }

  private handleError(): void {
    this.close();
    const now = this.now();
    this.failures = [...this.failures.filter((at) => now - at < FAILURE_WINDOW_MS), now];
    void this.options.probeSession().then((result) => {
      if (!this.running) return;
      if (result === "signed-out") {
        liveStatus.set("signed-out");
        this.options.onEvent({ type: "session.expired" });
        this.stop();
        return;
      }
      if (result === "offline") {
        liveStatus.set("offline");
      } else if (this.failures.length >= FAILURES_BEFORE_POLLING) {
        // The API answers but the stream keeps failing: probably a buffering proxy.
        this.startPolling();
      }
      this.scheduleRetry();
    });
  }

  private scheduleRetry(): void {
    clearTimeout(this.retryTimer);
    const base = Math.min(BACKOFF_MAX_MS, BACKOFF_START_MS * 2 ** this.attempt);
    const delay =
      liveStatus.get() === "polling"
        ? RETRY_STREAM_WHILE_POLLING_MS
        : base / 2 + this.random() * (base / 2);
    this.attempt += 1;
    this.retryTimer = setTimeout(() => {
      if (this.running && this.doc.visibilityState !== "hidden") this.open();
    }, delay);
  }

  private startPolling(): void {
    if (this.pollTimer !== undefined) return;
    liveStatus.set("polling");
    this.options.onPoll();
    this.pollTimer = setInterval(() => {
      this.options.onPoll();
    }, POLL_EVERY_MS);
  }

  private stopPolling(): void {
    if (this.pollTimer === undefined) return;
    clearInterval(this.pollTimer);
    this.pollTimer = undefined;
  }
}
