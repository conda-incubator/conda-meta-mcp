"""
Tests for Phase 1 optimizations: get_keys parameter filtering and grep functionality.

Tests cover:
- get_keys parameter for field filtering (pkg_search, repoquery, pkg_insights, import_mapping)
- grep parameter for text filtering (cli_help)
- Context reduction validation
- Backward compatibility (empty get_keys/grep returns all data)
"""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

# ============================================================================
# Tests for get_keys parameter (pkg_search)
# ============================================================================


@pytest.mark.asyncio
async def test_pkg_search__get_keys_empty_returns_all(server):
    """Empty get_keys should return all fields (backward compatible)."""
    async with Client(server) as client:
        result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "numpy",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 1,
                "get_keys": "",  # Empty = all fields
            },
        )
        data = result.data
        assert "results" in data
        results = data["results"]
        assert len(results) == 1
        record = results[0]
        # Should have all 5 fields from PackageRecord
        expected_keys = {"version", "build_number", "build", "url", "depends"}
        assert expected_keys.issubset(record.keys())


@pytest.mark.asyncio
async def test_pkg_search__get_keys_filters_fields(server):
    """get_keys parameter should filter result to only requested fields."""
    async with Client(server) as client:
        result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "numpy",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 1,
                "get_keys": "version,url",  # Only these 2 fields
            },
        )
        data = result.data
        assert "results" in data
        results = data["results"]
        assert len(results) == 1
        record = results[0]
        # Should have ONLY the requested fields
        assert set(record.keys()) == {"version", "url"}
        assert "build" not in record
        assert "build_number" not in record
        assert "depends" not in record


@pytest.mark.asyncio
async def test_pkg_search__get_keys_context_reduction(server):
    """get_keys should reduce result size significantly."""
    async with Client(server) as client:
        # Get full result
        full_result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "numpy",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 5,
                "get_keys": "",
            },
        )
        full_size = len(str(full_result.data["results"]))

        # Get filtered result
        filtered_result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "numpy",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 5,
                "get_keys": "version,url",
            },
        )
        filtered_size = len(str(filtered_result.data["results"]))

        # Filtered should be significantly smaller
        reduction = (full_size - filtered_size) / full_size
        assert reduction > 0.5  # At least 50% reduction


# ============================================================================
# Tests for get_keys parameter (repoquery)
# ============================================================================


@pytest.mark.asyncio
async def test_repoquery__get_keys_empty_returns_all(server):
    """Empty get_keys should return all package fields (backward compatible)."""
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 1,
                "offset": 0,
                "get_keys": "",  # Empty = all fields
            },
        )
        data = result.data
        # Should have 20+ fields per package
        inner = data.get("result", {})
        packages = inner.get("pkgs") or inner.get("result", {}).get("pkgs", [])
        assert len(packages) > 0
        first_pkg = packages[0]
        # Verify we have many fields
        assert len(first_pkg.keys()) >= 15


@pytest.mark.asyncio
async def test_repoquery__get_keys_filters_packages(server):
    """get_keys parameter should filter packages to only requested fields."""
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 2,
                "offset": 0,
                "get_keys": "name,version,url",  # Only these 3 fields
            },
        )
        data = result.data
        inner = data.get("result", {})
        packages = inner.get("pkgs") or inner.get("result", {}).get("pkgs", [])

        # All packages should have ONLY requested fields
        for pkg in packages:
            assert set(pkg.keys()) == {"name", "version", "url"}
            assert "build" not in pkg
            assert "depends" not in pkg


@pytest.mark.asyncio
async def test_repoquery__get_keys_context_reduction(server):
    """get_keys should reduce repoquery result size by 60-80%."""
    async with Client(server) as client:
        # Get full result
        full_result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 5,
                "offset": 0,
                "get_keys": "",
            },
        )
        full_size = len(str(full_result.data))

        # Get filtered result
        filtered_result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 5,
                "offset": 0,
                "get_keys": "name,version",
            },
        )
        filtered_size = len(str(filtered_result.data))

        # Filtered should be significantly smaller (60-80% reduction)
        reduction = (full_size - filtered_size) / full_size
        assert reduction > 0.6  # At least 60% reduction


# ============================================================================
# Tests for get_keys parameter (import_mapping)
# ============================================================================


@pytest.mark.asyncio
async def test_import_mapping__get_keys_empty_returns_all(server):
    """Empty get_keys should return all fields (backward compatible)."""
    async with Client(server) as client:
        result = await client.call_tool(
            "import_mapping",
            {
                "import_name": "numpy",
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
                "get_keys": "best_package,heuristic",  # Only these 2 fields
            },
        )
        data = result.data
        # Should have ONLY the requested fields
        assert set(data.keys()) == {"best_package", "heuristic"}
        assert "query_import" not in data
        assert "normalized_import" not in data


# ============================================================================
# Tests for grep parameter (cli_help)
# ============================================================================


@pytest.mark.asyncio
async def test_cli_help__grep_empty_returns_all(server):
    """Empty grep should return all lines (backward compatible)."""
    async with Client(server) as client:
        result = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                "grep": "",  # Empty = all lines
            },
        )
        data = result.data
        lines = data.strip().split("\n")
        # Full help should have 1000+ lines
        assert len(lines) > 1000


@pytest.mark.asyncio
async def test_cli_help__grep_filters_lines(server):
    """grep parameter should filter to only matching lines."""
    async with Client(server) as client:
        # Search for install-related commands
        result = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                "grep": "install",
            },
        )
        data = result.data
        lines = [line for line in data.strip().split("\n") if line.strip()]

        # All non-empty lines should contain "install" (case-insensitive)
        for line in lines:
            assert "install" in line.lower()

        # Should be much fewer lines than full help
        assert len(lines) < 100  # Full help > 1000, grep results < 100


@pytest.mark.asyncio
async def test_cli_help__grep_context_reduction(server):
    """grep should reduce context usage by ~90% for targeted queries."""
    async with Client(server) as client:
        # Get full help
        full_result = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                "grep": "",
            },
        )
        full_size = len(full_result.data)

        # Get filtered help
        filtered_result = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                "grep": "install|update|create",
            },
        )
        filtered_size = len(filtered_result.data)

        # Should be significantly smaller (~90% or more)
        reduction = (full_size - filtered_size) / full_size
        assert reduction > 0.85  # At least 85% reduction (typically 90%+)


@pytest.mark.asyncio
async def test_cli_help__grep_case_insensitive(server):
    """grep should be case-insensitive."""
    async with Client(server) as client:
        # Search lowercase
        result_lower = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                "grep": "install",
            },
        )
        lower_lines = len([line for line in result_lower.data.split("\n") if line.strip()])

        # Search uppercase
        result_upper = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                "grep": "INSTALL",
            },
        )
        upper_lines = len([line for line in result_upper.data.split("\n") if line.strip()])

        # Should return same number of results (case-insensitive)
        assert lower_lines == upper_lines


@pytest.mark.asyncio
async def test_cli_help__grep_regex_patterns(server):
    """grep should support regex patterns."""
    async with Client(server) as client:
        # Use regex alternation for common conda subcommands
        result = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                "grep": "create|install|list",  # Lines containing create, install, or list
            },
        )
        data = result.data
        lines = [line for line in data.strip().split("\n") if line.strip()]

        # Should have some matching lines
        assert len(lines) > 0

        # Each line should match the pattern (case-insensitive)
        import re

        pattern = re.compile("create|install|list", re.IGNORECASE)
        for line in lines:
            assert pattern.search(line)


@pytest.mark.asyncio
async def test_cli_help__grep_invalid_regex_error(server):
    """grep with invalid regex should raise error."""
    with pytest.raises(ToolError):
        async with Client(server) as client:
            await client.call_tool(
                "cli_help",
                {
                    "tool": "conda",
                    "grep": "[invalid(regex",  # Invalid regex syntax
                },
            )


# ============================================================================
# Tests for backward compatibility
# ============================================================================


@pytest.mark.asyncio
async def test_pkg_search__backward_compat_no_get_keys_param(server):
    """Old calls without get_keys should still work."""
    async with Client(server) as client:
        result = await client.call_tool(
            "package_search",
            {
                "package_ref_or_match_spec": "numpy",
                "channel": "conda-forge",
                "platform": "osx-arm64",
                "limit": 1,
                # No get_keys parameter
            },
        )
        data = result.data
        assert "results" in data
        results = data["results"]
        assert len(results) == 1
        # Should return all fields by default
        expected_keys = {"version", "build_number", "build", "url", "depends"}
        assert expected_keys.issubset(results[0].keys())


@pytest.mark.asyncio
async def test_repoquery__backward_compat_no_get_keys_param(server):
    """Old repoquery calls without get_keys should still work."""
    async with Client(server) as client:
        result = await client.call_tool(
            "repoquery",
            {
                "subcmd": "depends",
                "spec": "python",
                "channel": "conda-forge",
                "limit": 1,
                # No get_keys parameter
            },
        )
        data = result.data
        inner = data.get("result", {})
        packages = inner.get("pkgs") or inner.get("result", {}).get("pkgs", [])
        # Should return all fields by default
        assert len(packages[0].keys()) >= 15


@pytest.mark.asyncio
async def test_cli_help__backward_compat_no_grep_param(server):
    """Old cli_help calls without grep should still work."""
    async with Client(server) as client:
        result = await client.call_tool(
            "cli_help",
            {
                "tool": "conda",
                # No grep parameter
            },
        )
        data = result.data
        lines = data.strip().split("\n")
        # Should return all lines
        assert len(lines) > 1000
