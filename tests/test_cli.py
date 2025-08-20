def test_main(monkeypatch):
    import conda_meta_mcp.server as server
    from conda_meta_mcp import cli

    rec = {}

    def fake(args):
        rec["v"] = args.verbose

    monkeypatch.setattr(server, "run_cmd", fake)
    cli.main(["run", "--verbose"])
    assert rec["v"] is True
