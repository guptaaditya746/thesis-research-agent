"""`gold` command line."""
from __future__ import annotations

import argparse

from gold import build_cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gold")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_cli.register(subparsers)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
