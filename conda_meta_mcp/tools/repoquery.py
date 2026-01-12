"""
repoquery tool

This tool is based on:
`conda_libmamba_solver.index.LibMambaIndexHelper`
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, cast

from conda.base.context import context
from conda.models.channel import Channel
from conda_libmamba_solver.index import LibMambaIndexHelper
from fastmcp.exceptions import ToolError

from .registry import register_tool

ALLOWED_SUBCMDS = {"depends", "whoneeds"}


def _filter_package_keys(pkg: dict[str, Any], get_keys: str) -> dict[str, Any]:
    """Filter a package record to specified keys only.

    Args:
        pkg: Package record dictionary
        get_keys: Comma-separated field names to include (empty = all fields)

    Returns:
        Filtered package dictionary
    """
    if not get_keys or not get_keys.strip():
        return pkg

    keys = set(k.strip() for k in get_keys.split(",") if k.strip())
    return {k: v for k, v in pkg.items() if k in keys}


@lru_cache(maxsize=64)
def _cached_raw_query(subcmd: str, spec: str, channel: str, platform: str, tree: bool) -> dict:
    """
    Execute the underlying query once and cache the full (unpaginated) raw payload.

    For 'depends' / 'whoneeds' we return the raw QueryResult.to_dict() structure.
    """
    index = LibMambaIndexHelper(
        installed_records=(),
        channels=[Channel(channel)],
        subdirs=(platform, "noarch"),
        repodata_fn=context.repodata_fns[-1],
    )

    if subcmd == "depends":
        raw = index.depends(spec, tree=tree, return_type="raw")
        return cast("Any", raw).to_dict()
    else:  # whoneeds
        raw = index.whoneeds(spec, tree=tree, return_type="raw")
        return cast("Any", raw).to_dict()


def _run_repoquery(
    subcmd: str,
    spec: str,
    channel: str,
    platform: str | None,
    tree: bool,
    offset: int,
    limit: int,
    get_keys: str = "",
) -> dict[str, Any]:
    """Run the actual repoquery with pagination and field filtering.

    Returns a RepoQueryResult dictionary containing query metadata and result payload.
    """
    subcmd = subcmd.lower()
    if subcmd not in ALLOWED_SUBCMDS:
        raise ToolError(
            f"Unsupported subcmd '{subcmd}'. Must be one of {sorted(ALLOWED_SUBCMDS)}."
        )

    platform = platform or context.subdir
    spec = spec.strip()
    channel = channel.strip()
    offset = max(offset or 0, 0)
    limit = max(limit or 0, 0)

    raw_data = _cached_raw_query(subcmd, spec, channel, platform, tree)

    total = len(raw_data.get("result", {}).get("pkgs", []))
    if (offset or limit) and "result" in raw_data and "pkgs" in raw_data["result"]:
        pkgs = raw_data["result"]["pkgs"]
        slice_ = pkgs[offset : (offset + limit) if limit else None]
        # Shallow copy outer + inner to avoid mutating cache
        new_outer = dict(raw_data)
        new_inner = dict(new_outer.get("result", {}))
        # Apply field filtering if get_keys is specified
        new_inner["pkgs"] = [_filter_package_keys(pkg, get_keys) for pkg in slice_]
        new_inner["offset"] = offset
        new_inner["limit"] = limit
        new_inner["total"] = total
        new_outer["result"] = new_inner
        result_payload = new_outer
    else:
        result_payload = raw_data
        # Apply field filtering to all packages if no pagination
        if get_keys and "result" in result_payload and "pkgs" in result_payload["result"]:
            result_payload["result"]["pkgs"] = [
                _filter_package_keys(pkg, get_keys) for pkg in result_payload["result"]["pkgs"]
            ]

    return {
        "query": {
            "subcmd": subcmd,
            "spec": spec,
            "channel": channel,
            "platform": platform,
            "tree": tree,
            "offset": offset,
            "limit": limit,
            "installed_included": False,
            "total": total,
        },
        "result": result_payload,
    }


@register_tool(cache_clearers=[_cached_raw_query.cache_clear])
async def repoquery(
    subcmd: str,
    spec: str,
    channel: str,
    platform: str = "linux-64",
    tree: bool = False,
    offset: int = 0,
    limit: int = 30,
    get_keys: str = "",
) -> dict[str, Any]:
    """
    Run a conda repoquery (depends | whoneeds) for a single spec
    and channel. Installed packages excluded. Supports pagination via offset/limit.
    - depends/whoneeds: raw structure unpaginated; sliced pkgs list with offset/limit/total
      when paginated

    Args:
        subcmd (str): e.g. "depends": show dependencies of this package,
                           "whoneeds": show packages that depend on this package.
        channel (str): e.g. "defaults", "conda-forge", "bioconda", "nvidia"
        platform (str): e.g. "linux-64", "linux-aarch64", "osx-64", "osx-arm64", "win-64"
        limit (int): for pagination / slicing
        offset (int): for pagination / slicing
        get_keys (str): Comma-separated field names to include in results.
                       Empty string returns all fields (default).
                       Example: "name,version,url,license" reduces context by ~60-80%.
    """
    try:
        return await asyncio.to_thread(
            _run_repoquery,
            subcmd,
            spec,
            channel,
            platform,
            tree,
            offset,
            limit,
            get_keys,
        )
    except Exception as e:
        raise ToolError(f"'repoquery' failed: {e}") from e
