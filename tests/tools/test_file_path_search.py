import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
async def test_file_path_search__success(server):
    async with Client(server) as client:
        result = await client.call_tool(
            "file_path_search",
            {
                "path": "bin/fzf",
                "limit": 3,
                "offset": 0,
            },
        )
        data = result.data
        assert "query_path" in data
        assert "artifacts" in data
        assert "count" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert data["query_path"] == "bin/fzf"
        assert isinstance(data["artifacts"], list)
        assert data["count"] == len(data["artifacts"])
        assert data["total"] >= data["count"]
        assert data["limit"] == 3
        assert data["offset"] == 0


@pytest.mark.asyncio
async def test_file_path_search__pagination(server):
    async with Client(server) as client:
        r0 = await client.call_tool(
            "file_path_search",
            {
                "path": "bin/fzf",
                "limit": 1,
                "offset": 0,
            },
        )
        r1 = await client.call_tool(
            "file_path_search",
            {
                "path": "bin/fzf",
                "limit": 1,
                "offset": 1,
            },
        )

        d0 = r0.data
        d1 = r1.data

        assert "artifacts" in d0
        assert "artifacts" in d1
        assert d0["limit"] == 1
        assert d1["limit"] == 1

        total = d0.get("total", d0.get("count", 0))

        # If there are at least two matching artifacts, ensure pagination returns different items
        if total >= 2:
            assert d0["artifacts"][0] != d1["artifacts"][0]


@pytest.mark.asyncio
async def test_file_path_search__error_on_empty_input(server):
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc:
            await client.call_tool(
                "file_path_search",
                {
                    "path": "",
                },
            )
        assert "invalid input" in str(exc.value).lower()
