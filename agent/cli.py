"""`agent` command line."""
from __future__ import annotations

import argparse
from pathlib import Path

from .rundir import RunDir


def cmd_check_run(args: argparse.Namespace) -> int:
    problems = RunDir(args.run_dir).validate(complete=args.complete)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print(f"PASS {args.run_dir}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-run", help="validate a run directory's layout and config")
    check.add_argument("run_dir", type=Path)
    check.add_argument("--complete", action="store_true", help="also require answer.json")
    check.set_defaults(func=cmd_check_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
