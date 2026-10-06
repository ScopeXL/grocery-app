# ADR 0014: Live updates use server-sent events; commands use REST

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

Two people may plan or shop at the same time from different phones, and everyone must see the same list live. The reference apps use SSE successfully (an invariant there: "SSE for push, REST for commands"). WebSockets would add a second protocol for traffic that only flows one way.

## Decision

**The stream**
- One household-wide stream: `GET /api/events?since=<epoch>:<seq>`.
- Each frame is JSON carrying a `type`.
- Every frame has a stream position, `epoch:seq`.
  - `epoch` is random per server start; `seq` has no gaps.
  - A ring buffer keeps the last 1024 frames for replay.
  - The client reconnects with `since`. The server either replays the missed frames or sends `resync`, which tells the client to refetch.
- The heartbeat is a real data event (`ping`) every 15 s, because comment lines never reach JavaScript. The client reconnects after 40 s with no frame.
- Headers: `no-cache, no-transform` and `X-Accel-Buffering: no`. The app never gzips responses.

**What events carry**
- Trip events carry the changed item states, so other phones merge them by version.
- Planning events trigger a debounced refetch.

**Robustness**
- If a proxy turns out to buffer the stream, the client quietly falls back to polling.
- The client closes the stream when the app is hidden and reopens it when visible.
- On error it probes the session, which avoids reconnect loops on 401.

All writes go through REST. Trip check-offs use the batched ops endpoint (ADR 0015).

## Consequences

- One worker holds the hub in memory (ADR 0002).
- The tests need a hand-written ASGI harness, because `httpx.ASGITransport` buffers whole responses. There's also one real-uvicorn smoke test and a manual proxy matrix.
- Proxy configuration is the main deployment risk. It's documented per proxy and verified during the M0 deploy.
