"""Cache maintenance MCP tool."""

from __future__ import annotations

from .cache_utils import clear_external_library_caches
from .registry import register_tool


@register_tool
async def cache_maintenance() -> str:
    """
    Run cache maintenance for all registered external and tool-level caches.

    Returns a short status message after cleanup has been triggered.
    """
    clear_external_library_caches()
    return "External and tool-level caches cleared."
