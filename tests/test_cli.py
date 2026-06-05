def test_main__run__called(monkeypatch):
    import conda_meta_mcp.server as server
    from conda_meta_mcp import cli

    rec = {}

    def fake(args):
        rec["v"] = args.verbose
        rec["transport"] = args.transport
        rec["port"] = args.port
        rec["parent_watcher"] = args.parent_watcher

    monkeypatch.setattr(server, "run_cmd", fake)
    cli.main(["run", "--verbose", "--no-parent-watcher"])
    assert rec["v"] is True
    assert rec["transport"] == "stdio"
    assert rec["port"] is None
    assert rec["parent_watcher"] is False


def test_main__run__transport_and_port(monkeypatch):
    import conda_meta_mcp.server as server
    from conda_meta_mcp import cli

    rec = {}

    def fake(args):
        rec["transport"] = args.transport
        rec["port"] = args.port

    monkeypatch.setattr(server, "run_cmd", fake)
    cli.main(["run", "--transport", "streamable-http", "--port", "4042"])
    assert rec["transport"] == "streamable-http"
    assert rec["port"] == 4042


def test_main__run__parent_watcher_defaults_to_enabled(monkeypatch):
    import conda_meta_mcp.server as server
    from conda_meta_mcp import cli

    rec = {}

    def fake(args):
        rec["parent_watcher"] = args.parent_watcher

    monkeypatch.setattr(server, "run_cmd", fake)
    cli.main(["run"])

    assert rec["parent_watcher"] is True


def test_main__run__parent_watcher_uses_env_fallback(monkeypatch):
    import conda_meta_mcp.server as server
    from conda_meta_mcp import cli

    rec = {}

    def fake(args):
        rec["parent_watcher"] = args.parent_watcher

    monkeypatch.setenv("CONDA_META_MCP_PARENT_WATCHDOG", "0")
    monkeypatch.setattr(server, "run_cmd", fake)
    cli.main(["run"])

    assert rec["parent_watcher"] is False


def test__mcp_json__called(capsys):
    from conda_meta_mcp import cli

    cli.main(["mcp-json"])
    out = capsys.readouterr().out

    # Basic structure checks
    assert '"command": "pixi"' in out
    assert '"args": [' in out
