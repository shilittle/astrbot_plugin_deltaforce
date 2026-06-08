from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import time
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    value: Any


class TTLCache:
    def __init__(self) -> None:
        self._items: dict[Hashable, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: Hashable) -> Any | None:
        now = time.monotonic()
        async with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._items.pop(key, None)
                return None
            return entry.value

    async def set(self, key: Hashable, value: Any, ttl_seconds: int | float) -> None:
        async with self._lock:
            self._items[key] = _CacheEntry(time.monotonic() + float(ttl_seconds), value)

    async def get_or_set(
        self,
        key: Hashable,
        ttl_seconds: int | float,
        factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory()
        await self.set(key, value, ttl_seconds)
        return value

    async def clear(self) -> None:
        async with self._lock:
            self._items.clear()


def seconds_until_next_local_time(hour: int, minute: int, minimum: int = 60) -> int:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(minimum, int((target - now).total_seconds()))
