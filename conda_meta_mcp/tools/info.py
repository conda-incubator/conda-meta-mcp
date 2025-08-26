from __future__ import annotations

import asyncio
from functools import cache
from typing import TYPE_CHECKING

from fastmcp import Context  # noqa: TC002
from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from fastmcp import FastMCP


@cache
def _get_info():
    from conda import __version__ as conda_version
    from conda_package_streaming import __version__ as conda_package_streaming_version
    from fastmcp import __version__ as fastmcp_version
    from libmambapy import __version__ as libmambapy_version

    from .. import __version__

    return {
        "conda_version": conda_version,
        "libmambapy_version": libmambapy_version,
        "fastmcp_version": fastmcp_version,
        "conda_package_streaming_version": conda_package_streaming_version,
        "conda_meta_mcp_version": __version__,
    }


def register_info(mcp: FastMCP) -> None:
    @mcp.tool
    async def info(ctx: Context) -> dict:
        """
        Display information about the MCP instance.
        """
        await ctx.info("Info got called")
        try:
            return await asyncio.to_thread(_get_info)
        except Exception as e:
            raise ToolError(f"'info' failed with: {e}")
