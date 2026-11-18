"""`synth3` commands for the system under test: `system-plan` drafts one plan per question."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from synth3 import system
from synth3.cliargs import BadArgument, _ascii, _spec
from synth3.qcli import _questions
from synth3.questions import QUESTIONS
from synth3.sheets import RESULTS
from synth3.spec import SPECS


def system_plan(args: argparse.Namespace) -> int:
    spec = _spec(args)
    qs = _questions(args, spec)
    redo = {x.strip() for x in (args.redo or "").split(",") if x.strip()}
    unknown = sorted(redo - {q.id for q in qs.questions})
    if unknown:
        raise BadArgument(f"--redo names questions that are not in the file: {', '.join(unknown)}")
    base = args.results / args.domain
    lm = system.orch_lm(base / system.PLANNER_CACHE)
    redo_lm = None
    if redo:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        redo_lm = system.orch_lm(base / f"planner-redo-{stamp}.jsonl")
    out = system.plan_domain(args.domain, qs, args.plans, lm, system.saved_templates(), redo=redo, redo_lm=redo_lm)
    print(f"drafted {len(out['drafted'])}, kept {len(out['kept'])}, rekinded {len(out['rekinded'])}, "
          f"failed {len(out['failed'])}")
    for qid, why in out["failed"].items():
        print(_ascii(f"  failed {qid}: {why}"))
    for qid, found in out["problems"].items():
        for problem in found:
            print(_ascii(f"  problem {qid}: {problem}"))
    print("Plans are drafts: open each on /plan (or edit the file) and confirm it, or run system-run with "
          "--confirm-as-system.")
    return 1 if out["failed"] or out["problems"] else 0


def add_system_commands(sub) -> None:
    p = sub.add_parser("system-plan", help="draft one plan per question (orch-model), with its sub-questions")
    p.add_argument("--domain", required=True)
    p.add_argument("--redo", default="", help="question ids to plan again with a fresh call record, e.g. d01,d02")
    p.add_argument("--plans", type=Path, default=system.PLANS)
    p.add_argument("--questions-root", type=Path, default=QUESTIONS)
    p.add_argument("--spec-root", type=Path, default=SPECS)
    p.add_argument("--results", type=Path, default=RESULTS)
    p.set_defaults(run=system_plan)
