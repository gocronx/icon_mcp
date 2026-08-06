"""Allow running as: python -m icon_mcp / icon-mcp CLI."""

from icon_mcp.server import mcp, set_server_config
from icon_mcp.config import ServerConfig


def main() -> None:
    """Entry point for `icon-mcp` CLI command."""
    set_server_config(ServerConfig())
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
