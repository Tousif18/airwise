"""In-memory TTL cache for air quality responses."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Stored cache payload with creation and expiration timestamps."""

    value: T
    cached_at: datetime
    expires_at: datetime


class TTLCache(Generic[T]):
    """Thread-safe in-memory TTL cache."""

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
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
            self._store[key] = entry
        return entry

    def clear(self) -> None:
        """Clear all entries (useful for testing)."""
        with self._lock:
            self._store.clear()
