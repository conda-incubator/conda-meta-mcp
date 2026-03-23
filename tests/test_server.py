import types

import conda_meta_mcp.server as server


def test_setup_server__called__tools_registered(monkeypatch):
    tools = []
    instances = []

    class FakeFastMCP:
        def __init__(self, name, transforms=None):
            self.name = name
            self.transforms = transforms
            instances.append(self)

        def tool(self, func, name=None):
            tools.append(name or func.__name__)
            return func

    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)
    m = server.setup_server()

    assert m.name == server.SERVICE_NAME
    assert m.transforms is None
    assert "info" in tools


def test_setup_server__code_mode_enabled(monkeypatch):
    sentinel = object()

    class FakeFastMCP:
        def __init__(self, name, transforms=None):
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
