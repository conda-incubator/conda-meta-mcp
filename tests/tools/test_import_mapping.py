from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conda_meta_mcp.tools import import_mapping as import_mapping_module

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
                "channel": "conda-forge",
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
                    "channel": "conda-forge",
                },
            )
        # Sanity check on error message clarity
        assert "invalid input" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_import_mapping__disabled_when_dependency_missing(monkeypatch):
    import_mapping_module._map_import.cache_clear()
    monkeypatch.setattr(import_mapping_module, "get_pkgs_for_import", None)

    with pytest.raises(ToolError) as exc:
        await import_mapping_module.import_mapping("numpy", "conda-forge")

    assert str(exc.value) == "Disabled, enable via installing the package conda-forge-metadata"
    import_mapping_module._map_import.cache_clear()


@pytest.mark.asyncio
async def test_import_mapping__unsupported_channel_before_dependency_missing(monkeypatch):
    import_mapping_module._map_import.cache_clear()
    monkeypatch.setattr(import_mapping_module, "get_pkgs_for_import", None)

    with pytest.raises(ToolError) as exc:
        await import_mapping_module.import_mapping("numpy", "defaults")

    message = str(exc.value)
    assert "No data available for channel 'defaults'" in message
    assert "Try a different channel" in message
    import_mapping_module._map_import.cache_clear()


@pytest.mark.asyncio
async def test_import_mapping__get_keys_empty_returns_all(server):
    """Empty get_keys should return all fields (backward compatible)."""
    async with Client(server) as client:
        result = await client.call_tool(
            "import_mapping",
            {
                "import_name": "numpy",
                "channel": "conda-forge",
                "get_keys": "",  # Empty = all fields
            },
        )
        data = result.data
        # Should have all 5 fields
        expected_keys = {
            "query_import",
            "normalized_import",
            "best_package",
            "candidate_packages",
            "heuristic",
        }
        assert set(data.keys()) == expected_keys


@pytest.mark.asyncio
async def test_import_mapping__get_keys_filters_result(server):
    """get_keys parameter should filter result to only requested fields."""
    async with Client(server) as client:
        result = await client.call_tool(
            "import_mapping",
            {
                "import_name": "numpy",
                "channel": "conda-forge",
                "get_keys": "best_package,heuristic",  # Only these 2 fields
            },
        )
        data = result.data
        # Should have ONLY the requested fields
        assert set(data.keys()) == {"best_package", "heuristic"}
        assert "query_import" not in data
        assert "normalized_import" not in data
