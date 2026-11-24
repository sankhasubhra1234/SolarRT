"""Small async TTL cache that serves stale data when a refresh fails.

It is bounded (least-recently-used entries are evicted) so that requests for endless
different places or coordinates can't grow the server's memory without limit.
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
    def __init__(self, max_entries: int = 5000) -> None:
        self.max_entries = max_entries
        self._data: OrderedDict[str, Entry] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    def __len__(self) -> int:
        return len(self._data)

    def _put(self, key: str, value: Any) -> None:
        self._data[key] = Entry(value, time.monotonic())
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            old, _ = self._data.popitem(last=False)
            self._locks.pop(old, None)

    async def get(self, key: str, ttl: float, loader: Callable[[], Awaitable[Any]]) -> tuple[Any, bool]:
        """Return (value, stale). Refreshes when older than ttl; on failure returns the
        previous value marked stale, or re-raises if there is nothing cached yet."""
        entry = self._data.get(key)
        if entry and time.monotonic() - entry.fetched_at < ttl:
            self._data.move_to_end(key)
            return entry.value, False

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            entry = self._data.get(key)  # another request may have refreshed it meanwhile
            if entry and time.monotonic() - entry.fetched_at < ttl:
                return entry.value, False
            try:
                value = await loader()
            except Exception as exc:
                if entry is None:
                    self._locks.pop(key, None)
                    raise
                # Only the key's kind (e.g. "wx"), never per-user parts such as coordinates
                log.warning("Refresh of %s failed (%s); serving stale data",
                            key.split(":")[0], type(exc).__name__)
                return entry.value, True
            self._put(key, value)
            return value, False

    def clear(self) -> None:
        self._data.clear()
        self._locks.clear()
