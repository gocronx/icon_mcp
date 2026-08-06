"""Tests for CacheManager: LRU eviction, TTL, event-driven selection."""

from __future__ import annotations

import asyncio
import time

import pytest

from icon_mcp.models import SelectionData, SelectionStatus
from icon_mcp.utils.cache import CacheManager


# --- LRU eviction ---


class TestLRUEviction:
    def test_icon_cache_evicts_oldest(self):
        cache = CacheManager(max_icon_entries=3)
        cache.set_icon("a", 1)
        cache.set_icon("b", 2)
        cache.set_icon("c", 3)
        # Cache is full, inserting d should evict a (oldest)
        cache.set_icon("d", 4)
        assert cache.get_icon("a") is None
        assert cache.get_icon("b") == 2
        assert cache.get_icon("d") == 4

    def test_icon_cache_access_promotes(self):
        cache = CacheManager(max_icon_entries=3)
        cache.set_icon("a", 1)
        cache.set_icon("b", 2)
        cache.set_icon("c", 3)
        # Access 'a' promotes it; next eviction should remove 'b'
        cache.get_icon("a")
        cache.set_icon("d", 4)
        assert cache.get_icon("a") == 1  # still present
        assert cache.get_icon("b") is None  # evicted

    def test_search_cache_evicts_oldest(self):
        cache = CacheManager(max_search_entries=2)
        cache.set_search("s1", {"q": "x"})
        cache.set_search("s2", {"q": "y"})
        cache.set_search("s3", {"q": "z"})
        assert cache.get_search("s1") is None
        assert cache.get_search("s2") == {"q": "y"}
        assert cache.get_search("s3") == {"q": "z"}

    def test_update_existing_key_does_not_increase_size(self):
        cache = CacheManager(max_icon_entries=3)
        cache.set_icon("a", 1)
        cache.set_icon("b", 2)
        cache.set_icon("c", 3)
        # Update existing key — should not evict anything
        cache.set_icon("b", 20)
        assert cache.get_icon("a") == 1
        assert cache.get_icon("b") == 20
        assert cache.get_icon("c") == 3


# --- TTL ---


class TestTTL:
    def test_expired_icon_returns_none(self):
        cache = CacheManager(expiry_seconds=0.05)
        cache.set_icon("x", "data")
        time.sleep(0.06)
        assert cache.get_icon("x") is None

    def test_valid_icon_returns_data(self):
        cache = CacheManager(expiry_seconds=10)
        cache.set_icon("x", "data")
        assert cache.get_icon("x") == "data"

    def test_expired_search_returns_none(self):
        cache = CacheManager(expiry_seconds=0.05)
        cache.set_search("s", {"icons": []})
        time.sleep(0.06)
        assert cache.get_search("s") is None


# --- Selection + Event ---


class TestSelectionEvent:
    @pytest.mark.asyncio
    async def test_event_fires_on_completed(self):
        cache = CacheManager()
        cache.set_search("s1", {"icons": []})
        event = cache.get_selection_event("s1")

        async def fire():
            await asyncio.sleep(0.05)
            cache.set_selection(
                "s1",
                SelectionData(
                    status=SelectionStatus.COMPLETED,
                    search_id="s1",
                    selected_icons=[{"id": 1}],
                ),
            )

        asyncio.create_task(fire())
        await asyncio.wait_for(event.wait(), timeout=1.0)
        sel = cache.get_selection("s1")
        assert sel is not None
        assert sel.status == SelectionStatus.COMPLETED
        assert sel.selected_icons == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_event_fires_on_failed(self):
        cache = CacheManager()
        event = cache.get_selection_event("s2")

        cache.set_selection(
            "s2",
            SelectionData(status=SelectionStatus.FAILED, search_id="s2"),
        )
        # Event should already be set
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_timeout_when_no_event(self):
        cache = CacheManager()
        event = cache.get_selection_event("s3")
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(event.wait(), timeout=0.1)

    def test_delete_selection_cleans_event(self):
        cache = CacheManager()
        cache.set_selection(
            "s4",
            SelectionData(status=SelectionStatus.WAITING, search_id="s4"),
        )
        _ = cache.get_selection_event("s4")
        cache.delete_selection("s4")
        assert cache.get_selection("s4") is None
        # Event dict should also be cleaned
        assert "s4" not in cache._selection_events


# --- Stats & Clear ---


class TestStatsAndClear:
    def test_stats_report(self):
        cache = CacheManager(max_icon_entries=10, max_search_entries=5)
        cache.set_icon("i1", "data")
        cache.set_search("s1", {"q": "a"})
        stats = cache.get_stats()
        assert stats["icon_cache"]["total"] == 1
        assert stats["icon_cache"]["max_entries"] == 10
        assert stats["search_cache"]["total"] == 1
        assert stats["search_cache"]["max_entries"] == 5

    def test_clear_all(self):
        cache = CacheManager()
        cache.set_icon("a", 1)
        cache.set_icon("b", 2)
        cache.set_search("s", {})
        result = cache.clear()
        assert result["icon_cleared"] == 2
        assert result["search_cleared"] == 1
        assert cache.get_icon("a") is None

    def test_clear_expired_only(self):
        cache = CacheManager(expiry_seconds=0.05)
        cache.set_icon("old", 1)
        time.sleep(0.06)
        cache.set_icon("new", 2)  # re-create with fresh timestamp
        # Only old entry's TTL has passed; "new" was just set
        result = cache.clear(expired_only=True)
        assert result["icon_cleared"] == 1
        assert cache.get_icon("new") == 2
