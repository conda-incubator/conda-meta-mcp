from unittest.mock import patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
async def test_info__package_insights__correct_schema(server):
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
async def test_info__package_insights__all(server):
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
async def test_info__package_insights__list_without_content(server):
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
async def test_info__package_insights__single_file(server):
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
async def test_info__package_insights__single_file_paging(server):
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
async def test_info__package_insights__get_keys_extracts_json_fields(server):
    """get_keys parameter should extract specific fields from JSON files."""
    async with Client(server) as client:
        # Get full about.json
        full_result = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "info/about.json",
            },
        )
        full_content = full_result.data["info/about.json"]
        full_size = len(full_content)

        # Get only specific keys
        filtered_result = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "info/about.json",
                "get_keys": "channels,conda_build_version",
            },
        )
        filtered_content = str(filtered_result.data["info/about.json"])
        filtered_size = len(filtered_content)

        # Filtered result should be smaller
        assert filtered_size < full_size
        # Filtered result should be a dict with only requested keys
        assert isinstance(filtered_result.data["info/about.json"], dict)
        assert "channels" in filtered_result.data["info/about.json"]
        assert "conda_build_version" in filtered_result.data["info/about.json"]


@pytest.mark.asyncio
async def test_info__package_insights__get_keys_requires_single_file(server):
    """get_keys requires exactly one file to be selected."""
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "package_insights",
                {
                    "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                    "file": "some",  # This selects 3 files
                    "get_keys": "channels",
                },
            )
        assert "exactly one file" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_info__package_insights__get_keys_empty_returns_full_content(server):
    """Empty get_keys should return full file content (backward compatible)."""
    async with Client(server) as client:
        result = await client.call_tool(
            "package_insights",
            {
                "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda",
                "file": "info/about.json",
                "get_keys": "",  # Empty = no filtering
            },
        )
        # Should return full string (not parsed)
        assert isinstance(result.data["info/about.json"], str)
        # Should contain valid JSON content
        import json

        parsed = json.loads(result.data["info/about.json"])
        assert "channels" in parsed


@pytest.mark.asyncio
@patch("conda_meta_mcp.tools.pkg_insights._package_insights", side_effect=Exception("MOCKED"))
async def test_info__package_insights__error__handled(mock_pkg_insights, server):
    with pytest.raises(ToolError):
        async with Client(server) as client:
            await client.call_tool(
                "package_insights",
                {
                    "url": "https://conda.anaconda.org/conda-forge/osx-arm64/zstd-1.5.7-h6491c7d_2.conda"
                },
            )
    mock_pkg_insights.assert_called_once()
