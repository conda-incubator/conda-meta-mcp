import argparse
import json
import os
import sys
from pathlib import Path


def setup_mcp_json(subparser: argparse._SubParsersAction):
    run_parser = subparser.add_parser(
        "mcp-json", help="Generate MCP configuration JSON for manual installation"
    )
    run_parser.set_defaults(func=run_mcp_json)


def run_mcp_json(args):
    manifest = os.getenv("PIXI_PROJECT_MANIFEST")
    manifest_path = Path(manifest) if manifest else None
    cmm_path = Path(sys.argv[0])
    command = ""
    args = []
    if manifest_path and manifest_path.exists():
        command = "pixi"
        args = ["run", "--manifest-path", str(manifest_path), "cmm", "run"]
    elif cmm_path and cmm_path.exists() and cmm_path.name.endswith("cmm"):
        command = str(cmm_path)
        args = ["run"]
    config = {
        "conda-meta-mcp": {
            "command": command,
            "args": args,
            "env": {},
        }
    }
    print(json.dumps(config, indent=2))
