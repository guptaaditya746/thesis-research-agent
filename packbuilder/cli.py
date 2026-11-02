"""`packbuilder` command line.

    packbuilder serve --corpus DIR    the corpus tool server (server.py) over stdio, for an MCP client
"""
from __future__ import annotations

import argparse
from pathlib import Path

from packbuilder.server import create_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="packbuilder")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="serve a corpus's tools over MCP stdio")
    serve.add_argument("--corpus", type=Path, required=True, help="corpus directory (manifest.json and papers/)")
    args = parser.parse_args(argv)
    if args.command == "serve":
        create_server(args.corpus).run(transport="stdio")


if __name__ == "__main__":
    main()
