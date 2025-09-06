"""
pypi_to_conda tool

This tool is based on (and wraps) logic from:
`conda_forge_metadata.autotick_bot.pypi_to_conda`
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from fastmcp import FastMCP


from conda_forge_metadata.autotick_bot.pypi_to_conda import (
    map_pypi_to_conda,
)


@lru_cache(maxsize=4096)
def _map_pypi_name(pypi_name: str) -> dict:
    if not pypi_name or not pypi_name.strip():
        raise ValueError("pypi_name must be a non-empty string")

    original = pypi_name.strip()
    conda_name = map_pypi_to_conda(original)
    changed = conda_name != original.lower()
    return {
        "pypi_name": original,
        "conda_name": conda_name,
        "changed": changed,
    }


def register_pypi_to_conda(mcp: FastMCP) -> None:
    @mcp.tool
    async def pypi_to_conda(pypi_name: str) -> dict:
        """
        Map a (case-sensitive) PyPI distribution name to the most likely conda package name.

        Returns:
          {
            "pypi_name": original input (trimmed),
            "conda_name": mapped (lowercase) conda name (fallback: pypi_name.lower()),
            "changed": conda_name != pypi_name.lower()
          }

        'changed' is True only when the resolved conda name differs from simple lowercase.
        """
        try:
            return await asyncio.to_thread(_map_pypi_name, pypi_name)
        except ValueError as ve:
            raise ToolError(f"'pypi_to_conda' invalid input: {ve}") from ve
        except Exception as e:  # pragma: no cover
            raise ToolError(f"'pypi_to_conda' failed: {e}") from e
