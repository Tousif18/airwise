"""In-memory TTL cache and async request coalescing helpers."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Awaitable, Callable, Generic, TypeVar
from weakref import WeakKeyDictionary

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Stored cache payload with creation and expiration timestamps."""

    value: T
    cached_at: datetime
    expires_at: datetime


class TTLCache(Generic[T]):
    """Thread-safe in-memory TTL cache with bounded capacity."""

    def __init__(self, ttl_seconds: int = 600, max_entries: int = 256) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._store: dict[str, CacheEntry[T]] = {}
        self._lock = Lock()

    def get(self, key: str) -> CacheEntry[T] | None:
        """Return a non-expired cache entry, or None if missing/expired."""
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if now >= entry.expires_at:
                return None
            return entry

    def get_with_staleness(self, key: str) -> tuple[CacheEntry[T] | None, bool]:
        """Return (entry, is_expired) so callers can fall back to stale cache if live fetch fails."""
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None, False
            return entry, now >= entry.expires_at

    def set(self, key: str, value: T, ttl_seconds: int | None = None) -> CacheEntry[T]:
        """Store a value with UTC cached_at and expires_at timestamps."""
        effective_ttl = self._ttl_seconds if ttl_seconds is None else max(0, ttl_seconds)
        now = datetime.now(timezone.utc)
        entry = CacheEntry(
            value=value,
            cached_at=now,
            expires_at=now + timedelta(seconds=effective_ttl),
        )
        with self._lock:
            if key not in self._store and len(self._store) >= self._max_entries:
                # Evict oldest entry (preferring already-expired entries first)
                expired_keys = [k for k, v in self._store.items() if now >= v.expires_at]
                evict_key = (
                    expired_keys[0]
                    if expired_keys
                    else min(self._store.items(), key=lambda item: item[1].cached_at)[0]
                )
                self._store.pop(evict_key, None)
            self._store[key] = entry
        return entry

    def delete(self, key: str) -> None:
        """Remove a specific key from the cache."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all entries (useful for testing)."""
        with self._lock:
            self._store.clear()


class AsyncRequestCoalescer(Generic[T]):
    """Coalesces concurrent identical async calls on the active event loop."""

    def __init__(self) -> None:
        self._loop_tasks: WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Task[T]]] = (
            WeakKeyDictionary()
        )
        self._guard = Lock()

    async def run(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        """Execute `factory` once per concurrent key; additional callers await the same task."""
        loop = asyncio.get_running_loop()
        created = False

        with self._guard:
            tasks = self._loop_tasks.get(loop)
            if tasks is None:
                tasks = {}
                self._loop_tasks[loop] = tasks

            task = tasks.get(key)
            if task is None or task.done():
                task = asyncio.ensure_future(factory())
                tasks[key] = task
                created = True

        try:
            return await asyncio.shield(task)
        finally:
            if created:
                with self._guard:
                    loop_map = self._loop_tasks.get(loop)
                    if loop_map is not None and loop_map.get(key) is task:
                        loop_map.pop(key, None)
