"""MCP Server core - uses MCPServer (v2 high-level API) with lifespan."""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations

from .config import ServerConfig
from .lang import t, init_from_env
from .models import SelectionStatus
from .utils.cache import CacheManager
from .utils.search import IconSearcher
from .utils.saver import IconSaver
from .utils.web_server import WebServer
from .web.interface import WebInterface

__all__ = ["mcp", "set_server_config", "AppState"]


@dataclass
class AppState:
    """Shared application state created during lifespan."""

    config: ServerConfig
    cache: CacheManager
    searcher: IconSearcher
    saver: IconSaver
    web_server: WebServer
    web_interface: WebInterface


@asynccontextmanager
async def app_lifespan(server: MCPServer):
    """Application lifespan: initialize and clean up resources."""
    config = _get_config()
    init_from_env()

    # Initialize components
    cache = CacheManager(
        expiry_seconds=config.cache_expiry_seconds,
        max_icon_entries=config.cache_max_icon_entries,
        max_search_entries=config.cache_max_search_entries,
        cleanup_interval=config.cache_cleanup_interval_s,
    )
    searcher = IconSearcher(config, cache)
    saver = IconSaver(cache)
    web_server = WebServer(
        cache=cache,
        port=config.web_server_port,
        auto_open=config.web_server_auto_open,
    )
    web_interface = WebInterface(port=config.web_server_port)
    web_server.set_html_generator(web_interface)

    state = AppState(
        config=config,
        cache=cache,
        searcher=searcher,
        saver=saver,
        web_server=web_server,
        web_interface=web_interface,
    )

    # Start periodic cache cleanup
    cache.start_cleanup_task()

    # Log startup info
    print(t("server.starting"), file=sys.stderr)
    print(f"  MCP transport : stdio", file=sys.stderr)
    print(f"  Web server port: {config.web_server_port}", file=sys.stderr)
    print(f"  Language       : {config.language}", file=sys.stderr)
    print(f"  Auto start web : {config.auto_start_web_server}", file=sys.stderr)
    print(f"  Auto open browser: {config.web_server_auto_open}", file=sys.stderr)

    # Auto-start web server if configured
    if config.auto_start_web_server:
        await web_server.start(auto_open=config.web_server_auto_open)
        web_interface.port = web_server.port
        print(f"  Web server URL : {web_server.get_url()}", file=sys.stderr)

    print(t("server.started"), file=sys.stderr)

    try:
        yield state
    finally:
        # Cleanup
        cache.stop_cleanup_task()
        await searcher.close()
        if web_server.is_running():
            await web_server.stop()
        print(t("server.shutdown"), file=sys.stderr)


# --- Config singleton for lifespan ---

_server_config: ServerConfig | None = None


def set_server_config(config: ServerConfig) -> None:
    """Set the server config before creating the MCPServer."""
    global _server_config
    _server_config = config


def _get_config() -> ServerConfig:
    """Get the server config (set by run.py or defaults)."""
    return _server_config or ServerConfig()


# --- Create the MCPServer instance ---

mcp = MCPServer("icon-mcp-server", lifespan=app_lifespan)


# --- Helper to get state from context ---


def _state(ctx: Context) -> AppState:
    """Extract AppState from context's lifespan_context."""
    return ctx.request_context.lifespan_context


# --- Tool definitions ---
#
# NOTE: Tool parameters use camelCase (e.g. sortType, pageSize, searchId) intentionally.
# MCP tool schemas are exposed directly to AI models via JSON Schema; camelCase matches
# the iconfont.cn API conventions and common JSON naming, making the schema more natural
# for LLM consumption. The internal Python code receiving these values converts to
# snake_case when passing to business logic (e.g. sort_type, page_size).
#


@mcp.tool(
    name="search_icons",
    description="Search icons from iconfont.cn",
    annotations=ToolAnnotations(read_only_hint=True),
)
async def search_icons(
    ctx: Context,
    q: str,
    sortType: str = "recommend",
    page: int = 1,
    pageSize: int = 100,
) -> dict[str, Any]:
    """Search icons from iconfont.cn.

    Args:
        q: Search keyword for icons
        sortType: Sort type - recommend (default) or updated_at
        page: Page number (default: 1)
        pageSize: Number of results per page (1-100, default: 100)
    """
    state = _state(ctx)

    result = await state.searcher.search_icons(
        q=q,
        sort_type=sortType,
        page=page,
        page_size=pageSize,
    )

    # Auto-start web server if not running
    if not state.web_server.is_running():
        await state.web_server.start(auto_open=False)
        state.web_interface.port = state.web_server.port
        print(
            f"  Web server auto-started: {state.web_server.get_url()}",
            file=sys.stderr,
        )

    # Add web URL to result
    search_id = result["search_id"]
    result["web_url"] = f"{state.web_server.get_url()}?searchId={search_id}"
    result["waiting_message"] = t("search.pleaseWaitForSelection")
    return result


@mcp.tool(
    name="start_web_server",
    description="Start web server for icon selection",
    annotations=ToolAnnotations(read_only_hint=False, idempotent_hint=True),
)
async def start_web_server(
    ctx: Context,
    port: int | None = None,
    autoOpen: bool = True,
) -> dict[str, Any]:
    """Start the web icon selection interface.

    Args:
        port: Server port (default: 3000)
        autoOpen: Auto-open browser (default: true)
    """
    state = _state(ctx)
    result = await state.web_server.start(port=port, auto_open=autoOpen)
    state.web_interface.port = state.web_server.port
    return result


@mcp.tool(
    name="stop_web_server",
    description="Stop web server",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True),
)
async def stop_web_server(ctx: Context) -> dict[str, str]:
    """Stop the web icon selection server."""
    state = _state(ctx)
    return await state.web_server.stop()


@mcp.tool(
    name="check_selection_status",
    description="Check user selection status",
    annotations=ToolAnnotations(read_only_hint=True),
)
async def check_selection_status(
    ctx: Context,
    searchId: str,
    maxWaitTime: int = 180000,
) -> dict[str, Any]:
    """Wait for user to select icons in the web UI.

    Args:
        searchId: Search ID to check selection for
        maxWaitTime: Max wait time in ms (default: 180000)
    """
    state = _state(ctx)

    # Validate search_id exists
    cached = state.cache.get_search(searchId)
    if cached is None:
        raise ValueError(t("selection.noSearchFound", {"searchId": searchId}))

    print(
        t("selection.checkingStatus", {"searchId": searchId}),
        file=sys.stderr,
    )

    max_wait_s = maxWaitTime / 1000.0
    event = state.cache.get_selection_event(searchId)

    # Check if a terminal state was already set before we started waiting
    selection = state.cache.get_selection(searchId)
    if selection is None or selection.status == SelectionStatus.WAITING:
        # Block until the event fires or timeout — zero CPU spin
        try:
            await asyncio.wait_for(event.wait(), timeout=max_wait_s)
        except asyncio.TimeoutError:
            return {
                "success": False,
                "status": "timeout",
                "message": t(
                    "selection.selectionTimeout", {"seconds": int(max_wait_s)}
                ),
            }
        # Re-read after waking up
        selection = state.cache.get_selection(searchId)

    if selection is None:
        return {
            "success": False,
            "status": "timeout",
            "message": t("selection.selectionTimeout", {"seconds": int(max_wait_s)}),
        }

    if selection.status == SelectionStatus.COMPLETED:
        icons = selection.selected_icons
        state.cache.delete_selection(searchId)
        return {
            "success": True,
            "status": "completed",
            "selected_icons": icons,
            "count": len(icons),
        }
    elif selection.status == SelectionStatus.FAILED:
        state.cache.delete_selection(searchId)
        return {
            "success": False,
            "status": "failed",
            "message": t("selection.selectionFailed"),
        }
    else:
        return {
            "success": False,
            "status": "timeout",
            "message": t("selection.selectionTimeout", {"seconds": int(max_wait_s)}),
        }


@mcp.tool(
    name="get_cache_stats",
    description="Get icon cache statistics",
    annotations=ToolAnnotations(read_only_hint=True),
)
async def get_cache_stats(ctx: Context) -> dict[str, Any]:
    """Get cache statistics including valid/expired/total counts."""
    state = _state(ctx)
    return state.cache.get_stats()


@mcp.tool(
    name="clear_cache",
    description="Clear icon cache",
    annotations=ToolAnnotations(destructive_hint=True),
)
async def clear_cache(ctx: Context, expiredOnly: bool = False) -> dict[str, Any]:
    """Clear cache entries.

    Args:
        expiredOnly: Only clear expired entries (default: false)
    """
    state = _state(ctx)
    result = state.cache.clear(expired_only=expiredOnly)
    result["message"] = (
        t("cache.expiredCleared") if expiredOnly else t("cache.cleared")
    )
    return result


@mcp.tool(
    name="save_icons",
    description="Save selected icons to local filesystem as SVG files",
    annotations=ToolAnnotations(read_only_hint=False),
)
async def save_icons(
    ctx: Context,
    icons: list[dict[str, Any]],
    savePath: str = "./saved-icons",
) -> dict[str, Any]:
    """Save icon SVG data to local files.

    Args:
        icons: Array of icon objects to save (each with name and svg/show_svg)
        savePath: Path to save icons (default: ./saved-icons)
    """
    state = _state(ctx)
    return await state.saver.save_icons(icons=icons, save_path=savePath)
