"""Cache manager for MCP Icon Server.

Provides LRU-bounded in-memory caching with TTL expiry and periodic cleanup.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Any

from ..models import CacheEntry, SelectionData, SelectionStatus

__all__ = ["CacheManager"]


class CacheManager:
    """In-memory cache with LRU eviction, TTL expiry, and periodic cleanup.

    Args:
        expiry_seconds: Time-to-live for cache entries in seconds.
        max_icon_entries: Maximum number of icon cache entries (LRU eviction).
        max_search_entries: Maximum number of search cache entries (LRU eviction).
        cleanup_interval: Seconds between automatic expired-entry sweeps.
    """

    def __init__(
        self,
        expiry_seconds: float = 1800.0,
        max_icon_entries: int = 500,
        max_search_entries: int = 200,
        cleanup_interval: float = 300.0,
    ):
        self.expiry_seconds = expiry_seconds
        self.max_icon_entries = max_icon_entries
        self.max_search_entries = max_search_entries
        self.cleanup_interval = cleanup_interval

        # OrderedDict gives us O(1) move-to-end for LRU
        self._icon_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._search_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._selection_cache: dict[str, SelectionData] = {}
        # asyncio.Event per search_id — set when selection reaches terminal state
        self._selection_events: dict[str, asyncio.Event] = {}

        # Background cleanup task handle
        self._cleanup_task: asyncio.Task[None] | None = None

    # --- Lifecycle ---

    def start_cleanup_task(self) -> None:
        """Start the periodic background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    def stop_cleanup_task(self) -> None:
        """Stop the periodic background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def _periodic_cleanup(self) -> None:
        """Periodically remove expired entries."""
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)
                self._evict_expired()
        except asyncio.CancelledError:
            pass

    def _evict_expired(self) -> None:
        """Remove all expired entries from both caches."""
        now = time.time()
        for key in list(self._icon_cache.keys()):
            if now - self._icon_cache[key].timestamp > self.expiry_seconds:
                del self._icon_cache[key]
        for key in list(self._search_cache.keys()):
            if now - self._search_cache[key].timestamp > self.expiry_seconds:
                del self._search_cache[key]

    # --- Icon Cache ---

    def get_icon(self, key: str) -> Any | None:
        """Get an icon cache entry if it exists and is not expired."""
        entry = self._icon_cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.timestamp > self.expiry_seconds:
            del self._icon_cache[key]
            return None
        # Move to end (most recently used)
        self._icon_cache.move_to_end(key)
        return entry.data

    def set_icon(self, key: str, data: Any) -> None:
        """Set an icon cache entry with LRU eviction."""
        if key in self._icon_cache:
            # Update existing entry and move to end
            self._icon_cache[key] = CacheEntry(data=data, timestamp=time.time(), key=key)
            self._icon_cache.move_to_end(key)
        else:
            # Evict oldest if at capacity
            while len(self._icon_cache) >= self.max_icon_entries:
                self._icon_cache.popitem(last=False)
            self._icon_cache[key] = CacheEntry(data=data, timestamp=time.time(), key=key)

    # --- Search Cache ---

    def get_search(self, key: str) -> Any | None:
        """Get a search cache entry if it exists and is not expired."""
        entry = self._search_cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.timestamp > self.expiry_seconds:
            del self._search_cache[key]
            return None
        # Move to end (most recently used)
        self._search_cache.move_to_end(key)
        return entry.data

    def set_search(self, key: str, data: Any) -> None:
        """Set a search cache entry with LRU eviction."""
        if key in self._search_cache:
            self._search_cache[key] = CacheEntry(data=data, timestamp=time.time(), key=key)
            self._search_cache.move_to_end(key)
        else:
            while len(self._search_cache) >= self.max_search_entries:
                self._search_cache.popitem(last=False)
            self._search_cache[key] = CacheEntry(data=data, timestamp=time.time(), key=key)

    # --- Selection Cache ---

    def _get_or_create_event(self, search_id: str) -> asyncio.Event:
        """Return (creating if necessary) the asyncio.Event for a search_id."""
        if search_id not in self._selection_events:
            self._selection_events[search_id] = asyncio.Event()
        return self._selection_events[search_id]

    def get_selection_event(self, search_id: str) -> asyncio.Event:
        """Return the asyncio.Event for a search_id (creates if not present)."""
        return self._get_or_create_event(search_id)

    def get_selection(self, search_id: str) -> SelectionData | None:
        """Get selection data for a search ID."""
        return self._selection_cache.get(search_id)

    def set_selection(self, search_id: str, data: SelectionData) -> None:
        """Set selection data and notify waiters if the selection is terminal."""
        self._selection_cache[search_id] = data
        # Signal waiters when the selection reaches a terminal state
        if data.status in (SelectionStatus.COMPLETED, SelectionStatus.FAILED):
            event = self._get_or_create_event(search_id)
            event.set()

    def delete_selection(self, search_id: str) -> None:
        """Delete selection data and clean up the associated event."""
        self._selection_cache.pop(search_id, None)
        self._selection_events.pop(search_id, None)

    # --- Stats & Cleanup ---

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        now = time.time()
        icon_valid = sum(
            1
            for e in self._icon_cache.values()
            if now - e.timestamp <= self.expiry_seconds
        )
        icon_expired = len(self._icon_cache) - icon_valid
        search_valid = sum(
            1
            for e in self._search_cache.values()
            if now - e.timestamp <= self.expiry_seconds
        )
        search_expired = len(self._search_cache) - search_valid

        return {
            "icon_cache": {
                "valid": icon_valid,
                "expired": icon_expired,
                "total": len(self._icon_cache),
                "max_entries": self.max_icon_entries,
            },
            "search_cache": {
                "valid": search_valid,
                "expired": search_expired,
                "total": len(self._search_cache),
                "max_entries": self.max_search_entries,
            },
            "selection_cache": {
                "total": len(self._selection_cache),
            },
            "cache_expiry_minutes": int(self.expiry_seconds / 60),
            "cleanup_interval_seconds": int(self.cleanup_interval),
        }

    def clear(self, expired_only: bool = False) -> dict[str, int]:
        """Clear cache entries. Returns count of cleared entries."""
        if expired_only:
            now = time.time()
            icon_cleared = 0
            for key in list(self._icon_cache.keys()):
                if now - self._icon_cache[key].timestamp > self.expiry_seconds:
                    del self._icon_cache[key]
                    icon_cleared += 1
            search_cleared = 0
            for key in list(self._search_cache.keys()):
                if now - self._search_cache[key].timestamp > self.expiry_seconds:
                    del self._search_cache[key]
                    search_cleared += 1
            return {"icon_cleared": icon_cleared, "search_cleared": search_cleared}
        else:
            icon_count = len(self._icon_cache)
            search_count = len(self._search_cache)
            self._icon_cache.clear()
            self._search_cache.clear()
            return {"icon_cleared": icon_count, "search_cleared": search_count}
