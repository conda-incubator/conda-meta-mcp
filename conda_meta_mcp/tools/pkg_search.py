from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError
from pydantic import BaseModel

if TYPE_CHECKING:
    from fastmcp import FastMCP

from conda.api import SubdirData


class PackageRecord(BaseModel):
    version: str
    build_number: str
    build: str
    url: str
    depends: str


@lru_cache(maxsize=1000)
def _full_package_search(package_ref_or_match_spec, channel, platform) -> list[PackageRecord]:
    return [
        PackageRecord(
            version=str(match.version),
            build_number=str(match.build_number),
            build=str(match.build),
            url=str(match.url),
            depends=str(match.depends),
        )
        for match in SubdirData.query_all(
            package_ref_or_match_spec, channels=[f"{channel}/{platform}"], subdirs=[platform]
        )
    ]


def _package_search(package_ref_or_match_spec, channel, platform, limit) -> list[PackageRecord]:
    results = _full_package_search(package_ref_or_match_spec, channel, platform)
    if limit and limit > 0:
        return results[-limit:]
    return results


def register_package_search(mcp: FastMCP) -> None:
    @mcp.tool
    async def package_search(
        package_ref_or_match_spec: str, channel: str, platform: str, limit: int = 0
    ) -> list[PackageRecord]:
        """
        Search available conda packages matching the given package_ref_or_match_spec, channel, and
        platform.

        package_ref_or_match_spec (PackageRef or MatchSpec or str): The package reference or match
          specification to search for, e.g. "numpy", "numpy>=1.20", "numpy=1.20.3",
          "numpy=1.20.3=py38h550f1ac_0".
        channel (str): The channel to search in, e.g. "defaults", "conda-forge", "bioconda",
          "nvidia"
        platform (str): The platform to search for, e.g. "linux-64", "linux-aarch64" "osx-64",
          "osx-arm64", "win-64"
        limit (int): The maximum number of results to return.
        """
        try:
            return await asyncio.to_thread(
                _package_search, package_ref_or_match_spec, channel, platform, limit
            )
        except Exception as e:
            raise ToolError(f"'package_search' failed with: {e}")
