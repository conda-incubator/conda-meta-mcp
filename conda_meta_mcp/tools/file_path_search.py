import asyncio
from functools import lru_cache

import requests
from fastmcp.exceptions import ToolError

from .registry import register_tool


@lru_cache(maxsize=1024)
def _file_path_search_raw(path):
    """
    Fetch raw artifacts list for a given path from the conda-forge-paths API.

    This function is cached by `path` only. It returns a dict with keys:
      - ok (bool): whether the external API call succeeded
      - artifacts (list[str]): list of artifact names when ok is True
      - error (str, optional): error message when ok is False
    """
    if not path or not path.strip():
        raise ValueError("path must be a non-empty string")

    query = path.strip()

    try:
        r = requests.get(
            "https://cforge.quansight.dev/path_to_artifacts/find_artifacts.json",
            params={"path": query},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("ok"):
            artifacts = [row[0] for row in data.get("rows", [])]
            return {"ok": True, "artifacts": artifacts}
        else:
            return {"ok": False, "artifacts": [], "error": data.get("error", "Unknown error")}
    except Exception as e:
        raise ToolError(f"Failed to search for path: {e}")


def _file_path_search(path, limit: int = 0, offset: int = 0):
    """
    Paginate results for the given path from the raw fetch function.

    Args:
        path (str): Path to search for
        limit (int): Maximum number of results to return (0 means all)
        offset (int): Number of results to skip before applying limit

    Returns:
        dict with:
            - query_path: the searched path
            - artifacts: paginated list of artifact names
            - count: number of artifacts in the returned page
            - total: total number of matching artifacts
            - limit: limit used in this query (int)
            - offset: offset used in this query (int)
            - error: optional error string if available
    """
    # Basic validation
    if not path or not path.strip():
        raise ValueError("path must be a non-empty string")

    try:
        limit = int(limit or 0)
        offset = int(offset or 0)
    except Exception:
        raise ValueError("limit and offset must be integers")

    if limit < 0 or offset < 0:
        raise ValueError("limit and offset must be non-negative integers")

    query = path.strip()
    raw = _file_path_search_raw(query)

    if not raw.get("ok"):
        # Propagate an empty but consistent response with error if the API reported a problem
        return {
            "query_path": query,
            "artifacts": [],
            "count": 0,
            "total": 0,
            "limit": limit if limit and limit > 0 else 0,
            "offset": max(offset, 0),
            "error": raw.get("error", "Unknown error"),
        }

    artifacts = raw["artifacts"]
    total = len(artifacts)
    offset = max(offset, 0)
    paginated = artifacts[offset : offset + limit] if limit and limit > 0 else artifacts[offset:]

    return {
        "query_path": query,
        "artifacts": paginated,
        "count": len(paginated),
        "total": total,
        "limit": limit if limit and limit > 0 else total,
        "offset": offset,
    }


@register_tool(cache_clearers=[_file_path_search_raw.cache_clear])
async def file_path_search(path, limit: int = 0, offset: int = 0):
    """
    Find conda artifacts that contain a given file path.

    Searches the conda-forge-paths database for packages that ship the specified path.

    Args:
        path: The file path to search for (e.g., "libcuda.so", "bin/conda")
        limit: Maximum number of results to return (0 means all)
        offset: Number of results to skip before applying limit

    Returns:
        dict with:
        - query_path: the searched path
        - artifacts: paginated list of artifact names
        - count: number of artifacts in the returned page
        - total: total number of matching artifacts
        - limit: limit used in this query
        - offset: offset used in this query
    """
    try:
        return await asyncio.to_thread(_file_path_search, path, limit, offset)
    except ValueError as ve:
        raise ToolError(f"'file_path_search' invalid input: {ve}") from ve
    except Exception as e:
        raise ToolError(f"'file_path_search' failed: {e}") from e
