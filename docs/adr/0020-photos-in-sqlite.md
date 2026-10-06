# ADR 0020: Household meal photos are stored in SQLite as WebP

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

Meals can have an optional photo taken by the household. Storing those photos as files under `/data` would mean separate backup, export and cleanup logic. One household will have perhaps 100–300 photos.

## Decision

- **Processing:** uploaded photos are resized server-side with Pillow and stored as WebP blobs in a `photos` table:
  - the main image is at most 1600 px on its long edge;
  - a thumbnail is at most 400 px;
  - EXIF data is stripped.
- **Serving:** they're served at stable URLs with an ETag and long-lived caching.
- **Backups and export:** photos are included automatically. Export embeds them as base64.

## Consequences

- The database grows by roughly 100–200 KB per photo, which is fine at this scale.
- Backups, restore and export stay single-file and complete.
- Kroger product photos are never stored this way. They stay hot-linked (ADR 0016).
