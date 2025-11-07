"""
Type definitions for conda-meta-mcp tools.

This module provides TypedDict classes for better type safety and IDE support
across all MCP tools. These are used for return type annotations and runtime
validation.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class PackageRecordDict(TypedDict, total=False):
    """Type definition for a conda package record."""

    version: str
    build_number: str
    build: str
    url: str
    depends: str
    license: NotRequired[str]
    size: NotRequired[int]
    timestamp: NotRequired[int]


class PackageSearchResult(TypedDict):
    """Type definition for package_search results."""

    results: list[PackageRecordDict]
    total: int
    limit: int
    offset: int


class InfoResult(TypedDict):
    """Type definition for info() results."""

    conda_version: str
    libmambapy_version: str
    fastmcp_version: str
    conda_package_streaming_version: str
    conda_meta_mcp_version: str


class ImportMappingResult(TypedDict):
    """Type definition for import_mapping() results."""

    query_import: str
    normalized_import: str
    best_package: str
    candidate_packages: list[str]
    heuristic: str


class PyPiToCondaResult(TypedDict):
    """Type definition for pypi_to_conda() results."""

    pypi_name: str
    conda_name: str
    changed: bool


class QueryMetadata(TypedDict):
    """Metadata about the query itself."""

    subcmd: str
    spec: str
    channel: str
    platform: str
    tree: bool
    offset: int
    limit: int
    installed_included: bool
    total: int


class PackageDetail(TypedDict, total=False):
    """Extended package details from repoquery."""

    build: str
    build_number: int
    name: str
    version: str
    depends: list[str]
    url: str
    license: str
    size: int
    timestamp: int
    md5: NotRequired[str]
    sha256: NotRequired[str]
    platform: NotRequired[str]
    arch: NotRequired[str]
    defaults_mirrors: NotRequired[list[str]]


class RepoQueryInnerResult(TypedDict):
    """Inner result structure from repoquery (contains packages)."""

    query: dict[str, Any]
    result: NotRequired[dict[str, Any]]
    status: str
    offset: int
    limit: int
    total: int
    pkgs: list[PackageDetail]


class RepoQueryResult(TypedDict):
    """Type definition for repoquery() results."""

    query: QueryMetadata
    result: dict[str, Any]


class PackageInsightsResult(TypedDict, total=False):
    """Type definition for package_insights() results.

    Keys are filenames (e.g., "info/about.json", "info/recipe/meta.yaml")
    Values are either raw strings or parsed objects (dict/list) if get_keys was used.
    """

    pass  # Dynamic keys, so we use dict[str, Any] in practice


class CliHelpResult(TypedDict):
    """Type definition for cli_help() results."""

    help_text: str
    total_lines: int
    returned_lines: int
    filtered: bool
