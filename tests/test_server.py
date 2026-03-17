import types

import conda_meta_mcp.server as server


def test_setup_server__called__tools_registered(monkeypatch):
    tools = []

    class FakeFastMCP:
        def __init__(self, name):
            self.name = name

        def tool(self, func, name=None):
            tools.append(name or func.__name__)
            return func

    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)
    m = server.setup_server()

    assert m.name == server.SERVICE_NAME
    assert "info" in tools


def test_run_cmd(monkeypatch):
    calls = {}

    class Dummy:
        def run(self, **kw):
            calls["kw"] = kw

    def fake_setup_server():
        calls["setup_called"] = True
        return Dummy()

    monkeypatch.setattr(server, "setup_server", fake_setup_server)
    monkeypatch.delenv("FASTMCP_LOG_LEVEL", raising=False)
    server.run_cmd(types.SimpleNamespace(verbose=True))
    assert calls["setup_called"]
    assert server.os.environ["FASTMCP_LOG_LEVEL"] == "DEBUG"
    assert calls["kw"] == {"transport": "stdio", "show_banner": False}
