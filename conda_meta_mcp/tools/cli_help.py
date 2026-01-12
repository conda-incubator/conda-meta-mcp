"""
Tool to get the entire cli help for a given command line tool.

Currently based on https://github.com/praiskup/argparse-manpage
"""

from __future__ import annotations

import asyncio
import re
from functools import cache

from fastmcp.exceptions import ToolError

from .registry import register_tool


@cache
def _get_conda_help() -> str:
    from argparse_manpage.manpage import Manpage
    from conda.cli.conda_argparse import generate_parser

    return str(Manpage(generate_parser(add_help=True, prog="conda")))


def _cli_help(tool: str = "conda", limit: int = 0, offset: int = 0, grep: str = "") -> str:
    match tool:
        case "conda":
            lines = _get_conda_help().splitlines()

            # Apply regex filtering if grep is provided
            if grep and grep.strip():
                try:
                    pattern = re.compile(grep, re.IGNORECASE)
                    lines = [line for line in lines if pattern.search(line)]
                except re.error as e:
                    raise ToolError(f"Invalid regex pattern: {e}") from e

            # Apply pagination
            offset = max(offset or 0, 0)
            lines = lines[offset : offset + limit] if limit and limit > 0 else lines[offset:]
            return "\n".join(lines)
        case _:
            raise ToolError(f"Unknown/ not yet implemented tool: {tool}")


@register_tool
async def cli_help(tool: str = "conda", limit: int = 0, offset: int = 0, grep: str = "") -> str:
    """
    Provides the full help text for the given tool including all subcommands and options.

    To be used to answer advanced CLI questions beyond the knowledge cutoff of models,
    to e.g. help with new features that recently landed in the tool.

    Args:
        tool: str = "conda"
        limit: max number of lines returned (0 means all)
        offset: number of initial lines skipped
        grep: Regular expression pattern to filter help lines (case-insensitive).
              Empty string returns all lines (default).
              Example: "install|update|create" returns lines matching any of these.
              Reduces context by ~90% for targeted queries.

    Returns:
      A string with the help text
    """
    try:
        return await asyncio.to_thread(_cli_help, tool, limit, offset, grep)
    except ValueError as ve:
        raise ToolError(f"[validation_error] Invalid input: {ve}") from ve
    except Exception as e:
        raise ToolError(f"[unknown_error] 'cli_help' failed: {e}") from e
