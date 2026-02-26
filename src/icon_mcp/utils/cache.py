"""Cache manager for MCP Icon Server."""

from __future__ import annotations

import time
from typing import Any

from ..models import CacheEntry, SelectionData, SelectionStatus


class CacheManager:
    """In-memory cache with TTL expiry for icons, searches, and selections."""

    def __init__(self, expiry_seconds: float = 1800.0):
        self.expiry_seconds = expiry_seconds
        self._icon_cache: dict[str, CacheEntry] = {}
        self._search_cache: dict[str, CacheEntry] = {}
        self._selection_cache: dict[str, SelectionData] = {}

    # --- Icon Cache ---

    def get_icon(self, key: str) -> Any | None:
        """Get an icon cache entry if it exists and is not expired."""
        entry = self._icon_cache.get(key)
        if entry is None:
            return None
        if time.time() - entry.timestamp > self.expiry_seconds:
            del self._icon_cache[key]
            return None
        return entry.data

    def set_icon(self, key: str, data: Any) -> None:
        """Set an icon cache entry."""
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
        return entry.data

    def set_search(self, key: str, data: Any) -> None:
        """Set a search cache entry."""
        self._search_cache[key] = CacheEntry(
            data=data, timestamp=time.time(), key=key
        )

    # --- Selection Cache ---

    def get_selection(self, search_id: str) -> SelectionData | None:
        """Get selection data for a search ID."""
        return self._selection_cache.get(search_id)

    def set_selection(self, search_id: str, data: SelectionData) -> None:
        """Set selection data for a search ID."""
        self._selection_cache[search_id] = data

    def delete_selection(self, search_id: str) -> None:
        """Delete selection data."""
        self._selection_cache.pop(search_id, None)

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
            },
            "search_cache": {
                "valid": search_valid,
                "expired": search_expired,
                "total": len(self._search_cache),
            },
            "selection_cache": {
                "total": len(self._selection_cache),
            },
            "cache_expiry_minutes": int(self.expiry_seconds / 60),
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
