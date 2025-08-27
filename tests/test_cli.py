def test_main__run__called(monkeypatch):
    import conda_meta_mcp.server as server
    from conda_meta_mcp import cli

    rec = {}

    def fake(args):
        rec["v"] = args.verbose

    monkeypatch.setattr(server, "run_cmd", fake)
    cli.main(["run", "--verbose"])
    assert rec["v"] is True


def test__mcp_json__called(capsys):
    from conda_meta_mcp import cli

    cli.main(["mcp-json"])
    out = capsys.readouterr().out

    # Basic structure checks
    assert '"command": "pixi"' in out
    assert '"args": [' in out
