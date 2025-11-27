from __future__ import annotations

import asyncio
from functools import cache
from typing import TYPE_CHECKING, Any

from fastmcp import Context  # noqa: TC002
from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from fastmcp import FastMCP


@cache
def _get_info() -> dict[str, Any]:
    """Get version information for all dependencies.

    Returns:
        dict[str, Any]: Mapping of package names to version strings.
            See InfoResult TypedDict for structure.
    """
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
    async def info(ctx: Context) -> dict[str, Any]:
        """
        Display version information about the MCP instance.

        Can be compared with local output of "conda info" to see if they match.

        Returns:
            dict[str, Any]: Version information for MCP instance and dependencies.
                See InfoResult TypedDict for structure.
        """
        await ctx.info("Info got called")
        try:
            return await asyncio.to_thread(_get_info)
        except ImportError as ie:
            raise ToolError(f"[import_error] Failed to load dependencies: {ie}") from ie
        except Exception as e:
            raise ToolError(f"[unknown_error] 'info' failed: {e}") from e
