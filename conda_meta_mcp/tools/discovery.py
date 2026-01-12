from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from .registry import AVAILABLE_TOOLS


def discover_tools() -> list[Callable[..., Any]]:
    """
    Automatically import all tools so that @register_tool decorators run
    and populate AVAILABLE_TOOLS.

    Returns:
        A list of all registered MCP tool functions.
    """
    pkg_name = "conda_meta_mcp.tools"
    pkg = importlib.import_module(pkg_name)

    for mod_info in pkgutil.walk_packages(pkg.__path__, pkg_name + "."):
        # Skip private modules and this discovery module itself
        mod_basename = mod_info.name.rsplit(".", 1)[-1]
        if mod_basename.startswith("_"):
            continue
        if mod_basename in ("registry", "discovery"):
            continue

        importlib.import_module(mod_info.name)

    return sorted(AVAILABLE_TOOLS, key=lambda fn: getattr(fn, "__mcp_tool_name__", fn.__name__))
