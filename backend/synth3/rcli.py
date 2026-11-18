"""`synth3` replay commands: `reexec` re-runs one folder's system runs with no cache and reports."""
from __future__ import annotations

import argparse
from pathlib import Path

from evidence.stability import render
from synth3.cliargs import BadArgument, _ascii, _spec
from synth3.qcli import _questions
from synth3.questions import QUESTIONS
from synth3.remeasure import commit_note, measure_folder, question_line
from synth3.sheets import RESULTS
from synth3.spec import SPECS


def reexec(args: argparse.Namespace) -> int:
    spec = _spec(args)
    known = [q.id for q in _questions(args, spec).questions]
    qids = [x.strip() for x in args.questions.split(",") if x.strip()] if args.questions else known
    unknown = [x for x in qids if x not in known]
    if unknown:
        raise BadArgument(f"unknown question id: {', '.join(unknown)}")
    if args.times < 1:
        raise BadArgument("--times must be at least 1")
    report = measure_folder(args.results, args.domain, args.seed, qids, times=args.times)
    print("\n".join(render(report["total"])))
    note = commit_note(report)
    if note:
        print(note)
    for qid, one in report["questions"].items():
        print(question_line(qid, one))
    for qid, why in report["skipped"].items():
        print(f"  skipped {qid}: {_ascii(why)}")
    for qid, why in report["failed"].items():
        print(f"  failed {qid}: {_ascii(why)}")
    return 1 if report["failed"] else 0


def add_replay_commands(sub) -> None:
    p = sub.add_parser("reexec", help="re-run one folder's system runs N times with no cache and measure them")
    p.add_argument("--domain", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--times", type=int, default=5)
    p.add_argument("--questions", default="", help="comma-separated question ids; default: every question")
    p.add_argument("--questions-root", type=Path, default=QUESTIONS)
    p.add_argument("--spec-root", type=Path, default=SPECS)
    p.add_argument("--results", type=Path, default=RESULTS)
    p.set_defaults(run=reexec)
