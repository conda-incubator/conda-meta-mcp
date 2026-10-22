from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import msgpack
import pytest
from fastmcp.exceptions import ToolError

from conda_meta_mcp import completion


@pytest.fixture
def identity(tmp_path, monkeypatch):
    identity = {
        "conda_version": "26.5.2",
        "conda_completion_version": "0.3.2",
        "python_prefix": str(tmp_path),
        "python_version": "3.14",
        "plugins": [],
    }
    monkeypatch.setattr(completion, "runtime_identity", lambda: identity.copy())
    monkeypatch.setattr(completion, "user_cache_path", lambda *args, **kwargs: tmp_path)
    return identity


def test_manifest_path__runtime_versions_are_part_of_identity(identity):
    path = completion.manifest_path(identity)
    for field in ("conda_version", "conda_completion_version", "python_prefix", "python_version"):
        changed = {**identity, field: "different"}
        assert completion.manifest_path(changed) != path
    assert completion.manifest_path({**identity, "plugins": [{"name": "new-plugin"}]}) != path


def test_runtime_identity__bundled_distribution_versions(monkeypatch):
    def distribution(name, version, entries=()):
        return SimpleNamespace(metadata={"Name": name}, version=version, entry_points=entries)

    plugin = SimpleNamespace(group="conda", name="example", value="example.plugin")
    installed = [
        distribution("conda", "26.5.2"),
        distribution("conda-completion", "0.3.2"),
        distribution("example", "1.0", [plugin]),
    ]
    paths = []

    def distributions(*, path):
        paths.extend(path)
        return installed

    monkeypatch.setattr(completion, "distributions", distributions)
    result = completion.runtime_identity()
    assert result["plugins"] == [
        {"name": "example", "value": "example.plugin", "distribution": "example", "version": "1.0"}
    ]
    installed[2].version = "1.1"
    assert completion.runtime_identity() != result
    assert paths


@pytest.mark.parametrize(
    "manifest, message",
    [
        ([], "root is not a mapping"),
        ({}, "Unsupported CLI manifest version"),
        ({"version": True, "commands": {}}, "Unsupported CLI manifest version"),
        ({"version": 2, "commands": {}}, "Unsupported CLI manifest version"),
        ({"version": 1}, "commands must be a mapping"),
        ({"version": 1, "commands": []}, "commands must be a mapping"),
    ],
)
def test_read_manifest__rejects_incompatible_data(tmp_path, manifest, message):
    path = tmp_path / "completion.msgpack"
    path.write_bytes(msgpack.packb(manifest))
    with pytest.raises(ToolError, match=message):
        completion.read_manifest(path)


def test_read_manifest__corrupt_oversized_and_symlink(tmp_path, monkeypatch):
    path = tmp_path / "completion.msgpack"
    path.write_bytes(b"\xc1")
    with pytest.raises(ToolError, match="Failed to read"):
        completion.read_manifest(path)
    monkeypatch.setattr(completion, "MAX_MSGPACK_FILE_SIZE", 1)
    path.write_bytes(b"ab")
    with pytest.raises(ToolError, match="too large"):
        completion.read_manifest(path)
    link = tmp_path / "link.msgpack"
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip("Symlinks not supported by this test environment")
    with pytest.raises(ToolError, match="non-symlink"):
        completion.read_manifest(link)


def test_prepare_cli__bundled_isolated_generation(identity, monkeypatch):
    calls = []
    monkeypatch.setenv("CONDA_COMPLETION_CACHE_DIR", "/ambient-cache")
    monkeypatch.setenv("CONDA_NO_PLUGINS", "true")

    def run(command, **kwargs):
        calls.append((command, kwargs))
        destination = Path(command[command.index("--cache-dir") + 1])
        (destination / "completion.msgpack").write_bytes(
            msgpack.packb({"version": 1, "commands": {"install": {"summary": "Bundled command."}}})
        )
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(completion.subprocess, "run", run)
    path = completion.prepare_cli()
    assert path == completion.manifest_path(identity)
    assert completion.read_manifest(path)["commands"]["install"]["summary"] == "Bundled command."
    command, kwargs = calls[0]
    assert command[:4] == [sys.executable, "-I", "-S", "-c"]
    assert "reset_context(search_path=())" in command[4]
    assert "from conda_completion.cli.main import build_parser, execute" in command[4]
    assert command[-2:] == ["generate", "--no-repodata"]
    assert "CONDA_COMPLETION_CACHE_DIR" not in kwargs["env"]
    assert "CONDA_NO_PLUGINS" not in kwargs["env"]
    assert "CONDARC" not in kwargs["env"]
    staging = command[command.index("--cache-dir") + 1]
    assert kwargs["cwd"] == staging
    assert kwargs["capture_output"] is True
    assert not Path(staging).exists()


@pytest.mark.parametrize("failure", ["exit", "schema", "timeout"])
def test_prepare_cli__failure_preserves_previous_artifact(identity, monkeypatch, failure):
    path = completion.manifest_path(identity)
    path.parent.mkdir(parents=True)
    previous = msgpack.packb({"version": 1, "commands": {"previous": {}}})
    path.write_bytes(previous)

    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        if failure == "exit":
            return SimpleNamespace(returncode=1, stderr="Generation failed")
        staging = command[command.index("--cache-dir") + 1]
        (Path(staging) / "completion.msgpack").write_bytes(msgpack.packb({"version": 99}))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(completion.subprocess, "run", run)
    with pytest.raises((ToolError, subprocess.TimeoutExpired)):
        completion.prepare_cli()
    assert path.read_bytes() == previous


def test_prepare_cli__runtime_change_rejected(identity, monkeypatch):
    calls = 0

    def runtime_identity():
        nonlocal calls
        calls += 1
        return identity if calls == 1 else {**identity, "conda_version": "changed"}

    def run(command, **kwargs):
        staging = command[command.index("--cache-dir") + 1]
        (Path(staging) / "completion.msgpack").write_bytes(
            msgpack.packb({"version": 1, "commands": {}})
        )
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(completion, "runtime_identity", runtime_identity)
    monkeypatch.setattr(completion.subprocess, "run", run)
    with pytest.raises(ToolError, match="runtime changed"):
        completion.prepare_cli()
    assert not completion.manifest_path(identity).exists()


def test_prepare_cli__real_bundled_producer(tmp_path, monkeypatch):
    from conda_meta_mcp.tools.conda_cli import CompletionManifestReader

    monkeypatch.setattr(completion, "user_cache_path", lambda *args, **kwargs: tmp_path)
    monkeypatch.setenv("CONDA_PREVIEW", "enable")
    monkeypatch.setenv("CONDA_NO_PLUGINS", "true")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "external-python-packages"))
    path = completion.prepare_cli()
    manifest = completion.read_manifest(path)
    assert "install" in manifest["commands"]
    assert "completion" in manifest["commands"]
    assert "repoquery" in manifest["commands"]
    assert not manifest.get("package_names")
    assert not (path.parent / "versions.index").exists()
    result = CompletionManifestReader.from_environment().command("repoquery depends")
    assert result["resolved_command_path"] == ["repoquery", "depends"]
    assert result["runtime"] == completion.runtime_identity()


def test_prepare_cli__unloadable_plugin_fails_closed(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins"
    metadata = plugin_dir / "unloadable_plugin-1.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text("Name: unloadable-plugin\nVersion: 1.0\n")
    (metadata / "entry_points.txt").write_text(
        "[conda]\nunloadable-plugin = module_that_does_not_exist.plugin\n"
    )
    paths = completion._runtime_paths()
    monkeypatch.setattr(completion, "_runtime_paths", lambda: [*paths, str(plugin_dir)])
    monkeypatch.setattr(completion, "user_cache_path", lambda *args, **kwargs: tmp_path / "cache")
    identity = completion.runtime_identity()
    with pytest.raises(ToolError, match="module_that_does_not_exist"):
        completion.prepare_cli()
    assert not completion.manifest_path(identity).exists()
