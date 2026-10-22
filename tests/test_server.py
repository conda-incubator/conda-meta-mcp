import types

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conda_meta_mcp import server


def test_setup_server__called__tools_registered(monkeypatch):
    tools = []
    instances = []

    class FakeFastMCP:
        def __init__(self, name, transforms=None, lifespan=None):
            self.name = name
            self.transforms = transforms
            self.lifespan = lifespan
            instances.append(self)

        def tool(self, func, name=None):
            tools.append(name or func.__name__)
            return func

    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)
    monkeypatch.setattr(
        server, "prepare_cli", lambda: pytest.fail("Construction must not prepare")
    )
    m = server.setup_server()

    assert m.name == server.SERVICE_NAME
    assert m.transforms is None
    assert "info" in tools
    assert "conda_cli_command" in tools
    assert "cli_help" not in tools
    assert m.lifespan is server._lifespan


def test_setup_server__code_mode_enabled(monkeypatch):
    sentinel = object()

    class FakeFastMCP:
        def __init__(self, name, transforms=None, lifespan=None):
            self.name = name
            self.transforms = transforms

        def tool(self, func, name=None):
            return func

    monkeypatch.setattr(server, "_build_code_mode_transform", lambda: sentinel)
    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)
    m = server.setup_server(code=True)

    assert m.name == server.SERVICE_NAME
    assert m.transforms == [sentinel]


def test_build_code_mode_transform__configured(monkeypatch):
    class FakeListTools:
        pass

    class FakeGetSchemas:
        pass

    class FakeMontySandboxProvider:
        def __init__(self, limits):
            self.limits = limits

    class FakeCodeMode:
        def __init__(self, discovery_tools, sandbox_provider):
            self.discovery_tools = discovery_tools
            self.sandbox_provider = sandbox_provider

    fake_module = types.SimpleNamespace(
        CodeMode=FakeCodeMode,
        GetSchemas=FakeGetSchemas,
        ListTools=FakeListTools,
        MontySandboxProvider=FakeMontySandboxProvider,
    )

    monkeypatch.setattr(server.importlib, "import_module", lambda name: fake_module)

    transform = server._build_code_mode_transform()

    assert isinstance(transform, FakeCodeMode)
    assert len(transform.discovery_tools) == 2
    assert isinstance(transform.discovery_tools[0], FakeListTools)
    assert isinstance(transform.discovery_tools[1], FakeGetSchemas)
    assert transform.sandbox_provider.limits == {
        "max_duration_secs": 30,
        "max_memory": 2_000_000_000,
    }


def test_run_cmd__starts_parent_watcher_before_setup(monkeypatch):
    calls = {}
    order = []

    class Dummy:
        def run(self, **kw):
            calls["kw"] = kw

    def fake_start_watcher():
        order.append("watcher")

    def fake_setup_server(code=False):
        order.append("setup")
        return Dummy()

    monkeypatch.setattr(server, "setup_server", fake_setup_server)
    monkeypatch.setattr(server, "start_parent_watcher", fake_start_watcher)

    server.run_cmd(
        types.SimpleNamespace(
            verbose=False,
            code=False,
            transport="streamable-http",
            port=4042,
        )
    )

    assert order == ["watcher", "setup"]
    assert calls["kw"] == {
        "transport": "streamable-http",
        "show_banner": False,
        "port": 4042,
    }


@pytest.mark.asyncio
async def test_server__prepares_on_every_startup(monkeypatch):
    prepared = []
    monkeypatch.setattr(server, "prepare_cli", lambda: prepared.append("prepared"))
    instance = server.setup_server()
    assert prepared == []
    for _ in range(2):
        async with Client(instance) as client:
            tools = await client.list_tools()
            assert "conda_cli_command" in {tool.name for tool in tools}
            assert "cli_help" not in {tool.name for tool in tools}
    assert prepared == ["prepared", "prepared"]


@pytest.mark.asyncio
async def test_server__preparation_failure_prevents_startup(monkeypatch):
    def fail():
        raise ToolError("CLI manifest generation failed")

    monkeypatch.setattr(server, "prepare_cli", fail)
    with pytest.raises(RuntimeError, match="CLI manifest generation failed"):
        async with Client(server.setup_server()):
            pytest.fail("Server must not start after failed preparation")


@pytest.mark.asyncio
async def test_server__real_startup_prepares_bundled_manifest(tmp_path, monkeypatch):
    from conda_meta_mcp import completion

    monkeypatch.setattr(completion, "user_cache_path", lambda *args, **kwargs: tmp_path)
    path = completion.manifest_path(completion.runtime_identity())
    assert not path.exists()
    async with Client(server.setup_server()) as client:
        result = await client.call_tool("conda_cli_command", {"command_path": "repoquery depends"})
        assert path.is_file()
        assert result.data["resolved_command_path"] == ["repoquery", "depends"]
        assert result.data["runtime"] == completion.runtime_identity()
        root = await client.call_tool("conda_cli_command", {})
        commands = {command["name"] for command in root.data["subcommands"]}
        assert {"workspace", "ws", "task"} <= commands
        plugins = {plugin["distribution"] for plugin in root.data["runtime"]["plugins"]}
        assert {"conda-workspaces", "conda-lockfiles"} <= plugins
        lock = await client.call_tool("conda_cli_command", {"command_path": "workspace lock"})
        assert {"--platform", "--output", "--merge"} <= {
            option["name"] for option in lock.data["options"]
        }
        install = await client.call_tool(
            "conda_cli_command", {"command_path": "workspace install"}
        )
        assert {"--locked", "--frozen"} <= {option["name"] for option in install.data["options"]}
        export = await client.call_tool("conda_cli_command", {"command_path": "workspace export"})
        options = {option["name"]: option for option in export.data["options"]}
        assert "--from-lockfile" in options
        assert "conda-workspaces-lock-v1" in options["--format"]["choices"]
        task = await client.call_tool("conda_cli_command", {"command_path": "task run"})
        assert "task_name" in {argument["name"] for argument in task.data["positionals"]}


def test_run_cmd__skips_parent_watcher_when_disabled(monkeypatch):
    calls = {}

    class Dummy:
        def run(self, **kw):
            calls["kw"] = kw

    monkeypatch.setattr(server, "setup_server", lambda code=False: Dummy())
    monkeypatch.setattr(
        server,
        "start_parent_watcher",
        lambda: calls.setdefault("watcher", True),
    )

    server.run_cmd(
        types.SimpleNamespace(
            verbose=False,
            code=False,
            transport="stdio",
            port=None,
            parent_watcher=False,
        )
    )

    assert "watcher" not in calls
    assert calls["kw"] == {"transport": "stdio", "show_banner": False}


def test_run_cmd(monkeypatch):
    calls = {}

    class Dummy:
        def run(self, **kw):
            calls["kw"] = kw

    def fake_setup_server(code=False):
        calls["setup_called"] = True
        calls["code"] = code
        return Dummy()

    monkeypatch.setattr(server, "setup_server", fake_setup_server)
    monkeypatch.setattr(server, "start_parent_watcher", lambda: None)
    monkeypatch.delenv("FASTMCP_LOG_LEVEL", raising=False)
    server.run_cmd(types.SimpleNamespace(verbose=True, code=False, transport="stdio", port=None))
    assert calls["setup_called"]
    assert calls["code"] is False
    assert server.os.environ["FASTMCP_LOG_LEVEL"] == "DEBUG"
    assert calls["kw"] == {"transport": "stdio", "show_banner": False}


def test_run_cmd__streamable_http_with_port(monkeypatch):
    calls = {}

    class Dummy:
        def run(self, **kw):
            calls["kw"] = kw

    monkeypatch.setattr(server, "setup_server", lambda code=False: Dummy())
    monkeypatch.setattr(server, "start_parent_watcher", lambda: None)
    server.run_cmd(
        types.SimpleNamespace(
            verbose=False,
            code=False,
            transport="streamable-http",
            port=4042,
        )
    )

    assert calls["kw"] == {
        "transport": "streamable-http",
        "show_banner": False,
        "port": 4042,
    }
