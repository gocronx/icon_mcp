"""MCP Icon Server entry point.

Usage:
    uv run python run.py
    uv run python run.py --port 8080 --language zh-CN
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure the src directory is on the path so icon_mcp can be imported
# when running this file directly (without pip install).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from icon_mcp.config import ServerConfig
from icon_mcp.server import MCPIconServer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MCP Icon Server - Search and fetch icons from iconfont.cn"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Web server port (default: 3000, overrides WEB_SERVER_PORT env)",
    )
    parser.add_argument(
        "--auto-open",
        action="store_true",
        default=None,
        help="Auto-open browser when starting web server",
    )
    parser.add_argument(
        "--auto-start-web",
        action="store_true",
        default=None,
        help="Auto-start the web server on startup",
    )
    parser.add_argument(
        "--language",
        choices=["en", "zh-CN"],
        default=None,
        help="UI language (default: en, overrides LANGUAGE env)",
    )

    args = parser.parse_args()

    # Build config (CLI args override env vars)
    config = ServerConfig()
    if args.port is not None:
        config.web_server_port = args.port
    if args.auto_open is not None:
        config.web_server_auto_open = args.auto_open
    if args.auto_start_web is not None:
        config.auto_start_web_server = args.auto_start_web
    if args.language is not None:
        config.language = args.language
        os.environ["LANGUAGE"] = args.language

    # Create and run server
    server = MCPIconServer(config)
    try:
        asyncio.run(server.run())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
