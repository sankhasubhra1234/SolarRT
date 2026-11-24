"""Small async TTL cache that serves stale data when a refresh fails.

It is bounded (least-recently-used entries are evicted) so that requests for endless
different places or coordinates can't grow the server's memory without limit. Stale data is
served only up to an optional ``max_stale`` age; beyond that the refresh error is raised so
the API can report the data as unavailable instead of silently showing an old forecast.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)


@dataclass
class Entry:
    value: Any
    fetched_at: float


class TTLCache:
    def __init__(self, max_entries: int = 5000,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.max_entries = max_entries
        self._clock = clock
        self._data: OrderedDict[str, Entry] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    def __len__(self) -> int:
        return len(self._data)

    def _put(self, key: str, value: Any) -> None:
        self._data[key] = Entry(value, self._clock())
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            old, _ = self._data.popitem(last=False)
            self._locks.pop(old, None)

    async def get(self, key: str, ttl: float, loader: Callable[[], Awaitable[Any]],
                  max_stale: float | None = None) -> tuple[Any, bool, float]:
        """Return ``(value, stale, age_seconds)``.

        Refreshes when older than ``ttl``; on failure returns the previous value marked
        stale if it is no older than ``max_stale`` seconds, otherwise re-raises. With no
        cached value at all the loader's exception is always re-raised.
        """
        entry = self._data.get(key)
        if entry and self._clock() - entry.fetched_at < ttl:
            self._data.move_to_end(key)
            return entry.value, False, self._clock() - entry.fetched_at

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self._data.get(key)  # another request may have refreshed it meanwhile
            age = self._clock() - entry.fetched_at if entry else 0.0
            if entry and age < ttl:
                return entry.value, False, age
            try:
                value = await loader()
            except Exception as exc:
                if entry is None:
                    self._locks.pop(key, None)
                    raise
                age = self._clock() - entry.fetched_at
                if max_stale is not None and age > max_stale:
                    log.warning("Refresh of %s failed (%s) and cached data is %ds old; "
                                "refusing to serve it", key.split(":")[0],
                                type(exc).__name__, int(age))
                    raise
                # Only the key's kind (e.g. "wx"), never per-user parts such as coordinates
                log.warning("Refresh of %s failed (%s); serving stale data (%ds old)",
                            key.split(":")[0], type(exc).__name__, int(age))
                return entry.value, True, age
            self._put(key, value)
            return value, False, 0.0

    def clear(self) -> None:
        self._data.clear()
        self._locks.clear()
