from __future__ import annotations

from itertools import pairwise
from unittest.mock import patch

import pytest
from conda.models.version import VersionOrder
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _is_sorted_newest_first(records: list[dict]) -> bool:
    """
    Validate that records are ordered newest-first by (version, build_number) according to
    conda's VersionOrder, then numeric build_number.
    """

    def key(r):
        version = VersionOrder(r["version"])
        bn = int(r["build_number"])
        return (version, bn)

    return all(key(prev) >= key(curr) for prev, curr in pairwise(records))


@pytest.mark.asyncio
async def test_pkg_search__basic_schema(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd",
                "channel": "conda-forge",
                "platform": "osx-arm64",
            },
        )
        data = result.data
        assert isinstance(data, list)
        assert len(data) > 0
        required_keys = {"version", "build_number", "build", "url", "depends"}
        for entry in data[:5]:  # sample a few to keep test lighter
            assert required_keys.issubset(entry.keys())
        assert _is_sorted_newest_first(data)


@pytest.mark.asyncio
async def test_pkg_search__version_filter(server):
    async with Client(server) as client:
        # Use a specific version constraint that should exist.
        version_spec = "1.5.7"
        result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": f"zstd={version_spec}",
                "channel": "conda-forge",
                "platform": "osx-arm64",
            },
        )
        data = result.data
        assert len(data) > 0
        assert all(entry["version"] == version_spec for entry in data)


@pytest.mark.asyncio
async def test_pkg_search__paging(server):
    async with Client(server) as client:
        # Get a baseline list (capped to avoid huge pulls).
        baseline_limit = 12
        baseline = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": baseline_limit,
            },
        )
        base_list = baseline.data
        # Need enough records for paging validation.
        assert len(base_list) >= 6

        # Page 1 (first 3)
        page1 = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 3,
                "offset": 0,
            },
        )
        # Page 2 (next 3)
        page2 = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 3,
                "offset": 3,
            },
        )
        # Page 3 (next 3)
        page3 = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 3,
                "offset": 6,
            },
        )

        p1 = page1.data
        p2 = page2.data
        p3 = page3.data

        assert p1 == base_list[0:3]
        assert p2 == base_list[3:6]
        assert p3 == base_list[6:9]

        # Ensure no overlap between consecutive pages
        assert not set(tuple(r.items()) for r in p1).intersection(
            set(tuple(r.items()) for r in p2)
        )
        assert not set(tuple(r.items()) for r in p2).intersection(
            set(tuple(r.items()) for r in p3)
        )

        # limit=1 should return the newest record (same as baseline[0])
        newest = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 1,
            },
        )
        assert newest.data[0] == base_list[0]

        # Offset beyond available -> empty
        far_offset = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 5,
                "offset": 10_000,
            },
        )
        assert far_offset.data == []


@pytest.mark.asyncio
@patch("conda_meta_mcp.tools.pkg_search._package_search", side_effect=Exception("MOCKED"))
async def test_pkg_search__error__handled(mock_pkg_search, server):
    with pytest.raises(ToolError):
        async with Client(server) as client:
            await client.call_tool(
                "package_search",
                {
                    "package_ref_or_match_spec": "zstd",
                    "channel": "conda-forge",
                    "platform": "osx-arm64",
                },
            )
    mock_pkg_search.assert_called_once()
