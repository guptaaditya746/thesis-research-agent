"""`synth3` commands for the system under test: `system-plan` drafts one plan per question."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from synth3 import system
from synth3.cliargs import BadArgument, _ascii, _seeds, _spec, each_folder
from synth3.qcli import _questions
from synth3.questions import QUESTIONS
from synth3.sheetfacts import Folder
from synth3.sheets import RESULTS, folders_of
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


def system_run(args: argparse.Namespace) -> int:
    spec, seeds = _spec(args), _seeds(args.seeds)
    qs = _questions(args, spec)
    keys = ("ran", "rerun", "kept", "skipped", "failed", "empty", "by_system")

    def step(folder: Folder) -> tuple[list[str], bool]:
        out = system.run_folder(folder, qs, args.plans, args.results, as_system=args.confirm_as_system,
                                workers=args.workers)
        n = {k: len(out[k]) for k in keys}
        lines = [f"s{folder.seed}: ran {n['ran']}, rerun {n['rerun']}, kept {n['kept']}, skipped {n['skipped']}, "
                 f"failed {n['failed']}, empty {n['empty']}, plans confirmed by system {n['by_system']}"]
        lines += [f"  skipped {qid}: {why}" for qid, why in out["skipped"].items()]
        lines += [f"  failed {qid}: {why}" for qid, why in out["failed"].items()]
        lines += [f"  empty {qid}" for qid in out["empty"]]
        return lines, bool(out["failed"])

    return each_folder(args.folders or folders_of(args.domain), seeds, spec, step)


def add_system_commands(sub) -> None:
    p = sub.add_parser("system-plan", help="draft one plan per question (orch-model), with its sub-questions")
    p.add_argument("--domain", required=True)
    p.add_argument("--redo", default="", help="question ids to plan again with a fresh call record, e.g. d01,d02")
    p.add_argument("--plans", type=Path, default=system.PLANS)
    p.add_argument("--questions-root", type=Path, default=QUESTIONS)
    p.add_argument("--spec-root", type=Path, default=SPECS)
    p.add_argument("--results", type=Path, default=RESULTS)
    p.set_defaults(run=system_plan)
    r = sub.add_parser("system-run", help="run every confirmed plan on every folder and save the answers")
    r.add_argument("--domain", required=True)
    r.add_argument("--seeds", default="1,2,3,4,5", help="comma-separated, e.g. 1,2,3,4,5")
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--confirm-as-system", action="store_true",
                   help="run a system-confirmed copy of each plan nobody confirmed (the draft is not changed)")
    r.add_argument("--folders", type=Path, default=None, help="holds s<seed>/; default: the domain's built set")
    r.add_argument("--plans", type=Path, default=system.PLANS)
    r.add_argument("--questions-root", type=Path, default=QUESTIONS)
    r.add_argument("--spec-root", type=Path, default=SPECS)
    r.add_argument("--results", type=Path, default=RESULTS)
    r.set_defaults(run=system_run)
