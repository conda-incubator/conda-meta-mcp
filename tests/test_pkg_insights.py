from unittest.mock import patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conda_meta_mcp.server import setup_server


@pytest.mark.asyncio
async def test_info__package_insights__correct_schema():
    server = setup_server()
    async with Client(server) as client:
        result = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda"
            },
        )
        assert sorted(result.data.keys()) == [
            "info/about.json",
            "info/recipe/meta.yaml",
            "info/run_exports.json",
        ]


@pytest.mark.asyncio
async def test_info__package_insights__all():
    server = setup_server()
    async with Client(server) as client:
        result = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "all",
            },
        )
        keys = result.data.keys()
        assert "info/recipe/meta.yaml" in keys
        assert len(keys) > 3  # more than the SOME_FILES subset


@pytest.mark.asyncio
async def test_info__package_insights__list_without_content():
    server = setup_server()
    async with Client(server) as client:
        result = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "list-without-content",
            },
        )
        assert sorted(result.data.keys()) == [
            "info/about.json",
            "info/recipe/meta.yaml",
            "info/run_exports.json",
        ]
        assert all(v.isdigit() for v in result.data.values()), result


@pytest.mark.asyncio
async def test_info__package_insights__single_file():
    server = setup_server()
    async with Client(server) as client:
        result = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "info/recipe/meta.yaml",
            },
        )
        assert list(result.data.keys()) == ["info/recipe/meta.yaml"]
        assert result.data["info/recipe/meta.yaml"].strip() != ""


@pytest.mark.asyncio
async def test_info__package_insights__single_file_paging():
    server = setup_server()
    async with Client(server) as client:
        # Get full content
        full = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "info/recipe/meta.yaml",
            },
        )
        full_lines = full.data["info/recipe/meta.yaml"].splitlines()
        assert len(full_lines) > 10  # ensure enough lines to page

        # Get a paged slice of the content (line-level paging)
        paged = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "info/recipe/meta.yaml",
                "limit": 5,
                "offset": 2,
            },
        )
        paged_lines = paged.data["info/recipe/meta.yaml"].splitlines()
        assert paged_lines == full_lines[2 : 2 + 5]


@pytest.mark.asyncio
@patch("conda_meta_mcp.tools.pkg_insights._package_insights", side_effect=Exception("MOCKED"))
async def test_info__package_insights__error__handled(mock_pkg_insights):
    server = setup_server()
    with pytest.raises(ToolError):
        async with Client(server) as client:
            await client.call_tool(
                "package_insights",
                {
                    "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda"
                },
            )
    mock_pkg_insights.assert_called_once()
