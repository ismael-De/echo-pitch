"""Spend guard for a public URL: decides per stream whether Foundry may be used.

When a limit is hit the stream still works, it just falls back to the offline agents (templates),
so nobody sees an error and the Azure credit cannot be burned. All limits are env-configurable:

  BUDGET_STREAMS_PER_IP_HOUR   Foundry streams one client may start per rolling hour   (default 6)
  BUDGET_STREAMS_PER_DAY       Foundry streams across all clients per UTC day          (default 150, ~ $1.5)
  BUDGET_MAX_CONCURRENT        Foundry streams running at the same time                (default 4)
  BUDGET_MAX_REPLAYS           replay sessions kept in memory (oldest evicted)         (default 200)
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Budget:
    def __init__(self) -> None:
        self.per_ip_hour = _int("BUDGET_STREAMS_PER_IP_HOUR", 6)
        self.per_day = _int("BUDGET_STREAMS_PER_DAY", 150)
        self.max_concurrent = _int("BUDGET_MAX_CONCURRENT", 4)
        self.max_replays = _int("BUDGET_MAX_REPLAYS", 200)
        self._ip: dict[str, deque] = defaultdict(deque)
        self._day, self._day_count, self._live = time.strftime("%Y-%m-%d", time.gmtime()), 0, 0
        self._lock = threading.Lock()

    def acquire(self, client: str, now: float | None = None) -> tuple[bool, str | None]:
        """Reserve one Foundry stream; returns (allowed, reason-if-not)."""
        now = time.time() if now is None else now
        with self._lock:
            day = time.strftime("%Y-%m-%d", time.gmtime(now))
            if day != self._day:
                self._day, self._day_count = day, 0
            q = self._ip[client]
            while q and now - q[0] > 3600:
                q.popleft()
            if self._live >= self.max_concurrent:
                return False, "too many live AI streams right now"
            if self._day_count >= self.per_day:
                return False, "daily AI budget reached"
            if len(q) >= self.per_ip_hour:
                return False, "hourly AI limit for this viewer reached"
            q.append(now)
            self._day_count += 1
            self._live += 1
            return True, None

    def release(self) -> None:
        with self._lock:
            self._live = max(0, self._live - 1)


def client_id(headers, host: str | None) -> str:
    """First X-Forwarded-For hop (set by the Container Apps ingress), else the socket peer."""
    fwd = headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (host or "unknown")
