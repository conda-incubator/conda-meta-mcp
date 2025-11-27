import asyncio
import time
from typing import Any

import psutil
import pytest

from conda_meta_mcp.server import setup_server


def _current_rss_mb() -> float:
    """Return current process RSS in megabytes."""
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)


async def _hammer_tools(client: Any, iterations: int = 2) -> None:
    """Call memory-heavy tools repeatedly to exercise caches."""
    for _ in range(iterations):
        # package_search: hits SubdirData and _full_package_search cache
        await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "numpy",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 50,
                "get_keys": "",
            },
        )

        # repoquery: uses libmamba and _cached_raw_query cache
        await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "tree": True,
                "offset": 0,
                "limit": 100,
                "get_keys": "",
            },
        )

        # pypi_to_conda: exercises _map_pypi_name cache
        await client.call_tool(
            "pypi_to_conda",
            {
                "pypi_name": "numpy",
            },
        )


@pytest.mark.asyncio
async def test_cache_maintenance__called__memory_freed() -> None:
    from fastmcp.client import Client  # type: ignore[import-not-found]

    server = setup_server(log_level="INFO")

    async with Client(server) as client:
        baseline = _current_rss_mb()

        await _hammer_tools(client, iterations=2)
        after_load = _current_rss_mb()

        await client.call_tool("cache_maintenance", {})

        await asyncio.sleep(0.5)
        import gc

        gc.collect()
        time.sleep(0.5)

        after_cleanup = _current_rss_mb()

        assert after_load >= baseline
        assert after_cleanup <= after_load
        assert after_load - after_cleanup >= 128
