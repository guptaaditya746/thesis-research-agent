"""`gold` command line."""
from __future__ import annotations

import argparse

from . import review_cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gold")
    sub = parser.add_subparsers(dest="command", required=True)
    review_cli.register(sub)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
