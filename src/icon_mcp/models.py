"""Data models for MCP Icon Server."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IconData(BaseModel):
    """Represents a single icon from iconfont.cn."""

    id: int
    name: str = ""
    slug: str | None = None
    unicode: str | None = None
    font_class: str | None = None
    show_svg: str | None = None
    icon: str | None = None  # URL to icon image
    width: int | None = None
    height: int | None = None
    fills: int | None = None
    category: str | None = None
    user: dict[str, Any] | None = None

    class Config:
        extra = "allow"


class SearchResult(BaseModel):
    """Result from an icon search."""

    search_id: str
    query: str
    icons: list[IconData] = Field(default_factory=list)
    count: int = 0
    total_count: int = 0
    page: int = 1
    page_size: int = 100
    web_url: str | None = None


class CacheEntry(BaseModel):
    """A cached item with timestamp for TTL."""

    data: Any
    timestamp: float
    key: str = ""


class SelectionStatus(str, Enum):
    """Status of user icon selection."""

    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SelectionData(BaseModel):
    """User selection state tracked via WebSocket."""

    status: SelectionStatus = SelectionStatus.WAITING
    search_id: str = ""
    timestamp: float = 0
    connected: bool = False
    selected_icons: list[dict[str, Any]] = Field(default_factory=list)


class SelectedIcon(BaseModel):
    """An icon selected by the user with SVG content."""

    name: str
    id: int
    svg: str = ""
    file_name: str = ""
