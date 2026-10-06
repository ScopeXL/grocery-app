# ADR 0015: Offline shopping with a snapshot, an idempotent op outbox and last-writer-wins

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

Shopping happens in aisles with weak or no signal, sometimes with two shoppers on one trip. iOS has no Background Sync, can suspend the app, and keeps a home-screen app's storage separate from Safari. The design must never show an error wall offline.

## Decision

**On the phone**
- An opened trip is stored in IndexedDB (`idb`, with versioned migrations), and its product photos are cached by the service worker for the trip.
- Check-offs go into an IndexedDB **outbox** as ops with client-generated `op_id`s and absolute values, never toggles:
  - `item.set_state` (todo, done, missed)
  - `item.set_note`
  - `trip.finish`
  - `trip.reopen`
- The screen shows server state with pending ops on top, through a pure `deriveView`.

**Sync and conflicts**
- The outbox flushes when:
  - the stream opens;
  - the phone comes back online;
  - the app becomes visible;
  - the app starts;
  - every 15 s while ops are pending.
- `POST /api/trips/{id}/ops` applies a batch idempotently, using an `applied_ops` table.
- **Conflict rule: last writer wins, per item field.**
  - State, note and trip status are separate fields.
  - Ops are ordered by `effective_ts = min(client_ts, received_at)`.
  - Client clocks are corrected from `X-Server-Time-Ms` and kept strictly increasing per device, so an Undo always beats the action it undoes.
  - The clamp stops a phone with a fast clock from claiming the future.
  - Ties go to the later arrival.
- After a trip is finished elsewhere, item ops are still accepted for 24 h; later ones are rejected as `trip_closed`. Finishing a trip offline is just another op.

**Planning screens** are readable offline but **write only while online**. Their edits depend on the server (pricing, merging, deletes), where last-writer-wins isn't enough.

**Updates and versions**
- The service worker uses prompt-to-update and never reloads during shopping.
- The server accepts every op version ever shipped, because an offline phone may still be running an old build.

## Consequences

- Shoppers can always keep going, and two shoppers converge without dialogs.
- An offline action is never lost silently; it shows up again for review.
- Concurrent planning edits while offline aren't supported. That's an acceptable trade-off, since planning usually happens at home.
- Tests cover offline, conflicts, clock skew, undo compaction, late ops and dropped streams ([PLAN §9.8](../PLAN.md#98-tests-for-this-layer)).
