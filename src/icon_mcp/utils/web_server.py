"""HTTP + WebSocket server for the icon selection web interface."""

from __future__ import annotations

import asyncio
import json
import platform
import random
import subprocess
import sys
import time
from typing import Any

import aiohttp
from aiohttp import web

from ..lang import t, get_current_language
from ..models import SelectionData, SelectionStatus
from .cache import CacheManager


class WebServer:
    """aiohttp-based HTTP + WebSocket server for the icon selection UI."""

    def __init__(
        self,
        cache: CacheManager,
        port: int = 3000,
        auto_open: bool = False,
    ):
        self.cache = cache
        self.port = port
        self.auto_open = auto_open
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._ws_clients: set[web.WebSocketResponse] = set()
        self._html_generator: Any = None  # Will be set externally

    def set_html_generator(self, generator: Any) -> None:
        """Set the HTML generator for serving the web UI."""
        self._html_generator = generator

    def is_running(self) -> bool:
        return self._site is not None

    def get_url(self) -> str:
        return f"http://localhost:{self.port}"

    def get_ws_url(self) -> str:
        return f"ws://localhost:{self.port}/ws"

    async def start(self, port: int | None = None, auto_open: bool | None = None) -> dict[str, Any]:
        """Start the HTTP server with WebSocket support."""
        if self.is_running():
            return {
                "message": t("server.webServerAlreadyRunning", {"port": self.port}),
                "port": self.port,
                "url": self.get_url(),
            }

        if port is not None:
            self.port = port
        if auto_open is not None:
            self.auto_open = auto_open

        # Find available port
        self.port = await self._find_available_port(self.port)

        # Create aiohttp app
        self._app = web.Application()
        self._app.router.add_get("/", self._handle_index)
        self._app.router.add_get("/site.js", self._handle_site_js)
        self._app.router.add_get("/api/cache", self._handle_cache_api)
        self._app.router.add_post("/api/search", self._handle_search_api)
        self._app.router.add_post("/api/save", self._handle_save_api)
        self._app.router.add_get("/ws", self._handle_websocket)
        self._app.router.add_route("OPTIONS", "/{path:.*}", self._handle_cors)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "localhost", self.port)
        await self._site.start()

        print(
            t("server.webServerStarted", {"port": self.port}),
            file=sys.stderr,
        )

        if self.auto_open:
            self._open_browser(self.get_url())

        return {
            "message": t("server.webServerStarted", {"port": self.port}),
            "port": self.port,
            "url": self.get_url(),
            "websocket": True,
        }

    async def stop(self) -> dict[str, str]:
        """Stop the HTTP server."""
        # Close all WebSocket connections
        for ws in list(self._ws_clients):
            await ws.close()
        self._ws_clients.clear()

        if self._runner:
            await self._runner.cleanup()
        self._app = None
        self._runner = None
        self._site = None

        print(t("server.webServerStopped"), file=sys.stderr)
        return {"message": t("server.webServerStopped")}

    # --- Route Handlers ---

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Serve the main HTML page."""
        if self._html_generator is None:
            return web.Response(text="Web interface not configured", status=500)

        search_id = request.query.get("searchId", "")
        html = self._html_generator.generate_html(search_id=search_id)
        return web.Response(text=html, content_type="text/html")

    async def _handle_site_js(self, request: web.Request) -> web.Response:
        """Serve client-side JavaScript."""
        if self._html_generator is None:
            return web.Response(text="", content_type="application/javascript")

        js = self._html_generator.generate_js()
        return web.Response(text=js, content_type="application/javascript")

    async def _handle_cache_api(self, request: web.Request) -> web.Response:
        """Handle cache API - return cached search results."""
        search_id = request.query.get("searchId", "")
        page = int(request.query.get("page", "1"))
        page_size = int(request.query.get("pageSize", "15"))

        cached = self.cache.get_search(search_id)
        if cached is None:
            return web.json_response({"error": "Search not found"}, status=404)

        icons = cached.get("icons", [])
        total_count = cached.get("total_count", len(icons))

        # Client-side pagination
        start = (page - 1) * page_size
        end = start + page_size
        page_icons = icons[start:end]

        return web.json_response(
            {
                "icons": page_icons,
                "count": len(page_icons),
                "totalCount": total_count,
                "page": page,
                "pageSize": page_size,
                "totalPages": max(1, (len(icons) + page_size - 1) // page_size),
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def _handle_search_api(self, request: web.Request) -> web.Response:
        """Handle search API - proxy to icon search."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # This endpoint is reserved for future use (direct search from web UI)
        return web.json_response(
            {"error": "Use MCP tools for searching"},
            status=501,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def _handle_save_api(self, request: web.Request) -> web.Response:
        """Handle save API - receive selected icons from web UI."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        icons = body.get("icons", [])
        search_id = body.get("searchId", "")

        if not icons or not search_id:
            return web.json_response(
                {"error": "Missing icons or searchId"}, status=400
            )

        # Mark selection as completed
        self.cache.set_selection(
            search_id,
            SelectionData(
                status=SelectionStatus.COMPLETED,
                search_id=search_id,
                timestamp=time.time(),
                connected=True,
                selected_icons=icons,
            ),
        )

        print(
            t("selection.userSelectedIcons", {"count": len(icons)}),
            file=sys.stderr,
        )

        return web.json_response(
            {"success": True, "count": len(icons)},
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for real-time communication."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        search_id = request.query.get("searchId", "")
        self._ws_clients.add(ws)

        # Initialize selection tracking
        if search_id:
            self.cache.set_selection(
                search_id,
                SelectionData(
                    status=SelectionStatus.WAITING,
                    search_id=search_id,
                    timestamp=time.time(),
                    connected=True,
                ),
            )

        # Send welcome message
        await ws.send_json({
            "type": "welcome",
            "searchId": search_id,
            "message": "Connected to MCP Icon Server",
        })

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get("type") == "ping":
                            await ws.send_json({"type": "pong"})
                    except json.JSONDecodeError:
                        pass
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        finally:
            self._ws_clients.discard(ws)
            # Mark selection as failed after disconnect
            if search_id:
                selection = self.cache.get_selection(search_id)
                if selection and selection.status == SelectionStatus.WAITING:
                    await asyncio.sleep(2)  # Grace period
                    selection = self.cache.get_selection(search_id)
                    if selection and selection.status == SelectionStatus.WAITING:
                        self.cache.set_selection(
                            search_id,
                            SelectionData(
                                status=SelectionStatus.FAILED,
                                search_id=search_id,
                                timestamp=time.time(),
                                connected=False,
                            ),
                        )

        return ws

    async def _handle_cors(self, request: web.Request) -> web.Response:
        """Handle CORS preflight requests."""
        return web.Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )

    # --- Utilities ---

    async def _find_available_port(self, start_port: int) -> int:
        """Find an available port starting from start_port."""
        port = start_port
        max_port = start_port + 100

        while port < max_port:
            try:
                server = await asyncio.start_server(
                    lambda r, w: None, "localhost", port
                )
                server.close()
                await server.wait_closed()
                return port
            except OSError:
                port += 1

        # Fallback to random port
        return random.randint(20000, 30000)

    @staticmethod
    def _open_browser(url: str) -> None:
        """Open URL in the default browser."""
        system = platform.system().lower()
        try:
            if system == "darwin":
                subprocess.Popen(["open", url])
            elif system == "windows":
                subprocess.Popen(["start", url], shell=True)
            else:
                subprocess.Popen(["xdg-open", url])
        except Exception as e:
            print(f"Failed to open browser: {e}", file=sys.stderr)
