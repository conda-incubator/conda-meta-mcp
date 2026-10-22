from __future__ import annotations

import msgpack
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conda_meta_mcp import completion


@pytest.fixture(autouse=True)
def private_cli_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(completion, "user_cache_path", lambda *args, **kwargs: tmp_path)


def write_completion_cache(tmp_path):
    manifest = {
        "version": 1,
        "generated_at": "2026-06-14T12:00:00+00:00",
        "plugin_hash": "abc123",
        "root_options": {
            "--json": {
                "description": "Report all output as json.",
                "nargs": "0",
            }
        },
        "commands": {
            "env": {
                "summary": "Manage conda environments.",
                "subcommands": {
                    "list": {
                        "summary": "List conda environments.",
                        "options": {
                            "--name": {
                                "short": "-n",
                                "completion_type": "env_name",
                            }
                        },
                        "positionals": [],
                        "subcommands": {},
                    }
                },
            },
            "install": {
                "summary": "Install packages.",
                "options": {
                    "--channel": {
                        "short": "-c",
                        "completion_type": "channel",
                    }
                },
                "positionals": [
                    {
                        "name": "packages",
                        "completion_type": "package_spec",
                        "nargs": "*",
                    }
                ],
                "subcommands": {},
            },
        },
        "aliases": {
            "i": {
                "target": ["install"],
            }
        },
        "package_names": ["numpy", "numpy-base", "pandas", "python-numpy"],
    }
    path = completion.manifest_path(completion.runtime_identity())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msgpack.packb(manifest))


@pytest.mark.asyncio
async def test_conda_cli_command__root_metadata(server, tmp_path, monkeypatch):
    write_completion_cache(tmp_path)
    monkeypatch.setenv("CONDA_COMPLETION_CACHE_DIR", str(tmp_path / "ambient-cache"))

    async with Client(server) as client:
        result = await client.call_tool("conda_cli_command", {})

    assert result.data["command_path"] == []
    assert result.data["resolved_command_path"] == []
    assert result.data["manifest"]["version"] == 1
    assert result.data["runtime"] == completion.runtime_identity()
    assert result.data["options"] == [
        {
            "name": "--json",
            "description": "Report all output as json.",
            "nargs": "0",
        }
    ]
    assert result.data["subcommands"] == [
        {"name": "env", "summary": "Manage conda environments."},
        {"name": "install", "summary": "Install packages."},
    ]


@pytest.mark.asyncio
async def test_conda_cli_command__nested_command(server, tmp_path, monkeypatch):
    write_completion_cache(tmp_path)
    monkeypatch.setenv("CONDA_COMPLETION_CACHE_DIR", str(tmp_path))

    async with Client(server) as client:
        result = await client.call_tool(
            "conda_cli_command",
            {
                "command_path": "conda env list",
                "include_subcommands": False,
            },
        )

    assert result.data["command_path"] == ["env", "list"]
    assert result.data["resolved_command_path"] == ["env", "list"]
    assert result.data["summary"] == "List conda environments."
    assert result.data["options"] == [
        {
            "name": "--name",
            "short": "-n",
            "completion_type": "env_name",
        }
    ]
    assert "subcommands" not in result.data


@pytest.mark.asyncio
async def test_conda_cli_command__resolves_alias(server, tmp_path, monkeypatch):
    write_completion_cache(tmp_path)
    monkeypatch.setenv("CONDA_COMPLETION_CACHE_DIR", str(tmp_path))

    async with Client(server) as client:
        result = await client.call_tool("conda_cli_command", {"command_path": "i"})

    assert result.data["command_path"] == ["i"]
    assert result.data["resolved_command_path"] == ["install"]
    assert result.data["alias_target"] == ["install"]
    assert result.data["summary"] == "Install packages."


@pytest.mark.asyncio
async def test_conda_cli_command__unknown_command_error(server, tmp_path, monkeypatch):
    write_completion_cache(tmp_path)
    monkeypatch.setenv("CONDA_COMPLETION_CACHE_DIR", str(tmp_path))

    with pytest.raises(ToolError, match="Unknown conda command path"):
        async with Client(server) as client:
            await client.call_tool("conda_cli_command", {"command_path": "does-not-exist"})


@pytest.mark.asyncio
async def test_conda_cli_command__missing_completion_cache_error(server, tmp_path, monkeypatch):
    monkeypatch.setenv("CONDA_COMPLETION_CACHE_DIR", str(tmp_path))

    with pytest.raises(ToolError, match="cmm prepare-cli"):
        async with Client(server) as client:
            await client.call_tool("conda_cli_command", {})


@pytest.mark.asyncio
async def test_conda_cli_command__ambient_cache_is_not_used(server, tmp_path, monkeypatch):
    (tmp_path / "completion.msgpack").write_bytes(
        msgpack.packb({"version": 1, "commands": {"ambient": {"summary": "Wrong runtime."}}})
    )
    monkeypatch.setenv("CONDA_COMPLETION_CACHE_DIR", str(tmp_path))
    with pytest.raises(ToolError, match="cmm prepare-cli"):
        async with Client(server) as client:
            await client.call_tool("conda_cli_command", {})


@pytest.mark.asyncio
async def test_conda_cli_command__changed_runtime(server, tmp_path, monkeypatch):
    write_completion_cache(tmp_path)
    identity = completion.runtime_identity()
    identity["conda_version"] = "future-version"
    monkeypatch.setattr("conda_meta_mcp.tools.conda_cli.runtime_identity", lambda: identity)
    with pytest.raises(ToolError, match="cmm prepare-cli"):
        async with Client(server) as client:
            await client.call_tool("conda_cli_command", {})


@pytest.mark.asyncio
async def test_conda_cli_command__calls_do_not_generate(server, tmp_path, monkeypatch):
    write_completion_cache(tmp_path)
    monkeypatch.setattr(completion, "prepare_cli", lambda: pytest.fail("Tool must not generate"))
    monkeypatch.setattr(
        completion.subprocess, "run", lambda *a, **kw: pytest.fail("No subprocess")
    )
    async with Client(server) as client:
        result = await client.call_tool("conda_cli_command", {"command_path": "install"})
    assert result.data["summary"] == "Install packages."


@pytest.mark.asyncio
@pytest.mark.parametrize("command_path", ['"unclosed', "install --json"])
async def test_conda_cli_command__invalid_path(server, tmp_path, command_path):
    write_completion_cache(tmp_path)
    with pytest.raises(ToolError, match=r"\[validation_error\]"):
        async with Client(server) as client:
            await client.call_tool("conda_cli_command", {"command_path": command_path})
