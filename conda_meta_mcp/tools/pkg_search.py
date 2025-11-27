from __future__ import annotations

import asyncio
import contextlib
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from fastmcp import FastMCP


from conda.api import SubdirData
from conda.models.version import VersionOrder

from .cache_utils import register_external_cache_clearer


class PackageRecord(BaseModel):
    version: str
    build_number: str
    build: str
    url: str
    depends: str

    model_config = ConfigDict(frozen=True)

    def __hash__(self):
        return hash((self.version, self.build_number, self.build, self.url, self.depends))

    def _build_number_int(self):
        return int(self.build_number) if self.build_number.isdigit() else -1

    def _ordering_tuple(self):
        return (VersionOrder(self.version), self._build_number_int())

    def __lt__(self, other):
        return self._ordering_tuple() < other._ordering_tuple()


@lru_cache(maxsize=32)
def _full_package_search(package_ref_or_match_spec, channel, platform) -> list[PackageRecord]:
    return list(
        sorted(
            {
                PackageRecord(
                    version=str(match.version),
                    build_number=str(match.build_number),
                    build=str(match.build),
                    url=str(match.url),
                    depends=str(match.depends),
                )
                for match in SubdirData.query_all(
                    package_ref_or_match_spec,
                    channels=[f"{channel}/{platform}"],
                    subdirs=[platform],
                )
            },
            reverse=True,
        )
    )


def _clear_conda_subdirdata_cache_for_pkg_search() -> None:
    """
    Clear Conda's SubdirData global caches used by package_search.

    This cleans up large repodata JSON caches held in memory by Conda,
    in addition to our own lru_cache for _full_package_search.
    """
    with contextlib.suppress(Exception):
        from conda.core.subdir_data import SubdirData

        cache_attr = "_cache_"
        if hasattr(SubdirData, cache_attr):
            cache_obj = getattr(SubdirData, cache_attr, None)
            if hasattr(cache_obj, "clear") and callable(cache_obj.clear):
                cache_obj.clear()

        if hasattr(SubdirData, "clear_cached_local_channel_data"):
            SubdirData.clear_cached_local_channel_data()


def _filter_keys(results: list[PackageRecord], get_keys: str) -> list[dict]:
    """Filter PackageRecord results to specified keys only.

    Args:
        results: List of PackageRecord objects
        get_keys: Comma-separated field names to include (empty = all fields)

    Returns:
        List of dictionaries with only requested keys, or original records if get_keys is empty
    """
    if not get_keys or not get_keys.strip():
        # Return as dict to maintain serialization
        return [r.model_dump() for r in results]

    keys = set(k.strip() for k in get_keys.split(",") if k.strip())
    return [{k: v for k, v in r.model_dump().items() if k in keys} for r in results]


def _package_search(
    package_ref_or_match_spec, channel, platform, limit, offset, get_keys: str = ""
) -> dict[str, Any]:
    """Search for packages and return results with pagination metadata.

    Returns dict with structure matching PackageSearchResult TypedDict:
    {
        'results': list of package records (filtered by get_keys if specified),
        'total': total number of matching packages,
        'limit': limit used in this query,
        'offset': offset used in this query
    }
    """
    results = _full_package_search(package_ref_or_match_spec, channel, platform)
    offset = max(offset or 0, 0)
    paginated = results[offset : offset + limit] if limit and limit > 0 else results[offset:]

    # Apply field filtering if get_keys is specified
    filtered = _filter_keys(paginated, get_keys)

    return {
        "results": filtered,
        "total": len(results),
        "limit": limit if limit and limit > 0 else len(results),
        "offset": offset,
    }


def register_package_search(mcp: FastMCP) -> None:
    register_external_cache_clearer(_full_package_search.cache_clear)
    register_external_cache_clearer(_clear_conda_subdirdata_cache_for_pkg_search)

    @mcp.tool
    async def package_search(
        package_ref_or_match_spec: str,
        channel: str,
        platform: str,
        limit: int = 0,
        offset: int = 0,
        get_keys: str = "",
    ) -> dict[str, Any]:
        """
        Search available conda packages matching the given package_ref_or_match_spec, channel, and
        platform.

        Features:
          - Results are deduplicated.
          - Ordered by newest (version, then build_number descending).
          - limit=1 reliably returns the single newest record.
          - Supports paging via (offset, limit).
          - Optional field filtering via get_keys parameter.

        Args:
          package_ref_or_match_spec (PackageRef or MatchSpec or str):
            e.g. "numpy", "numpy>=1.20", "numpy=1.20.3", "numpy=1.20.3=py38h550f1ac_0"
          channel (str): e.g. "defaults", "conda-forge", "bioconda", "nvidia"
          platform (str): e.g. "linux-64", "linux-aarch64", "osx-64", "osx-arm64", "win-64"
          limit (int): Maximum number of results to return (0 means all).
          offset (int): Number of results to skip before applying limit (for paging).
          get_keys (str): Comma-separated field names to include in results.
                         Empty string returns all fields (default).
                         Example: "version,build,url" reduces context by ~60-70%.

        Returns:
          dict with keys:
            - results: list of package records (filtered by get_keys if specified)
            - total: total number of matching packages
            - limit: limit used in this query
            - offset: offset used in this query
        """
        try:
            return await asyncio.to_thread(
                _package_search,
                package_ref_or_match_spec,
                channel,
                platform,
                limit,
                offset,
                get_keys,
            )
        except ValueError as ve:
            raise ToolError(f"[validation_error] Invalid input: {ve}") from ve
        except Exception as e:
            raise ToolError(f"[unknown_error] 'package_search' failed: {e}") from e
