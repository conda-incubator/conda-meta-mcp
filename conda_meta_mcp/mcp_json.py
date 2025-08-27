import argparse
import json
from pathlib import Path

from .server import SERVICE_NAME


def setup_mcp_json(subparser: argparse._SubParsersAction):
    run_parser = subparser.add_parser(
        "mcp-json", help="Generate MCP configuration JSON for manual installation"
    )
    run_parser.set_defaults(func=run_mcp_json)


def run_mcp_json(args):
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    config = {
        SERVICE_NAME: {
            "command": "pixi",
            "args": ["run", "--manifest-path", str(pyproject_path), "cmm", "run"],
            "env": {},
        }
    }
    print(json.dumps(config, indent=2))
