"""`agent` command line."""
from __future__ import annotations

import argparse
from pathlib import Path

from .chain import verify
from .rundir import RunDir


def cmd_check_run(args: argparse.Namespace) -> int:
    problems = RunDir(args.run_dir).validate(complete=args.complete)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print(f"PASS {args.run_dir}")
    return 1 if problems else 0


def cmd_verify_chain(args: argparse.Namespace) -> int:
    run = RunDir(args.run_dir)
    report = verify(run.events, run.claims, head=args.head)
    for error in report.errors:
        print(f"FAIL {error}")
    if report.ok:
        print(f"PASS records={report.records} claims={report.claims} head={report.head}")
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent")
    sub = parser.add_subparsers(dest="command", required=True)
    chain = sub.add_parser("verify-chain", help="verify the hash chain of events.jsonl and claims.jsonl")
    chain.add_argument("run_dir", type=Path)
    chain.add_argument("--head", help="expected chain head, e.g. from the broker's line in the Slurm log")
    chain.set_defaults(func=cmd_verify_chain)
    check = sub.add_parser("check-run", help="validate a run directory's layout and config")
    check.add_argument("run_dir", type=Path)
    check.add_argument("--complete", action="store_true", help="also require answer.json")
    check.set_defaults(func=cmd_check_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
