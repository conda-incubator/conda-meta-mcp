"""
This module contains a tool to read the content of the info tarball within conda packages

It uses conda_package_streaming to access the data, which is possible within ~100 milliseconds
for CDN provided channels.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

if TYPE_CHECKING:
    from fastmcp import FastMCP

from conda_package_streaming.url import stream_conda_info

SOME_FILES = {"info/recipe/meta.yaml", "info/about.json", "info/run_exports.json"}


@lru_cache(maxsize=1000)
def _read_all(url) -> dict[str, str]:
    data = {}
    for tar, member in stream_conda_info(url):
        try:
            data[member.name] = tar.extractfile(member).read().decode()
        except Exception as e:
            data[member.name] = f"error while extracting: {e}"
    return data


def _package_insights(url: str, file: str = "some") -> dict[str, str]:
    data = _read_all(url)
    match file:
        case "all":
            return data
        case "some":
            return {k: v for k, v in data.items() if k in SOME_FILES}
        case "list-without-content":
            return {k: "" for k, v in data.items() if k in SOME_FILES}
        case _:
            return {file: data[file]}


def register_package_insights(mcp: FastMCP) -> None:
    @mcp.tool
    async def package_insights(url: str, file: str = "some") -> dict[str, str]:
        """
        Provides insights into a package's info tarball

        That includes the rendered recipe (meta.yaml) that allows for easy inspection of the
        package's build process, e.g. see build, host and run time dependencies. Which have
        big influence on what packages are linked against. The run_exports which end up as
        run time dependencies for other packages linked against this package. And the about
        information which contain the remote_url and sha to the repo location where the
        package recipe is maintained. That helps to open PRs in the right location to fix
        issues with the recipe.

        Args:
          url: The full package URL, e.g.
          "https://conda.anaconda.org/conda-forge/linux-64/numpy-1.24.3-py311h7f8727e_0.tar.bz2"

          file: can be set to "some", "all", "list-without-content" or to a specific filename
          like "info/recipe/meta.yaml"

          Returns:
            A dictionary with key=filename, value=content.
        """
        try:
            return await asyncio.to_thread(_package_insights, url, file)
        except Exception as e:
            raise ToolError(f"'package_insights' failed with: {e}")
