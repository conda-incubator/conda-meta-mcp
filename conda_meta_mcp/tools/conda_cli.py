from __future__ import annotations

import asyncio
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import msgpack
from fastmcp.exceptions import ToolError

from .registry import register_tool

MAX_MSGPACK_FILE_SIZE = 50 * 1024 * 1024
MAX_COLLECTION_SIZE = 2_000_000


@dataclass(frozen=True)
class CompletionManifestReader:
    cache_dir: Path

    @classmethod
    def from_environment(cls) -> Self:
        override = os.environ.get("CONDA_COMPLETION_CACHE_DIR")
        if override:
            return cls(Path(os.path.expandvars(override)).expanduser().resolve())
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA")
            if base:
                return cls(Path(base) / "conda" / "cache" / "completion")
            return cls(Path.home() / "AppData" / "Local" / "conda" / "cache" / "completion")
        if sys.platform == "darwin":
            return cls(Path.home() / "Library" / "Caches" / "conda" / "completion")
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        return cls(base / "conda" / "completion")

    def read_manifest(self) -> tuple[Path, dict[str, Any]]:
        path = self.cache_dir / "completion.msgpack"
        try:
            if path.is_symlink():
                raise ToolError(f"[cache_error] Refusing to read symlink: {path.name}")
            size = path.stat().st_size
            if size > MAX_MSGPACK_FILE_SIZE:
                raise ToolError(f"[cache_error] {path.name} is too large ({size} bytes)")
            manifest = msgpack.unpackb(
                path.read_bytes(),
                max_str_len=MAX_MSGPACK_FILE_SIZE,
                max_bin_len=MAX_MSGPACK_FILE_SIZE,
                max_array_len=MAX_COLLECTION_SIZE,
                max_map_len=MAX_COLLECTION_SIZE,
            )
        except FileNotFoundError as exc:
            raise ToolError(
                "[not_found] completion.msgpack not found; run 'conda completion generate' first."
            ) from exc
        except (msgpack.UnpackException, ValueError) as exc:
            raise ToolError(f"[cache_error] Failed to decode {path.name}: {exc}") from exc
        if not isinstance(manifest, dict):
            raise ToolError("[cache_error] completion.msgpack root is not a mapping")
        return path, manifest

    def mapping(self, value: Any, field: str) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ToolError(f"[cache_error] completion.msgpack field is not a mapping: {field}")
        return value

    def resolve_command(
        self,
        manifest: dict[str, Any],
        command_path: str,
    ) -> tuple[list[str], list[str], list[str] | None, dict[str, Any]]:
        try:
            requested = shlex.split(command_path)
        except ValueError as exc:
            raise ToolError(f"[validation_error] Invalid command_path: {exc}") from exc
        if requested and requested[0] == "conda":
            requested = requested[1:]
        if any(part.startswith("-") for part in requested):
            raise ToolError("[validation_error] command_path must contain commands, not options")

        resolved = list(requested)
        alias_target = None
        aliases = self.mapping(manifest.get("aliases"), "aliases")
        if resolved:
            alias = aliases.get(resolved[0])
            if isinstance(alias, dict) and isinstance(alias.get("target"), list):
                alias_target = [str(item) for item in alias["target"] if str(item)]
                resolved = [*alias_target, *resolved[1:]]

        commands = self.mapping(manifest.get("commands"), "commands")
        command: dict[str, Any] = {
            "summary": None,
            "options": self.mapping(manifest.get("root_options"), "root_options"),
            "positionals": [],
            "subcommands": commands,
            "exclusive_groups": [],
        }
        next_commands = commands
        visited: list[str] = []
        for part in resolved:
            next_command = next_commands.get(part)
            if not isinstance(next_command, dict):
                available = ", ".join(sorted(next_commands)[:20])
                detail = f" Available subcommands: {available}" if available else ""
                raise ToolError(
                    f"[not_found] Unknown conda command path: "
                    f"{' '.join([*visited, part])}.{detail}"
                )
            visited.append(part)
            command = next_command
            next_commands = self.mapping(command.get("subcommands"), "subcommands")
        return requested, resolved, alias_target, command

    def command(
        self,
        command_path: str = "",
        include_options: bool = True,
        include_positionals: bool = True,
        include_subcommands: bool = True,
    ) -> dict[str, Any]:
        manifest_path, manifest = self.read_manifest()
        requested, resolved, alias_target, command = self.resolve_command(manifest, command_path)

        result: dict[str, Any] = {
            "command_path": requested,
            "resolved_command_path": resolved,
            "alias_target": alias_target,
            "summary": command.get("summary"),
            "manifest": {
                "path": str(manifest_path),
                "version": manifest.get("version"),
                "generated_at": manifest.get("generated_at"),
                "plugin_hash": manifest.get("plugin_hash"),
            },
        }
        if include_options:
            result["options"] = [
                {"name": name, **value}
                if isinstance(value, dict)
                else {"name": name, "value": value}
                for name, value in sorted(self.mapping(command.get("options"), "options").items())
            ]
        if include_positionals:
            positionals = command.get("positionals") or []
            if not isinstance(positionals, list):
                raise ToolError(
                    "[cache_error] completion.msgpack field is not a list: positionals"
                )
            result["positionals"] = [item for item in positionals if isinstance(item, dict)]
        if include_subcommands:
            result["subcommands"] = [
                {
                    "name": name,
                    "summary": value.get("summary") if isinstance(value, dict) else None,
                }
                for name, value in sorted(
                    self.mapping(command.get("subcommands"), "subcommands").items()
                )
            ]
        exclusive_groups = command.get("exclusive_groups")
        if isinstance(exclusive_groups, list) and exclusive_groups:
            result["exclusive_groups"] = exclusive_groups
        return result


@register_tool
async def conda_cli_command(
    command_path: str = "",
    include_options: bool = True,
    include_positionals: bool = True,
    include_subcommands: bool = True,
) -> dict[str, Any]:
    """
    Read conda-completion's completion.msgpack and return structured conda CLI metadata.

    Args:
      command_path: Space-separated conda command path, e.g. "", "install", "env list",
        or "conda install". Empty string returns root command metadata.
      include_options: Include command options and flag metadata.
      include_positionals: Include positional argument metadata.
      include_subcommands: Include direct child subcommands.

    Returns:
      A dictionary with the resolved command path, summary, selected metadata sections,
      and completion.msgpack metadata.
    """
    try:
        reader = CompletionManifestReader.from_environment()
        return await asyncio.to_thread(
            reader.command,
            command_path,
            include_options,
            include_positionals,
            include_subcommands,
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"[unknown_error] 'conda_cli_command' failed: {e}") from e
