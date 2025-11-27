"""
import_mapping tool

This tool is based on (and wraps) logic from:
`conda_forge_metadata.autotick_bot.import_to_pkg`
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from fastmcp import FastMCP


from conda_forge_metadata.autotick_bot.import_to_pkg import (
    get_pkgs_for_import,
    map_import_to_package,
)

from .cache_utils import register_external_cache_clearer


@lru_cache(maxsize=1024)
def _map_import(import_name: str, get_keys: str = "") -> dict[str, Any]:
    """Map import name to package.

    Returns dict with structure matching ImportMappingResult TypedDict.
    """
    if not import_name or not import_name.strip():
        raise ValueError("import_name must be a non-empty string")

    query = import_name.strip()

    # Underlying function truncates to top-level automatically.
    candidates, normalized = get_pkgs_for_import(query)

    if candidates is None or len(candidates) == 0:
        # No mapping known; identity fallback.
        result = {
            "query_import": query,
            "normalized_import": normalized,
            "best_package": normalized,
            "candidate_packages": [],
            "heuristic": "identity",
        }
    else:
        best = map_import_to_package(query)

        if best == normalized and best in candidates:
            heuristic = "identity_present"
        elif best in candidates:
            heuristic = "ranked_selection"
        else:
            heuristic = "fallback"

        result = {
            "query_import": query,
            "normalized_import": normalized,
            "best_package": best,
            "candidate_packages": sorted(candidates),
            "heuristic": heuristic,
        }

    # Apply field filtering if get_keys is specified
    if get_keys and get_keys.strip():
        keys = set(k.strip() for k in get_keys.split(",") if k.strip())
        result = {k: v for k, v in result.items() if k in keys}

    return result


def register_import_mapping(mcp: FastMCP) -> None:
    register_external_cache_clearer(_map_import.cache_clear)

    @mcp.tool
    async def import_mapping(import_name: str, get_keys: str = "") -> dict[str, Any]:
        """
        Map a (possibly dotted) Python import name to the most likely conda package
        and expose supporting context.

        What this does:
          - Normalizes the import to its top-level module (e.g. "numpy.linalg" -> "numpy")
          - Retrieves an approximate candidate set of conda packages that may provide it
          - Applies a heuristic to pick a single "best" package
          - Returns a structured result with the decision rationale

        Heuristic labels:
          - identity:          No candidates known; fallback to normalized import
          - identity_present:  Candidates exist AND the normalized import name is among them
          - ranked_selection:  Best package chosen via ranked hubs authorities ordering
          - fallback:          Best package not in candidates (unexpected edge case)

        Returns:
          dict with structure matching ImportMappingResult TypedDict:
            - query_import: original query string supplied by caller
            - normalized_import: top-level portion used for lookup
            - best_package: chosen conda package name (may equal normalized_import)
            - candidate_packages: sorted list of possible supplying packages (may be empty)
            - heuristic: one of the heuristic labels above

        Args:
          import_name:
            Import string, e.g. "yaml", "matplotlib.pyplot", "sklearn.model_selection".
          get_keys:
            Comma-separated field names to include in results.
            Empty string returns all fields (default).
            Example: "best_package,heuristic" returns only key fields.
        """
        try:
            return await asyncio.to_thread(_map_import, import_name, get_keys)
        except ValueError as ve:
            raise ToolError(f"'import_mapping' invalid input: {ve}") from ve
        except Exception as e:  # pragma: no cover - generic protection
            raise ToolError(f"'import_mapping' failed: {e}") from e
