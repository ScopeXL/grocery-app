"""Login rate limiting (docs/PLAN.md §10.4).

Per IP: 5 failures in 15 minutes locks that IP out until the oldest failure ages out.
Globally: 50 failures in an hour pauses all logins for 15 minutes. Signed-in phones are
unaffected. Memory is enough: exactly one process serves the API.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from dinnerbell.core.clock import Clock

PER_IP_LIMIT = 5
PER_IP_WINDOW = timedelta(minutes=15)
GLOBAL_LIMIT = 50
GLOBAL_WINDOW = timedelta(hours=1)
GLOBAL_PAUSE = timedelta(minutes=15)


@dataclass
class LoginLimiter:
    clock: Clock
    _per_ip: dict[str, deque[datetime]] = field(default_factory=dict[str, deque[datetime]])
    _global: deque[datetime] = field(default_factory=deque[datetime])
    _paused_until: datetime | None = None

    def _trim(self, now: datetime) -> None:
        while self._global and now - self._global[0] > GLOBAL_WINDOW:
            self._global.popleft()
        for ip in list(self._per_ip):
            failures = self._per_ip[ip]
            while failures and now - failures[0] > PER_IP_WINDOW:
                failures.popleft()
            if not failures:
                del self._per_ip[ip]

    def retry_after_seconds(self, ip: str) -> int | None:
        """None if a login attempt is allowed now; otherwise seconds to wait."""
        now = self.clock.now()
        self._trim(now)
        if self._paused_until and now < self._paused_until:
            return math.ceil((self._paused_until - now).total_seconds())
        failures = self._per_ip.get(ip)
        if failures and len(failures) >= PER_IP_LIMIT:
            return max(1, math.ceil((failures[0] + PER_IP_WINDOW - now).total_seconds()))
        return None

    def record_failure(self, ip: str) -> None:
        now = self.clock.now()
        self._per_ip.setdefault(ip, deque()).append(now)
        self._global.append(now)
        self._trim(now)
        if len(self._global) >= GLOBAL_LIMIT:
            self._paused_until = now + GLOBAL_PAUSE

    def record_success(self, ip: str) -> None:
        self._per_ip.pop(ip, None)

    def reset(self) -> None:
        self._per_ip.clear()
        self._global.clear()
        self._paused_until = None
