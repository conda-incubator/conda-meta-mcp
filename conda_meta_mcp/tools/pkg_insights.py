"""
This module contains a tool to read the content of the info tarball within conda packages

It uses conda_package_streaming to access the data, which is possible within ~100 milliseconds
for CDN provided channels.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from typing import Any

import yaml
from conda_package_streaming.url import stream_conda_info
from fastmcp.exceptions import ToolError

from .registry import register_tool

SOME_FILES = {"info/recipe/meta.yaml", "info/about.json", "info/run_exports.json"}


def _line_count(s: str) -> int:
    return len(s.splitlines()) if s else 0


@lru_cache(maxsize=128)
def _read_all(url: str) -> dict[str, str]:
    data = {}
    for tar, member in stream_conda_info(url):
        try:
            data[member.name] = tar.extractfile(member).read().decode()
        except Exception as e:
            data[member.name] = f"error while extracting: {e}"
    return data


def _parse_file_content(content: str, filepath: str) -> Any:
    """Parse file content based on file type (YAML/JSON)."""
    if filepath.endswith(".json"):
        return json.loads(content)
    elif filepath.endswith(".yaml") or filepath.endswith(".yml"):
        return yaml.safe_load(content)
    else:
        # For non-structured files, return as-is
        return content


def _extract_keys_from_dict(data: Any, keys_str: str) -> Any:
    """Extract specified keys from parsed data (dict or list)."""
    if not keys_str or not keys_str.strip():
        return data

    keys = set(k.strip() for k in keys_str.split(",") if k.strip())

    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in keys}
    elif isinstance(data, list):
        # For lists, filter each dict item
        return [
            {k: v for k, v in item.items() if k in keys} if isinstance(item, dict) else item
            for item in data
        ]
    else:
        # For non-dict data, return as-is (can't extract keys)
        return data


def _package_insights(
    url: str,
    file: str = "some",
    limit: int = 0,
    offset: int = 0,
    get_keys: str = "",
) -> dict[str, Any]:
    data = _read_all(url)
    # list-without-content is a listing mode; paging not applied per requirement
    if file == "list-without-content":
        return {k: str(_line_count(v)) for k, v in data.items() if k in SOME_FILES}
    if file == "all":
        selected = data
    elif file == "some":
        selected = {k: v for k, v in data.items() if k in SOME_FILES}
    else:
        selected = {file: data[file]}

    # Apply line-level paging (not file-level): slice lines inside each selected file
    if (limit and limit > 0) or (offset and offset > 0):
        offset = max(offset, 0)
        processed: dict[str, str] = {}
        for k, v in selected.items():
            lines = v.splitlines()
            sliced = lines[offset : offset + limit] if limit and limit > 0 else lines[offset:]
            processed[k] = "\n".join(sliced)
        selected = processed

    # Apply get_keys filtering: parse file and extract specific keys
    if get_keys and get_keys.strip():
        # Only one file can be selected when using get_keys for key extraction
        if len(selected) != 1:
            raise ToolError(
                "get_keys parameter requires exactly one file to be selected. "
                f"Got {len(selected)} files. Use file parameter to select a single file."
            )

        filepath = next(iter(selected.keys()))
        content = selected[filepath]

        try:
            parsed = _parse_file_content(content, filepath)
            extracted = _extract_keys_from_dict(parsed, get_keys)
            return {filepath: extracted}
        except json.JSONDecodeError as e:
            raise ToolError(f"[parsing_error] Failed to parse {filepath} as JSON: {e}") from e
        except Exception as e:
            raise ToolError(f"[parsing_error] Failed to extract keys from {filepath}: {e}") from e

    return selected


@register_tool(cache_clearers=[_read_all.cache_clear])
async def package_insights(
    url: str, file: str = "some", limit: int = 0, offset: int = 0, get_keys: str = ""
) -> dict[str, Any]:
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

      file: can be set to "some", "all", "list-without-content" or a specific filename
      limit: max number of lines returned per file (0 means all; ignored for
        list-without-content)
      offset: number of initial lines skipped per file (ignored for
        list-without-content)
       get_keys: Comma-separated keys to extract from parsed file content (YAML/JSON).
                Empty string returns full file content (default).
                Example: "channels,conda_build_version" extracts those fields from
                about.json. Requires exactly one file (use 'file' parameter).
                Significantly reduces context by returning only needed fields.
       Returns:
         A dictionary with key=filename, value=content or parsed object.
    """
    try:
        return await asyncio.to_thread(_package_insights, url, file, limit, offset, get_keys)
    except ValueError as ve:
        raise ToolError(f"[validation_error] Invalid input: {ve}") from ve
    except KeyError as ke:
        raise ToolError(f"[not_found_error] File not found: {ke}") from ke
    except Exception as e:
        raise ToolError(f"[unknown_error] 'package_insights' failed: {e}") from e
