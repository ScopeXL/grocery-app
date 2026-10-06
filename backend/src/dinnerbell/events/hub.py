"""In-process event hub for server-sent events (docs/PLAN.md §9.3, docs/adr/0014).

* Every frame gets a stream position ``epoch:seq``: ``epoch`` is random per process start and
  ``seq`` has no gaps, so a client can tell when it missed something.
* The last ``ring_size`` frames are kept so a reconnecting client can be caught up (replay);
  otherwise it is told to refetch (resync).
* Each connection has a bounded queue. If it fills, the connection is marked overflowed and the
  client gets a ``resync`` instead of silently losing frames.

This lives in memory, which is only correct because exactly one process serves the API.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

ReplayMode = Literal["live", "replay", "resync"]


@dataclass(frozen=True, slots=True)
class Frame:
    seq: int
    text: str


STOP = Frame(seq=-1, text="")


@dataclass(eq=False)
class StreamConnection:
    device_id: str
    epoch: int
    queue: asyncio.Queue[Frame]
    overflowed: bool = False
    stopped: bool = False


def render(data: dict[str, Any], position: str | None = None) -> str:
    body = json.dumps(data, separators=(",", ":"), default=str)
    prefix = f"id: {position}\n" if position else ""
    return f"{prefix}data: {body}\n\n"


@dataclass
class EventHub:
    ring_size: int = 1024
    queue_size: int = 256
    ping_interval_s: float = 15.0
    epoch: str = field(default_factory=lambda: secrets.token_hex(4))
    seq: int = 0
    _ring: deque[Frame] = field(init=False)
    _connections: set[StreamConnection] = field(default_factory=set[StreamConnection])
    closing: bool = False

    def __post_init__(self) -> None:
        self._ring = deque(maxlen=self.ring_size)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self.seq += 1
        data = {"type": event_type, **(payload or {})}
        frame = Frame(self.seq, render(data, f"{self.epoch}:{self.seq}"))
        self._ring.append(frame)
        for conn in self._connections:
            if conn.overflowed or conn.stopped:
                continue
            try:
                conn.queue.put_nowait(frame)
            except asyncio.QueueFull:
                conn.overflowed = True

    def register(self, device_id: str, epoch: int) -> StreamConnection:
        conn = StreamConnection(device_id, epoch, asyncio.Queue(maxsize=self.queue_size))
        self._connections.add(conn)
        return conn

    def unregister(self, conn: StreamConnection) -> None:
        self._connections.discard(conn)

    def parse_position(self, value: str | None) -> tuple[str, int] | None:
        if not value or ":" not in value:
            return None
        epoch, _, seq = value.rpartition(":")
        try:
            return epoch, int(seq)
        except ValueError:
            return None

    def catch_up(self, since: str | None) -> tuple[ReplayMode, list[Frame], int]:
        """Decide how a (re)connecting client resumes. Returns (mode, backlog, start_seq)."""
        position = self.parse_position(since)
        if position is None:
            return ("resync" if since else "live"), [], self.seq
        epoch, last_seq = position
        oldest = self._ring[0].seq if self._ring else self.seq + 1
        if epoch != self.epoch or last_seq > self.seq or last_seq < oldest - 1:
            return "resync", [], self.seq
        backlog = [frame for frame in self._ring if frame.seq > last_seq]
        return "replay", backlog, last_seq

    def _stop(self, conn: StreamConnection) -> None:
        conn.stopped = True
        try:
            conn.queue.put_nowait(STOP)
        except asyncio.QueueFull:
            conn.overflowed = True  # the stream loop checks `stopped` first anyway

    def drop_devices(self, device_ids: set[str]) -> None:
        for conn in list(self._connections):
            if conn.device_id in device_ids:
                self._stop(conn)

    def drop_all(self) -> None:
        for conn in list(self._connections):
            self._stop(conn)

    def close(self) -> None:
        self.closing = True
        self.drop_all()
