import argparse

from .mcp_json import setup_mcp_json
from .server import setup_run


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cmm")
    subparser = parser.add_subparsers(help="sub-command help", dest="command")
    subparser.required = True
    setup_run(subparser)
    setup_mcp_json(subparser)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
