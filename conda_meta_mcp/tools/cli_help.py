"""
Tool to get the entire cli help for a given command line tool.

Currently based on https://github.com/praiskup/argparse-manpage
"""

from __future__ import annotations

import asyncio
from functools import cache
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from fastmcp import FastMCP


@cache
def _get_conda_help() -> str:
    from argparse_manpage.manpage import Manpage
    from conda.cli.conda_argparse import generate_parser

    return str(Manpage(generate_parser(add_help=True, prog="conda")))


def _cli_help(tool: str = "conda", limit: int = 0, offset: int = 0) -> str:
    match tool:
        case "conda":
            lines = _get_conda_help().splitlines()
            lines = lines[offset : offset + limit] if limit and limit > 0 else lines[offset:]
            return "\n".join(lines)
        case _:
            raise ToolError(f"Unknown/ not yet implemented tool: {tool}")


def register_cli_help(mcp: FastMCP) -> None:
    @mcp.tool
    async def cli_help(tool: str = "conda", limit: int = 0, offset: int = 0) -> str:
        """
        Provides the full help text for the given tool including all subcommands and options.

        To be used to answer advanced CLI questions beyond the knowledge cutoff of models,
        to e.g. help with new features that recently landed in the tool.

        tool: str = "conda"
        limit: max number of lines returned (0 means all)
        offset: number of initial lines skipped
        Returns:
          A string with the help
        """
        try:
            return await asyncio.to_thread(_cli_help, tool, limit, offset)
        except Exception as e:
            raise ToolError(f"'cli_help' failed: {e}")
