from __future__ import annotations

import pytest

from conda_meta_mcp.server import setup_server


@pytest.fixture
def server(monkeypatch):
    """
    Function-scoped FastMCP server fixture.

    A fresh server instance is created for each test to avoid any unintended
    cross-test state leakage. Tests can use this fixture directly:

        async def test_something(server):
            async with Client(server) as client:
                ...
    """
    monkeypatch.setattr("conda_meta_mcp.server.prepare_cli", lambda: None)
    return setup_server()
