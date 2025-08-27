from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from fastmcp import FastMCP

if TYPE_CHECKING:
    import argparse

SERVICE_NAME = "Conda ECO System Meta Data MCP"


def setup_run(subparser: argparse._SubParsersAction):
    run_parser = subparser.add_parser("run", help="Run server")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    run_parser.set_defaults(func=run_cmd)


def run_cmd(args):
    log_level = "DEBUG" if args.verbose else "INFO"
    mcp = setup_server(log_level=log_level)
    mcp.run(transport="stdio", show_banner=False)


def setup_server(log_level: str | None = None) -> FastMCP:
    from conda_meta_mcp.tools import TOOLS

    instance = FastMCP(name=SERVICE_NAME, log_level=log_level)

    for tool in TOOLS:
        tool(instance)

    return instance


# Enable usage of fastmcp cli
if "fastmcp" in sys.argv[0]:  # pragma: no cover
    mcp = setup_server()
