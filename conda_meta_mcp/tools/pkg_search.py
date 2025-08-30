from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError
from pydantic import BaseModel

if TYPE_CHECKING:
    from fastmcp import FastMCP

from conda.api import SubdirData
from conda.models.version import VersionOrder


class PackageRecord(BaseModel):
    version: str
    build_number: str
    build: str
    url: str
    depends: str

    class Config:
        allow_mutation = False  # make instances immutable

    def __hash__(self):
        return hash((self.version, self.build_number, self.build, self.url, self.depends))

    def _build_number_int(self):
        return int(self.build_number) if self.build_number.isdigit() else -1

    def _ordering_tuple(self):
        return (VersionOrder(self.version), self._build_number_int())

    def __lt__(self, other):
        return self._ordering_tuple() < other._ordering_tuple()


@lru_cache(maxsize=1000)
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


def _package_search(
    package_ref_or_match_spec, channel, platform, limit, offset
) -> list[PackageRecord]:
    results = _full_package_search(package_ref_or_match_spec, channel, platform)
    offset = max(offset or 0, 0)
    if limit and limit > 0:
        return results[offset : offset + limit]
    return results[offset:]


def register_package_search(mcp: FastMCP) -> None:
    @mcp.tool
    async def package_search(
        package_ref_or_match_spec: str,
        channel: str,
        platform: str,
        limit: int = 0,
        offset: int = 0,
    ) -> list[PackageRecord]:
        """
        Search available conda packages matching the given package_ref_or_match_spec, channel, and
        platform.

        Features:
          - Results are deduplicated.
          - Ordered by newest (version, then build_number descending).
          - limit=1 reliably returns the single newest record.
          - Supports paging via (offset, limit).

        Args:
          package_ref_or_match_spec (PackageRef or MatchSpec or str):
            e.g. "numpy", "numpy>=1.20", "numpy=1.20.3", "numpy=1.20.3=py38h550f1ac_0"
          channel (str): e.g. "defaults", "conda-forge", "bioconda", "nvidia"
          platform (str): e.g. "linux-64", "linux-aarch64", "osx-64", "osx-arm64", "win-64"
          limit (int): Maximum number of results to return (0 means all).
          offset (int): Number of results to skip before applying limit (for paging).
        """
        try:
            return await asyncio.to_thread(
                _package_search, package_ref_or_match_spec, channel, platform, limit, offset
            )
        except Exception as e:
            raise ToolError(f"'package_search' failed with: {e}")
