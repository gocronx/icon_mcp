"""Configuration management for MCP Icon Server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    """Server configuration loaded from environment variables."""

    # Language
    language: str = field(default_factory=lambda: os.environ.get("LANGUAGE", "en"))

    # Web server
    web_server_port: int = field(
        default_factory=lambda: int(os.environ.get("WEB_SERVER_PORT", "3000"))
    )
    web_server_auto_open: bool = field(
        default_factory=lambda: os.environ.get("WEB_SERVER_AUTO_OPEN", "false").lower()
        == "true"
    )
    auto_start_web_server: bool = field(
        default_factory=lambda: os.environ.get("AUTO_START_WEB_SERVER", "false").lower()
        == "true"
    )

    # Cache
    cache_expiry_ms: int = field(
        default_factory=lambda: int(os.environ.get("ICON_CACHE_EXPIRY", "1800000"))
    )

    # Search
    search_timeout_s: int = field(
        default_factory=lambda: int(os.environ.get("ICON_SEARCH_TIMEOUT", "30"))
    )

    # API
    iconfont_api_base: str = "https://www.iconfont.cn/api/icon/search.json"

    @property
    def cache_expiry_seconds(self) -> float:
        return self.cache_expiry_ms / 1000.0

    @property
    def cache_expiry_minutes(self) -> int:
        return self.cache_expiry_ms // 60000
