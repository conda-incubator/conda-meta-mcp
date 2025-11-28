from unittest.mock import patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
@patch("conda_meta_mcp.tools.info._get_info", return_value={"conda_version": "MOCKED"})
async def test_info__get_info__called(mock_get_info, server):
    async with Client(server) as client:
        result = await client.call_tool("info", {})
        assert result.data == {"conda_version": "MOCKED"}
    mock_get_info.assert_called_once()


@pytest.mark.asyncio
@patch("conda_meta_mcp.tools.info._get_info", side_effect=Exception("MOCKED"))
async def test_info__error__handled(mock_get_info, server):
    with pytest.raises(ToolError):
        async with Client(server) as client:
            await client.call_tool("info", {})
    mock_get_info.assert_called_once()


@pytest.mark.asyncio
async def test_info__get_info__correct_schema(server):
    async with Client(server) as client:
        result = await client.call_tool("info", {})
        assert sorted(result.data.keys()) == [
            "conda_meta_mcp_version",
            "conda_package_streaming_version",
            "conda_version",
            "fastmcp_version",
            "libmambapy_version",
            "pixi_env_path",
        ]
