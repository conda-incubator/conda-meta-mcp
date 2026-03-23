def test_main__run__called(monkeypatch):
    import conda_meta_mcp.server as server
    from conda_meta_mcp import cli

    rec = {}

    def fake(args):
        rec["v"] = args.verbose
        rec["transport"] = args.transport
        rec["port"] = args.port

    monkeypatch.setattr(server, "run_cmd", fake)
    cli.main(["run", "--verbose"])
    assert rec["v"] is True
    assert rec["transport"] == "stdio"
    assert rec["port"] is None


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


def test__mcp_json__called(capsys):
    from conda_meta_mcp import cli

    cli.main(["mcp-json"])
    out = capsys.readouterr().out

    # Basic structure checks
    assert '"command": "pixi"' in out
    assert '"args": [' in out
