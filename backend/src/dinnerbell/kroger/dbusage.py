"""Kroger usage counters kept in `kroger_api_usage`, so a restart remembers a 429 block."""

from __future__ import annotations

from datetime import timedelta

from dinnerbell.db.engine import Database
from dinnerbell.kroger.models import KrogerApiUsage
from dinnerbell.kroger.usage import Bucket, Usage


class DbUsageStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def load(self, bucket: Bucket) -> Usage:
        async with self._db.read() as session:
            row = await session.get(KrogerApiUsage, bucket.value)
        if row is None:
            return Usage(bucket)
        return Usage(
            bucket=bucket,
            window_started_at=row.window_started_at,
            calls=row.calls,
            blocked_until=row.blocked_until,
            last_429_at=row.last_429_at,
            probe_backoff=timedelta(seconds=row.probe_backoff_s) if row.probe_backoff_s else None,
        )

    async def save(self, usage: Usage) -> None:
        async with self._db.write() as tx:
            row = await tx.session.get(KrogerApiUsage, usage.bucket.value)
            if row is None:
                row = KrogerApiUsage(api=usage.bucket.value)
                tx.session.add(row)
            row.window_started_at = usage.window_started_at
            row.calls = usage.calls
            row.blocked_until = usage.blocked_until
            row.last_429_at = usage.last_429_at
            backoff = usage.probe_backoff
            row.probe_backoff_s = int(backoff.total_seconds()) if backoff else None
