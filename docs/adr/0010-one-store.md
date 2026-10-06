# ADR 0010: One store, with data scoped per store

- **Status:** Accepted (the owner's answer to the open question)
- **Date:** 2026-10-06

## Context

The household shops at one preferred Kroger store. Supporting several stores now would add:
- a per-trip store choice;
- more screens;
- more API calls;
- more to test.

But a second store later shouldn't need a rewrite.

## Decision

- One active store: `household.active_store_id`.
- Everything that varies by store is scoped per store:
  - prices, aisles and stock (the `kroger_product_cache` key includes `location_id`);
  - section walking order (`store_sections.store_id`);
  - trips (`trips.store_id`).
- Items link to products by product ID, which is national, so links don't depend on the store.

## Consequences

- Changing the store in Settings switches prices, aisles and sections without touching meals or items.
- Adding true multi-store support later only needs UI and a per-trip store choice, not schema changes.
