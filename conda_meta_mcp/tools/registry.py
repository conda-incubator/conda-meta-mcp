from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

AVAILABLE_TOOLS: list[Callable[..., Any]] = []


def register_tool(
    fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    cache_clearers: list[Callable[[], None]] | None = None,
) -> Callable[..., Any]:
    """
    Register a decorated function as an MCP tool.

    Usage:
        @register_tool
        async def my_tool(...):
            ...

        @register_tool(name="custom.name")
        async def my_tool(...):
            ...

        @register_tool(cache_clearers=[my_cache.cache_clear])
        async def my_tool(...):
            ...

    The decorator adds the function to AVAILABLE_TOOLS and sets
    __mcp_tool_name__ attribute for optional custom naming.

    Args:
        fn: The function to register (when used without parentheses)
        name: Optional custom name for the tool (defaults to function name)
        cache_clearers: Optional list of cache clearer functions to register

    Returns:
        The decorated function (unchanged, but registered)
    """
    from .cache_utils import register_external_cache_clearer

    def _decorate(f: Callable[..., Any]) -> Callable[..., Any]:
        f.__mcp_tool_name__ = name or f.__name__  # type: ignore[attr-defined]
        AVAILABLE_TOOLS.append(f)

        if cache_clearers:
            for clearer in cache_clearers:
                register_external_cache_clearer(clearer)

        return f

    if fn is None:
        # Called with arguments: @register_tool(name="...", cache_clearers=[...])
        return _decorate

    # Called without arguments: @register_tool
    return _decorate(fn)
