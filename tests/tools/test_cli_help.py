from __future__ import annotations

import pytest
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
