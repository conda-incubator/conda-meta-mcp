"""Minimal external cache clearing registry and on-demand MCP tool."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from fastmcp import FastMCP

T = TypeVar("T")

ExternalCacheClearer = Callable[[], None]
_external_cache_clearers: list[ExternalCacheClearer] = []


def register_external_cache_clearer(clearer: ExternalCacheClearer) -> None:
    """Register a callback that clears external or tool-level caches."""
    _external_cache_clearers.append(clearer)


def clear_external_library_caches() -> None:
    """Call all registered cache clearers (best-effort; ignore their errors)."""
    for clearer in list(_external_cache_clearers):
        with suppress(Exception):
            clearer()


def register_cache_maintenance(mcp: FastMCP) -> None:
    """Register an MCP tool to trigger cache maintenance on demand."""

    @mcp.tool
    async def cache_maintenance() -> str:
        """
        Run cache maintenance for all registered external and tool-level caches.

        Returns a short status message after cleanup has been triggered.
        """
        clear_external_library_caches()
        return "External and tool-level caches cleared."
