"""Tests for Pydantic data models."""

from __future__ import annotations

from icon_mcp.models import (
    CacheEntry,
    IconData,
    SearchResult,
    SelectedIcon,
    SelectionData,
    SelectionStatus,
)


class TestModels:
    def test_icon_data_minimal(self):
        icon = IconData(id=123)
        assert icon.id == 123
        assert icon.name == ""

    def test_icon_data_extra_fields(self):
        icon = IconData(id=1, name="test", unknown_field="ok")
        assert icon.id == 1
        # extra="allow" should keep it
        assert icon.unknown_field == "ok"  # type: ignore[attr-defined]

    def test_search_result(self):
        result = SearchResult(search_id="s1", query="home")
        assert result.icons == []
        assert result.count == 0

    def test_selection_status_values(self):
        assert SelectionStatus.WAITING == "waiting"
        assert SelectionStatus.COMPLETED == "completed"
        assert SelectionStatus.FAILED == "failed"
        assert SelectionStatus.TIMEOUT == "timeout"

    def test_selection_data_defaults(self):
        data = SelectionData()
        assert data.status == SelectionStatus.WAITING
        assert data.selected_icons == []
        assert data.connected is False

    def test_cache_entry(self):
        entry = CacheEntry(data={"icons": [1, 2]}, timestamp=100.0, key="k")
        assert entry.data == {"icons": [1, 2]}
        assert entry.key == "k"

    def test_selected_icon(self):
        icon = SelectedIcon(name="arrow", id=42, svg="<svg/>")
        assert icon.file_name == ""
