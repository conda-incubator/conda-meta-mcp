import types

import conda_meta_mcp.server as server


def test_setup_server__called__tools_registered(monkeypatch):
    tools = []

    class FakeFastMCP:
        def __init__(self, name, log_level=None):
            self.name = name
            self.log_level = log_level

        def tool(self, func):
            tools.append(func.__name__)
            return func

    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)
    m = server.setup_server(log_level="INFO")

    assert m.name == server.SERVICE_NAME
    assert m.log_level == "INFO"  # type: ignore[attr-defined]
    assert "info" in tools


def test_run_cmd(monkeypatch):
    calls = {}

    class Dummy:
        def run(self, **kw):
            calls["kw"] = kw

    def fake_setup_server(log_level=None):
        calls["level"] = log_level
        return Dummy()

    monkeypatch.setattr(server, "setup_server", fake_setup_server)
    server.run_cmd(types.SimpleNamespace(verbose=True))
    assert calls["level"] == "DEBUG"
    assert calls["kw"] == {"transport": "stdio", "show_banner": False}
