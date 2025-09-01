from __future__ import annotations

import pytest  # type: ignore[import-not-found]
from fastmcp import Client
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
async def test_cli_help__success(server):
    async with Client(server) as client:
        result = await client.call_tool("cli_help", {})
        assert isinstance(result.data, str)
        assert "repoquery" in result.data


@pytest.mark.asyncio
async def test_cli_help__unknown_tool_error(server):
    with pytest.raises(ToolError):
        async with Client(server) as client:
            await client.call_tool("cli_help", {"tool": "unknown_tool_xyz"})
