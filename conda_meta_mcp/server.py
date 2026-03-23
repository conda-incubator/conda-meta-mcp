from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import sys
from typing import TYPE_CHECKING

from fastmcp import FastMCP

if TYPE_CHECKING:
    import argparse

SERVICE_NAME = "Conda ECO System Meta Data MCP"

_periodic_cleanup_task: asyncio.Task | None = None


def _build_code_mode_transform():
    code_mode = importlib.import_module("fastmcp.experimental.transforms.code_mode")

    sandbox = code_mode.MontySandboxProvider(
        limits={"max_duration_secs": 30, "max_memory": 2_000_000_000}
    )
    return code_mode.CodeMode(
        discovery_tools=[code_mode.ListTools(), code_mode.GetSchemas()],
        sandbox_provider=sandbox,
    )


def setup_run(subparser: argparse._SubParsersAction):
    run_parser = subparser.add_parser("run", help="Run server")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    run_parser.add_argument("-c", "--code", action="store_true", help="Code Mode")
    run_parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http"],
        help="Server transport (default: stdio)",
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for non-stdio transports (e.g. streamable-http)",
    )
    run_parser.set_defaults(func=run_cmd)


def run_cmd(args):
    log_level = "DEBUG" if args.verbose else "INFO"
    os.environ["FASTMCP_LOG_LEVEL"] = log_level
    mcp = setup_server(args.code)

    run_kwargs = {"transport": args.transport, "show_banner": False}
    if args.port is not None:
        run_kwargs["port"] = args.port

    mcp.run(**run_kwargs)


def setup_server(code=False) -> FastMCP:
    from conda_meta_mcp.tools import discover_tools
    from conda_meta_mcp.tools.cache_utils import clear_external_library_caches

    global _periodic_cleanup_task

    transforms = [_build_code_mode_transform()] if code else None

    instance = FastMCP(name=SERVICE_NAME, transforms=transforms)

    for tool_fn in discover_tools():
        default_name = getattr(tool_fn, "__name__", "unknown")
        tool_name = getattr(tool_fn, "__mcp_tool_name__", default_name)
        instance.tool(tool_fn, name=tool_name)

    async def periodic_cleanup():
        """Periodically clear external library caches to prevent memory growth."""
        while True:
            await asyncio.sleep(1800)  # 30 minutes
            clear_external_library_caches()

    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop()
        _periodic_cleanup_task = asyncio.create_task(periodic_cleanup())

    return instance


# Enable usage of fastmcp cli
if "fastmcp" in sys.argv[0]:  # pragma: no cover
    mcp = setup_server()
