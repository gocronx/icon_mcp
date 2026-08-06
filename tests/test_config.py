"""Tests for ServerConfig."""

from __future__ import annotations

import os

from icon_mcp.config import ServerConfig


class TestServerConfig:
    def test_defaults(self):
        config = ServerConfig()
        assert config.web_server_port == 3000
        assert config.language == "en"
        assert config.cache_expiry_ms == 1800000
        assert config.cache_max_icon_entries == 500
        assert config.cache_max_search_entries == 200
        assert config.auto_start_web_server is False
        assert config.web_server_auto_open is False

    def test_cache_expiry_seconds(self):
        config = ServerConfig()
        assert config.cache_expiry_seconds == 1800.0

    def test_cache_expiry_minutes(self):
        config = ServerConfig()
        assert config.cache_expiry_minutes == 30

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("WEB_SERVER_PORT", "9999")
        monkeypatch.setenv("LANGUAGE", "zh-CN")
        monkeypatch.setenv("ICON_CACHE_MAX_ICONS", "100")
        config = ServerConfig()
        assert config.web_server_port == 9999
        assert config.language == "zh-CN"
        assert config.cache_max_icon_entries == 100
