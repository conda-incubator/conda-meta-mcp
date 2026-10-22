"""Prepare and locate CLI manifests for this MCP's bundled runtime."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import sysconfig
import tempfile
from importlib.metadata import PackageNotFoundError, distributions
from pathlib import Path
from typing import Any

import msgpack
from fastmcp.exceptions import ToolError
from platformdirs import user_cache_path

MAX_MSGPACK_FILE_SIZE = 50 * 1024 * 1024
MAX_COLLECTION_SIZE = 2_000_000
SUPPORTED_MANIFEST_VERSION = 1

# Skip site initialization (.pth/user hooks), then use the producer's CLI dispatcher
# with Conda's documented empty-search-path configuration. No parser-tree access here.
PREPARE_CLI_SCRIPT = """
import json
import sys
sys.path.extend(json.loads(sys.argv[1]))
sys.prefix = sys.exec_prefix = sys.argv[2]
from conda.base.context import reset_context
reset_context(search_path=())
from importlib.metadata import entry_points
for entry in entry_points(group="conda"):
    entry.load()
from conda_completion.cli.main import build_parser, execute
raise SystemExit(execute(build_parser().parse_args(sys.argv[3:])))
"""


def _runtime_paths() -> list[str]:
    return sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})


def runtime_identity() -> dict[str, Any]:
    """Identify packages visible to the isolated bundled Python interpreter."""
    installed = list(distributions(path=_runtime_paths()))
    versions = {
        dist.metadata["Name"].lower().replace("_", "-"): dist.version for dist in installed
    }
    for name in ("conda", "conda-completion"):
        if name not in versions:
            raise PackageNotFoundError(name)
    plugins = sorted(
        (
            {
                "name": entry.name,
                "value": entry.value,
                "distribution": dist.metadata["Name"],
                "version": dist.version,
            }
            for dist in installed
            for entry in dist.entry_points
            if entry.group == "conda"
        ),
        key=lambda plugin: (plugin["name"], plugin["distribution"], plugin["value"]),
    )
    return {
        "generation_profile": "bundled-defaults-v1",
        "conda_version": versions["conda"],
        "conda_completion_version": versions["conda-completion"],
        "python_prefix": sys.prefix,
        "python_version": sys.version,
        "plugins": plugins,
    }


def manifest_path(identity: dict[str, Any]) -> Path:
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return (
        user_cache_path("conda-meta-mcp", appauthor=False)
        / "cli"
        / fingerprint
        / "completion.msgpack"
    )


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            if not path.exists():
                raise FileNotFoundError(path)
            raise ToolError("[cache_error] completion.msgpack must be a regular, non-symlink file")
        size = path.stat().st_size
        if size > MAX_MSGPACK_FILE_SIZE:
            raise ToolError(f"[cache_error] completion.msgpack is too large ({size} bytes)")
        with path.open("rb") as file:
            data = file.read(MAX_MSGPACK_FILE_SIZE + 1)
        if len(data) > MAX_MSGPACK_FILE_SIZE:
            raise ToolError("[cache_error] completion.msgpack exceeds the size limit")
        manifest = msgpack.unpackb(
            data,
            max_str_len=MAX_MSGPACK_FILE_SIZE,
            max_bin_len=MAX_MSGPACK_FILE_SIZE,
            max_array_len=MAX_COLLECTION_SIZE,
            max_map_len=MAX_COLLECTION_SIZE,
        )
    except FileNotFoundError as exc:
        raise ToolError(
            "[not_found] No CLI manifest for the bundled runtime; restart the MCP server "
            "or run 'cmm prepare-cli' in this MCP environment."
        ) from exc
    except (OSError, msgpack.UnpackException, ValueError) as exc:
        raise ToolError(f"[cache_error] Failed to read completion.msgpack: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ToolError("[cache_error] completion.msgpack root is not a mapping")
    version = manifest.get("version")
    if type(version) is not int or version != SUPPORTED_MANIFEST_VERSION:
        raise ToolError(
            f"[cache_error] Unsupported CLI manifest version: {manifest.get('version')!r}; "
            f"expected {SUPPORTED_MANIFEST_VERSION}"
        )
    if not isinstance(manifest.get("commands"), dict):
        raise ToolError("[cache_error] completion.msgpack commands must be a mapping")
    return manifest


def prepare_cli() -> Path:
    """Generate a command-only manifest at startup or explicitly, outside tool calls."""
    identity = runtime_identity()
    path = manifest_path(identity)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ToolError("[cache_error] Refusing to replace a symlink CLI manifest")
    with tempfile.TemporaryDirectory(dir=path.parent) as staging:
        env = os.environ.copy()
        for name in list(env):
            if name.startswith("CONDA_") or name == "CONDARC":
                del env[name]
        command = [
            sys.executable,
            "-I",
            "-S",
            "-c",
            PREPARE_CLI_SCRIPT,
            json.dumps(_runtime_paths()),
            sys.prefix,
            "--cache-dir",
            staging,
            "generate",
            "--no-repodata",
        ]
        # Fixed script/arguments and this interpreter only; no shell or caller-supplied command.
        result = subprocess.run(  # noqa: S603
            command,
            env=env,
            cwd=staging,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode:
            raise ToolError(
                f"[setup_error] CLI manifest generation failed: {result.stderr.strip()}"
            )
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        generated = Path(staging) / "completion.msgpack"
        read_manifest(generated)
        if runtime_identity() != identity:
            raise ToolError(
                "[setup_error] Bundled runtime changed during manifest generation; retry"
            )
        generated.replace(path)
    return path


def setup_prepare_cli(subparser) -> None:
    parser = subparser.add_parser(
        "prepare-cli", help="Generate CLI metadata from bundled conda and plugins (no repodata)"
    )
    parser.set_defaults(func=prepare_cli_cmd)


def prepare_cli_cmd(args) -> None:
    print(prepare_cli())
