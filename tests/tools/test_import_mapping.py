from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

# Heuristic labels the tool may legitimately emit. Keeping a central set makes the
# success test resilient to minor internal mapping changes upstream.
VALID_HEURISTICS = {
    "identity",
    "identity_present",
    "ranked_selection",
    "fallback",
}


@pytest.mark.asyncio
async def test_import_mapping__success_basic(server):
    """
    Basic happy-path test: provide a dotted import and validate the response schema
    and invariants. We intentionally do NOT assert an exact best_package value
    (to stay resilient to upstream mapping evolution) but we enforce structural
    correctness and heuristic membership.
    """
    async with Client(server) as client:
        # Use a very common library import that should resolve deterministically.
        result = await client.call_tool(
            "import_mapping",
            {
                "import_name": "numpy.linalg",
            },
        )
        data = result.data
        # Schema keys
        assert sorted(data.keys()) == [
            "best_package",
            "candidate_packages",
            "heuristic",
            "normalized_import",
            "query_import",
        ]
        # Field relationships
        assert data["query_import"] == "numpy.linalg"
        assert data["normalized_import"] == "numpy"
        assert isinstance(data["candidate_packages"], list)
        assert all(isinstance(x, str) for x in data["candidate_packages"])
        assert data["heuristic"] in VALID_HEURISTICS
        assert isinstance(data["best_package"], str)


@pytest.mark.asyncio
async def test_import_mapping__error_on_empty_input(server):
    """
    Passing an empty string should surface a ToolError (input validation branch).
    """
    async with Client(server) as client:
        with pytest.raises(ToolError) as exc:
            await client.call_tool(
                "import_mapping",
                {
                    "import_name": "",
                },
            )
        # Sanity check on error message clarity
        assert "invalid input" in str(exc.value).lower()
