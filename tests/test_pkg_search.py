from unittest.mock import patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conda_meta_mcp.server import setup_server


@pytest.mark.asyncio
async def test_pkg_search__basic_schema():
    server = setup_server()
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


@pytest.mark.asyncio
async def test_pkg_search__version_filter():
    server = setup_server()
    async with Client(server) as client:
        # Pick a specific (currently available) version to ensure filtering works.
        result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "zstd=1.5.7",
                "channel": "conda-forge",
                "platform": "osx-arm64",
            },
        )
        data = result.data
        assert len(data) > 0
        assert all(entry["version"] == "1.5.7" for entry in data)


@pytest.mark.asyncio
@patch("conda_meta_mcp.tools.pkg_search._package_search", side_effect=Exception("MOCKED"))
async def test_pkg_search__error__handled(mock_pkg_search):
    server = setup_server()
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
