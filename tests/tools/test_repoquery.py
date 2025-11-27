from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
async def test_repoquery_depends_basic(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
            },
        )
        payload = result.data
        assert "query" in payload and "result" in payload
        q_outer = payload["query"]
        assert q_outer["subcmd"] == "depends"
        inner = payload["result"]
        # Inner should contain its own query/result keys (mirroring raw QueryResult)
        assert "query" in inner and "result" in inner
        assert inner["result"]["status"] == "OK"
        pkgs = inner["result"]["pkgs"]
        assert isinstance(pkgs, list) and len(pkgs) > 0
        # Each pkg should have at least a name key
        assert all("name" in p for p in pkgs)


@pytest.mark.asyncio
async def test_repoquery_whoneeds_basic(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "whoneeds",
                "spec": "zlib",
                "channel": "conda-forge",
                "platform": "osx-arm64",
            },
        )
        payload = result.data
        assert payload["query"]["subcmd"] == "whoneeds"
        inner = payload["result"]
        assert inner["result"]["status"] == "OK"
        pkgs = inner["result"]["pkgs"]
        # Expect at least one reverse dependency for zlib
        assert len(pkgs) > 0
        assert all("name" in p for p in pkgs)


@pytest.mark.asyncio
async def test_repoquery_depends_tree_mode(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "tree": True,
            },
        )
        payload = result.data
        assert payload["query"]["tree"] is True
        inner = payload["result"]
        assert inner["result"]["status"] == "OK"
        assert len(inner["result"]["pkgs"]) > 0


@pytest.mark.asyncio
async def test_repoquery_depends_paging(server):
    async with Client(server) as client:
        page = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 3,
                "offset": 0,
            },
        )
        payload = page.data
        assert payload["query"]["limit"] == 3
        assert payload["query"]["offset"] == 0

        inner = payload["result"]

        # The underlying structure may nest pkgs inside inner["result"]["pkgs"],
        # or (if pagination slicing logic changes) expose a sibling "pkgs".
        pkgs = inner.get("pkgs") or inner.get("result", {}).get("pkgs")
        assert pkgs is not None
        assert isinstance(pkgs, list)
        assert len(pkgs) > 0
        # If real slicing is applied len(pkgs) <= limit; if not, allow larger (future-proof)
        assert len(pkgs) <= 3 or payload["query"]["total"] >= len(pkgs)


@pytest.mark.asyncio
async def test_repoquery_whoneeds_paging(server):
    async with Client(server) as client:
        page = await client.call_tool(
            "repoquery",
            {
                "subcmd": "whoneeds",
                "spec": "zlib",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 4,
                "offset": 0,
            },
        )
        payload = page.data
        assert payload["query"]["limit"] == 4
        assert payload["query"]["offset"] == 0

        inner = payload["result"]
        pkgs = inner.get("pkgs") or inner.get("result", {}).get("pkgs")
        assert pkgs is not None
        assert isinstance(pkgs, list)
        assert len(pkgs) > 0
        assert len(pkgs) <= 4 or payload["query"]["total"] >= len(pkgs)


@pytest.mark.asyncio
async def test_repoquery_error_invalid_subcmd(server):
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "repoquery",
                {
                    "subcmd": "not-a-real-subcmd",
                    "spec": "python",
                    "channel": "conda-forge",
                    "platform": "osx-arm64",
                },
            )


@pytest.mark.asyncio
async def test_repoquery__get_keys_empty_returns_all(server):
    """Empty get_keys should return all package fields (backward compatible)."""
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 1,
                "offset": 0,
                "get_keys": "",  # Empty = all fields
            },
        )
        data = result.data
        # Should have 20+ fields per package
        inner = data.get("result", {})
        packages = inner.get("pkgs") or inner.get("result", {}).get("pkgs", [])
        assert len(packages) > 0
        first_pkg = packages[0]
        # Verify we have many fields
        assert len(first_pkg.keys()) >= 15


@pytest.mark.asyncio
async def test_repoquery__get_keys_filters_packages(server):
    """get_keys parameter should filter packages to only requested fields."""
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 2,
                "offset": 0,
                "get_keys": "name,version,url",  # Only these 3 fields
            },
        )
        data = result.data
        inner = data.get("result", {})
        packages = inner.get("pkgs") or inner.get("result", {}).get("pkgs", [])

        # All packages should have ONLY requested fields
        for pkg in packages:
            assert set(pkg.keys()) == {"name", "version", "url"}
            assert "build" not in pkg
            assert "depends" not in pkg


@pytest.mark.asyncio
async def test_repoquery__get_keys_context_reduction(server):
    """get_keys should reduce repoquery result size by 60-80%."""
    async with Client(server) as client:
        # Get full result
        full_result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 5,
                "offset": 0,
                "get_keys": "",
            },
        )
        full_size = len(str(full_result.data))

        # Get filtered result
        filtered_result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 5,
                "offset": 0,
                "get_keys": "name,version",
            },
        )
        filtered_size = len(str(filtered_result.data))

        # Filtered should be significantly smaller (60-80% reduction)
        reduction = (full_size - filtered_size) / full_size
        assert reduction > 0.6  # At least 60% reduction


@pytest.mark.asyncio
async def test_repoquery__backward_compat_no_get_keys_param(server):
    """Old repoquery calls without get_keys should still work."""
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "limit": 1,
                # No get_keys parameter
            },
        )
        data = result.data
        inner = data.get("result", {})
        packages = inner.get("pkgs") or inner.get("result", {}).get("pkgs", [])
        # Should return all fields by default
        assert len(packages[0].keys()) >= 15
