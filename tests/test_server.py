"""Integration tests for the MCP server using the SDK Client (in-process)."""

from __future__ import annotations

import json

import pytest
from mcp import Client

from icon_mcp.server import mcp, set_server_config
from icon_mcp.config import ServerConfig


@pytest.fixture(autouse=True)
def setup_config():
    """Set up server config before tests."""
    set_server_config(ServerConfig())


class TestServerIntegration:
    """Test the MCP server tools via the in-process Client."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Server should expose all 7 tools."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = [t.name for t in tools.tools]
            assert "search_icons" in names
            assert "start_web_server" in names
            assert "stop_web_server" in names
            assert "check_selection_status" in names
            assert "get_cache_stats" in names
            assert "clear_cache" in names
            assert "save_icons" in names
            assert len(names) == 7

    @pytest.mark.asyncio
    async def test_tool_annotations(self):
        """Tools should have proper annotations."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_map = {t.name: t for t in tools.tools}

            # search_icons should be read-only
            search = tool_map["search_icons"]
            assert search.annotations.read_only_hint is True

            # clear_cache should be destructive
            clear = tool_map["clear_cache"]
            assert clear.annotations.destructive_hint is True

            # stop_web_server should be destructive and idempotent
            stop = tool_map["stop_web_server"]
            assert stop.annotations.destructive_hint is True
            assert stop.annotations.idempotent_hint is True

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """get_cache_stats should return structured stats."""
        async with Client(mcp) as client:
            result = await client.call_tool("get_cache_stats", {})
            # Result is TextContent with JSON
            assert len(result.content) == 1
            data = json.loads(result.content[0].text)
            assert "icon_cache" in data
            assert "search_cache" in data
            assert "cache_expiry_minutes" in data
            assert data["icon_cache"]["max_entries"] == 500

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """clear_cache should return cleared counts."""
        async with Client(mcp) as client:
            result = await client.call_tool("clear_cache", {"expiredOnly": False})
            data = json.loads(result.content[0].text)
            assert "icon_cleared" in data
            assert "message" in data

    @pytest.mark.asyncio
    async def test_clear_cache_expired_only(self):
        """clear_cache with expiredOnly=True should work."""
        async with Client(mcp) as client:
            result = await client.call_tool("clear_cache", {"expiredOnly": True})
            data = json.loads(result.content[0].text)
            assert "icon_cleared" in data

    @pytest.mark.asyncio
    async def test_start_and_stop_web_server(self):
        """start_web_server and stop_web_server should work."""
        async with Client(mcp) as client:
            # Start
            result = await client.call_tool(
                "start_web_server", {"port": 19876, "autoOpen": False}
            )
            data = json.loads(result.content[0].text)
            assert data["port"] == 19876
            assert "url" in data

            # Stop
            result = await client.call_tool("stop_web_server", {})
            data = json.loads(result.content[0].text)
            assert "message" in data

    @pytest.mark.asyncio
    async def test_check_selection_invalid_search_id(self):
        """check_selection_status with invalid ID should return error."""
        async with Client(mcp, raise_exceptions=False) as client:
            result = await client.call_tool(
                "check_selection_status", {"searchId": "nonexistent_id"}
            )
            # Should get an error since the search ID doesn't exist
            assert result.is_error is True

    @pytest.mark.asyncio
    async def test_save_icons_empty(self):
        """save_icons with empty list should error."""
        async with Client(mcp, raise_exceptions=False) as client:
            result = await client.call_tool(
                "save_icons", {"icons": [], "savePath": "/tmp/test-icons"}
            )
            assert result.is_error is True

    @pytest.mark.asyncio
    async def test_save_icons_success(self):
        """save_icons should create files."""
        import tempfile
        import os

        icons = [
            {"name": "test-arrow", "svg": "<svg><path d='M0 0'/></svg>"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "save_icons", {"icons": icons, "savePath": tmpdir}
                )
                data = json.loads(result.content[0].text)
                assert "test-arrow.svg" in data["saved"]
                assert os.path.exists(os.path.join(tmpdir, "test-arrow.svg"))

    @pytest.mark.asyncio
    async def test_server_info(self):
        """Server should identify itself."""
        async with Client(mcp) as client:
            # The server name is "icon-mcp-server"
            assert client.server_info is not None
            assert client.server_info.name == "icon-mcp-server"
