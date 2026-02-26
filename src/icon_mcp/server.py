"""MCP Server core - registers tools and handles MCP protocol."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
    CallToolResult,
)

from .config import ServerConfig
from .lang import t, init_from_env
from .models import SelectionStatus
from .utils.cache import CacheManager
from .utils.search import IconSearcher
from .utils.saver import IconSaver
from .utils.web_server import WebServer
from .web.interface import WebInterface


class MCPIconServer:
    """Main MCP Icon Server - orchestrates all components."""

    def __init__(self, config: ServerConfig | None = None):
        self.config = config or ServerConfig()

        # Initialize language
        init_from_env()

        # Initialize components
        self.cache = CacheManager(expiry_seconds=self.config.cache_expiry_seconds)
        self.searcher = IconSearcher(self.config, self.cache)
        self.saver = IconSaver(self.cache)
        self.web_server = WebServer(
            cache=self.cache,
            port=self.config.web_server_port,
            auto_open=self.config.web_server_auto_open,
        )
        self.web_interface = WebInterface(port=self.config.web_server_port)
        self.web_server.set_html_generator(self.web_interface)

        # MCP server instance
        self.mcp = Server("icon-mcp-server")
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all MCP tool handlers."""

        @self.mcp.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="search_icons",
                    description=t("search.searchDescription"),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "q": {
                                "type": "string",
                                "description": "Search keyword for icons",
                            },
                            "sortType": {
                                "type": "string",
                                "description": "Sort type: recommend (default), updated_at",
                                "default": "recommend",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number (default: 1)",
                                "default": 1,
                                "minimum": 1,
                            },
                            "pageSize": {
                                "type": "integer",
                                "description": "Number of results per page (1-100, default: 100)",
                                "default": 100,
                                "minimum": 1,
                                "maximum": 100,
                            },
                        },
                        "required": ["q"],
                    },
                ),
                Tool(
                    name="start_web_server",
                    description=t("web.startServer"),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "port": {
                                "type": "integer",
                                "description": "Server port (default: 3000)",
                            },
                            "autoOpen": {
                                "type": "boolean",
                                "description": "Auto-open browser (default: true)",
                                "default": True,
                            },
                        },
                    },
                ),
                Tool(
                    name="stop_web_server",
                    description=t("web.stopServer"),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="check_selection_status",
                    description=t("web.checkSelection"),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "searchId": {
                                "type": "string",
                                "description": "Search ID to check selection for",
                            },
                            "maxWaitTime": {
                                "type": "integer",
                                "description": "Max wait time in ms (default: 180000)",
                                "default": 180000,
                            },
                        },
                        "required": ["searchId"],
                    },
                ),
                Tool(
                    name="get_cache_stats",
                    description=t("cache.statsDescription"),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="clear_cache",
                    description=t("cache.clearDescription"),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "expiredOnly": {
                                "type": "boolean",
                                "description": "Only clear expired entries (default: false)",
                                "default": False,
                            },
                        },
                    },
                ),
                Tool(
                    name="save_icons",
                    description="Save selected icons to local filesystem as SVG files",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "icons": {
                                "type": "array",
                                "description": "Array of icon objects to save",
                                "items": {"type": "object"},
                            },
                            "savePath": {
                                "type": "string",
                                "description": "Path to save icons (default: ./saved-icons)",
                                "default": "./saved-icons",
                            },
                        },
                        "required": ["icons"],
                    },
                ),
            ]

        @self.mcp.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            try:
                result = await self._dispatch_tool(name, arguments)
                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
            except Exception as e:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": str(e)}, ensure_ascii=False),
                    )
                ]

    async def _dispatch_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call to the appropriate handler."""
        if name == "search_icons":
            result = await self.searcher.search_icons(
                q=args.get("q", ""),
                sort_type=args.get("sortType", "recommend"),
                page=args.get("page", 1),
                page_size=args.get("pageSize", 100),
            )
            # Auto-start web server if not running
            if not self.web_server.is_running():
                await self.web_server.start(auto_open=False)
                self.web_interface.port = self.web_server.port
                print(f"  Web server auto-started: {self.web_server.get_url()}", file=sys.stderr)

            # Add web URL to result
            search_id = result["search_id"]
            result["web_url"] = f"{self.web_server.get_url()}?searchId={search_id}"
            result["waiting_message"] = t("search.pleaseWaitForSelection")
            return result

        elif name == "start_web_server":
            result = await self.web_server.start(
                port=args.get("port"),
                auto_open=args.get("autoOpen", True),
            )
            self.web_interface.port = self.web_server.port
            return result

        elif name == "stop_web_server":
            return await self.web_server.stop()

        elif name == "check_selection_status":
            return await self._check_selection(
                search_id=args["searchId"],
                max_wait_ms=args.get("maxWaitTime", 180000),
            )

        elif name == "get_cache_stats":
            return self.cache.get_stats()

        elif name == "clear_cache":
            expired_only = args.get("expiredOnly", False)
            result = self.cache.clear(expired_only=expired_only)
            result["message"] = (
                t("cache.expiredCleared") if expired_only else t("cache.cleared")
            )
            return result

        elif name == "save_icons":
            return await self.saver.save_icons(
                icons=args.get("icons", []),
                save_path=args.get("savePath", "./saved-icons"),
            )

        else:
            raise ValueError(t("error.methodNotFound", {"method": name}))

    async def _check_selection(
        self, search_id: str, max_wait_ms: int = 180000
    ) -> dict[str, Any]:
        """Poll for user selection status with timeout."""
        # Validate search_id exists
        cached = self.cache.get_search(search_id)
        if cached is None:
            raise ValueError(t("selection.noSearchFound", {"searchId": search_id}))

        print(
            t("selection.checkingStatus", {"searchId": search_id}),
            file=sys.stderr,
        )

        max_wait_s = max_wait_ms / 1000.0
        start = time.time()
        check_interval = 0.1  # 100ms polling
        log_interval = 10.0
        last_log = start

        while time.time() - start < max_wait_s:
            selection = self.cache.get_selection(search_id)

            if selection is not None:
                if selection.status == SelectionStatus.COMPLETED:
                    # Clean up and return icons
                    icons = selection.selected_icons
                    self.cache.delete_selection(search_id)
                    return {
                        "success": True,
                        "status": "completed",
                        "selected_icons": icons,
                        "count": len(icons),
                    }
                elif selection.status == SelectionStatus.FAILED:
                    self.cache.delete_selection(search_id)
                    return {
                        "success": False,
                        "status": "failed",
                        "message": t("selection.selectionFailed"),
                    }

            # Periodic status log
            now = time.time()
            if now - last_log >= log_interval:
                elapsed = int(now - start)
                print(
                    t("selection.waitingForSelection") + f" ({elapsed}s)",
                    file=sys.stderr,
                )
                last_log = now

            await asyncio.sleep(check_interval)

        # Timeout
        elapsed = int(time.time() - start)
        return {
            "success": False,
            "status": "timeout",
            "message": t("selection.selectionTimeout", {"seconds": elapsed}),
        }

    async def _cleanup(self) -> None:
        """Clean up all resources."""
        await self.searcher.close()
        if self.web_server.is_running():
            await self.web_server.stop()

    async def run(self) -> None:
        """Run the MCP server on stdio."""
        print(t("server.starting"), file=sys.stderr)
        print(f"  MCP transport : stdio", file=sys.stderr)
        print(f"  Web server port: {self.config.web_server_port}", file=sys.stderr)
        print(f"  Language       : {self.config.language}", file=sys.stderr)
        print(f"  Auto start web : {self.config.auto_start_web_server}", file=sys.stderr)
        print(f"  Auto open browser: {self.config.web_server_auto_open}", file=sys.stderr)

        # Auto-start web server if configured
        if self.config.auto_start_web_server:
            await self.web_server.start(auto_open=self.config.web_server_auto_open)
            self.web_interface.port = self.web_server.port
            print(f"  Web server URL : {self.web_server.get_url()}", file=sys.stderr)

        print(t("server.started"), file=sys.stderr)

        # Register signal handlers on the running event loop.
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, lambda: asyncio.ensure_future(self._shutdown_and_exit())
            )

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.mcp.run(
                    read_stream,
                    write_stream,
                    self.mcp.create_initialization_options(),
                )
        except asyncio.CancelledError:
            pass
        finally:
            await self._cleanup()

    async def _shutdown_and_exit(self) -> None:
        """Clean up resources then terminate the process.

        The MCP SDK's stdio_server reads stdin in a blocking thread that
        cannot be interrupted by task cancellation or fd closing on macOS.
        After cleaning up, we reset the signal handler to default and
        re-raise SIGINT so the process is terminated normally by the OS.
        This allows the parent process (e.g. uv) to reap the child
        cleanly without ESRCH errors.
        """
        print(t("server.shutdown"), file=sys.stderr)
        await self._cleanup()
        # Reset to default handler and re-raise — the OS terminates
        # the process, and the parent can waitpid() without ESRCH.
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGINT)
