"""
import_mapping tool

This tool is based on (and wraps) logic from:
`conda_forge_metadata.autotick_bot.import_to_pkg`
"""

from __future__ import annotations

import asyncio
import sys
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from collections.abc import Callable

from conda_forge_metadata.autotick_bot.import_to_pkg import (
    get_pkgs_for_import,
    map_import_to_package,
)

# Temporary windows runtime patch: normalize path separators from Windows (\\) to slash (/)
# so URLs constructed by the upstream module won't include backslashes. This is a
# temporary workaround until the upstream `conda-forge-metadata` package includes
# a fix that uses posix-style paths for URL building.
if sys.platform.startswith("win"):
    try:
        import conda_forge_metadata.autotick_bot.import_to_pkg as _import_to_pkg_mod

        _orig_get_bot_sharded_path = getattr(_import_to_pkg_mod, "_get_bot_sharded_path", None)
        if _orig_get_bot_sharded_path is not None:
            orig: Callable[[str, int], str] = _orig_get_bot_sharded_path

            def _patched_get_bot_sharded_path(file_path: str, n_dirs: int = 5) -> str:
                p = orig(file_path, n_dirs)
                # Convert any Windows backslash separators to forward slashes for URL safety.
                if "\\" in p:
                    p = p.replace("\\", "/")
                return p

            _import_to_pkg_mod._get_bot_sharded_path = _patched_get_bot_sharded_path
    except Exception:  # noqa: S110
        # Silently ignore patching failures (e.g., if module isn't available in some envs).
        pass

from .registry import register_tool


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


@register_tool(cache_clearers=[_map_import.cache_clear])
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
