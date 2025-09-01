from __future__ import annotations

import pytest

from conda_meta_mcp.server import setup_server


@pytest.fixture
def server():
    """
    Function-scoped FastMCP server fixture.

    A fresh server instance is created for each test to avoid any unintended
    cross-test state leakage. Tests can use this fixture directly:

        async def test_something(server):
            async with Client(server) as client:
                ...
    """
    return setup_server()
