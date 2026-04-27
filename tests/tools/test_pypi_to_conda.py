from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conda_meta_mcp.tools import pypi_to_conda as pypi_to_conda_module


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pypi_name,expected_conda,expected_changed",
    [
        ("authzed", "authzed-py", True),
        ("cashews", "cashews", False),
        ("PyYAML", "pyyaml", False),
    ],
)
async def test_pypi_to_conda__success_parametrized(
    server, pypi_name, expected_conda, expected_changed
):
    """
    Parametrized happy-path test for the pypi_to_conda tool.

    We validate:
      * Schema keys are present.
      * Returned mapping matches expected (for well-known packages).
      * `changed` flag matches the tool's definition (conda_name != pypi_name.lower()).
    """
    async with Client(server) as client:
        result = await client.call_tool("pypi_to_conda", {"pypi_name": pypi_name})
        data = result.data

        assert sorted(data.keys()) == ["changed", "conda_name", "pypi_name"]

        assert data["pypi_name"] == pypi_name
        assert data["conda_name"] == expected_conda
        assert data["changed"] == expected_changed

        # Derive expected_changed from logic for extra safety
        assert data["changed"] == (data["conda_name"] != pypi_name.lower())


@pytest.mark.asyncio
async def test_pypi_to_conda__error_empty_input(server):
    """
    Empty input should raise a ToolError (input validation path).
    """
    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool("pypi_to_conda", {"pypi_name": ""})


@pytest.mark.asyncio
async def test_pypi_to_conda__disabled_when_dependency_missing(monkeypatch):
    pypi_to_conda_module._map_pypi_name.cache_clear()
    monkeypatch.setattr(pypi_to_conda_module, "map_pypi_to_conda", None)

    with pytest.raises(ToolError) as exc:
        await pypi_to_conda_module.pypi_to_conda("authzed")

    assert str(exc.value) == "Disabled, enable via installing the package conda-forge-metadata"
    pypi_to_conda_module._map_pypi_name.cache_clear()
