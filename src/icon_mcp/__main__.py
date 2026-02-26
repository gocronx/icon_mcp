"""Allow `python -m icon_mcp` — delegates to run.main()."""

from __future__ import annotations

import os
import sys

# When invoked via `python -m icon_mcp` the src dir is already on sys.path,
# but when invoked other ways it may not be.
_src = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
if os.path.abspath(_src) not in (os.path.abspath(p) for p in sys.path):
    sys.path.insert(0, os.path.abspath(_src))

# Reuse the same entry point as run.py
# (import from package to avoid circular issues)
from icon_mcp.config import ServerConfig
from icon_mcp.server import MCPIconServer

import argparse
import asyncio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MCP Icon Server - Search and fetch icons from iconfont.cn"
    )
    parser.add_argument("--port", type=int, default=None, help="Web server port")
    parser.add_argument("--auto-open", action="store_true", default=None)
    parser.add_argument("--auto-start-web", action="store_true", default=None)
    parser.add_argument("--language", choices=["en", "zh-CN"], default=None)

    args = parser.parse_args()

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
