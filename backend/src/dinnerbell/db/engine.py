"""Database engines and sessions (docs/adr/0002-one-container-one-worker.md).

Two engines point at the same SQLite file:

* the **read** engine (small pool) starts transactions with a plain, deferred ``BEGIN``;
* the **write** engine (exactly one connection) starts them with ``BEGIN IMMEDIATE`` and is
  only used under ``Database.write()``, which also holds an asyncio lock. Events queued during
  a write are published after commit while the lock is still held, so the live-update stream
  always matches commit order.

Following SQLAlchemy's documented recipe, the driver's own transaction handling is disabled
(``isolation_level = None``) and we emit BEGIN ourselves; pragmas are set on every connection.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

BUSY_TIMEOUT_MS = 5000

Publisher = Callable[[str, dict[str, Any]], None]


def install_sqlite_hooks(sync_engine: Engine, *, immediate: bool, foreign_keys: bool) -> None:
    @event.listens_for(sync_engine, "connect")
    def _on_connect(dbapi_connection: Any, connection_record: Any) -> None:  # pyright: ignore[reportUnusedFunction]
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}")
        cursor.close()

    @event.listens_for(sync_engine, "begin")
    def _on_begin(conn: Any) -> None:  # pyright: ignore[reportUnusedFunction]
        conn.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")


@dataclass
class WriteTx:
    session: AsyncSession
    _events: list[tuple[str, dict[str, Any]]] = field(
        default_factory=list[tuple[str, dict[str, Any]]]
    )

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Queue a live-update event; it goes out only if the transaction commits."""
        self._events.append((event_type, payload or {}))


@dataclass
class Database:
    read_engine: AsyncEngine
    write_engine: AsyncEngine
    read_sessions: async_sessionmaker[AsyncSession]
    write_sessions: async_sessionmaker[AsyncSession]
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    publisher: Publisher | None = None

    @asynccontextmanager
    async def read(self) -> AsyncGenerator[AsyncSession]:
        async with self.read_sessions() as session:
            yield session

    @asynccontextmanager
    async def write(self) -> AsyncGenerator[WriteTx]:
        async with self.write_lock:
            async with self.write_sessions() as session:
                tx = WriteTx(session)
                async with session.begin():
                    yield tx
                # Committed. Publish while still holding the lock (commit order == stream order).
                if self.publisher is not None:
                    for event_type, payload in tx._events:  # pyright: ignore[reportPrivateUsage]
                        self.publisher(event_type, payload)

    async def dispose(self) -> None:
        await self.read_engine.dispose()
        await self.write_engine.dispose()


def make_database(db_path: Path, *, read_pool_size: int = 4) -> Database:
    url = f"sqlite+aiosqlite:///{db_path}"
    read_engine = create_async_engine(
        url, poolclass=AsyncAdaptedQueuePool, pool_size=read_pool_size, max_overflow=4
    )
    write_engine = create_async_engine(
        url, poolclass=AsyncAdaptedQueuePool, pool_size=1, max_overflow=0
    )
    install_sqlite_hooks(read_engine.sync_engine, immediate=False, foreign_keys=True)
    install_sqlite_hooks(write_engine.sync_engine, immediate=True, foreign_keys=True)
    return Database(
        read_engine=read_engine,
        write_engine=write_engine,
        read_sessions=async_sessionmaker(read_engine, expire_on_commit=False),
        write_sessions=async_sessionmaker(write_engine, expire_on_commit=False),
    )
