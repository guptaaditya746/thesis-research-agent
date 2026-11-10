"""Plan runs of the whole-run questions of one real set (general-system runbook, section 6).

    plan-runs.py plan    --set S --src DIR --sample FILE --plans DIR --cache DIR [--corpus DIR]
    plan-runs.py confirm --set S --src DIR --sample FILE --plans DIR --by NAME [--corpus DIR]
    plan-runs.py run     --set S --src DIR --sample FILE --plans DIR --cache DIR --runs DIR --confirm auto|hand
                         --reasoning on|off [--links on|off] [--redo-unchecked] [--confirm-by NAME] [--model ALIAS]
                         [--workers N] [--corpus DIR]

`plan` writes <plans>/<question id>.json for every question of FILE (sample.json, written by `evaluate wholerun`):
the planner (orch-model) and its critic, nothing confirmed; the word list holds the field ontology's other names.
`confirm` (the hand row, non-interactive): for each of the FIRST 5 questions, keeps an existing
<plans>/hand-confirmed/<id>.json, else writes it with every decision confirmed by NAME; it prints each decision and
the word list, so the person can edit that file before `run`. `run` confirms the plans and runs each as a plan run into
<runs>/<auto-confirmed|hand-confirmed>/<on|off>/<question id>/ (the layout `evaluate wholerun` reads).
auto: all questions, decisions confirmed by "system". hand: the first 5 questions, decisions confirmed by
--confirm-by NAME (a person who read those 5 plans; never "system"); an existing hand-confirmed file is used as it is,
never overwritten. --reasoning off: a real switch (no reasoner, no field ontology, no ontology tree; run.json settings
"reason": "off"). --links off: no builds-on links stage, so no OpenAlex request (run.json settings "links": "off"; use
it when the job has no network).
A question whose run folder is sealed `complete` is skipped. A folder that failed, or was never sealed, is moved to
<question id>.failed-<n> and the question runs again, asking failed model calls again (the record cache makes the
rest free). --redo-unchecked (default off): a complete folder whose stage_report.json or recheck_report.json lists
items left unchecked by a failed call is moved to <question id>.redo-<n> and run again the same way.
--set offtemplate: the 12 off-template questions (no --src, no --sample, --confirm auto --reasoning on); runs go to
<runs>/<question id>/ for `evaluate offtemplate`. --set synthetic --corpus DIR --question TEXT: one question on a
Claude-written corpus, run to <runs>/effect-<corpus name>/ (for `evaluate leak`).
The layout and these rules live in evaluation/planbatch.py; this script only parses its arguments."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evaluation import planbatch as pb
from evaluation.realpapers import WHOLE_RUN_SETS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plan-runs.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "confirm", "run"):
        p = sub.add_parser(name)
        p.add_argument("--set", required=True, choices=WHOLE_RUN_SETS + pb.FLAT_SETS)
        p.add_argument("--src", type=Path)
        p.add_argument("--corpus", type=Path)
        p.add_argument("--question")
        p.add_argument("--sample", type=Path)
        p.add_argument("--plans", type=Path, required=True)
        if name == "confirm":
            p.add_argument("--by", required=True)
        else:
            p.add_argument("--cache", type=Path, required=True)
        if name == "run":
            p.add_argument("--runs", type=Path, required=True)
            p.add_argument("--confirm", choices=("auto", "hand"), required=True)
            p.add_argument("--reasoning", choices=pb.REASONING, required=True)
            p.add_argument("--links", choices=("on", "off"), default="on")
            p.add_argument("--redo-unchecked", action="store_true",
                           help="also rerun a complete run whose reports list items a failed call left unchecked")
            p.add_argument("--confirm-by")
            p.add_argument("--model")
            p.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)
    try:
        qs = pb.questions(args.set, src=args.src, sample=args.sample, corpus=args.corpus, question=args.question)
        if args.cmd == "plan":
            return pb.plan_all(qs, args.plans, args.cache)
        if args.cmd == "confirm":
            return pb.confirm_hand(qs, args.plans, args.by)
        return pb.run_all(qs, set_name=args.set, plans=args.plans, runs=args.runs, cache=args.cache,
                          confirm=args.confirm, reasoning=args.reasoning, links=args.links,
                          redo_unchecked=args.redo_unchecked, confirm_by=args.confirm_by, model=args.model,
                          workers=args.workers)
    except pb.BatchError as exc:
        raise SystemExit(f"plan-runs: {exc}") from None


if __name__ == "__main__":
    sys.exit(main())
