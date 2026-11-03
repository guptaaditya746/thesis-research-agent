"""Plan runs of the whole-run questions of one real set (general-system runbook, section 6).

    plan-runs.py plan --set S --src DIR --sample FILE --plans DIR --cache DIR [--corpus DIR]
    plan-runs.py run  --set S --src DIR --sample FILE --plans DIR --cache DIR --runs DIR --confirm auto|hand
                      --reasoning on|off [--confirm-by NAME] [--model ALIAS] [--workers N] [--corpus DIR]

`plan` writes <plans>/<question id>.json for every question of FILE (sample.json, written by `evaluate wholerun`):
the planner (orch-model) and its critic, nothing confirmed. `run` confirms them and runs each as a plan run into
<runs>/<auto-confirmed|hand-confirmed>/<on|off>/<question id>/ (the layout `evaluate wholerun` reads).
auto: all questions, decisions confirmed by "system". hand: the FIRST 5 questions, decisions confirmed by
--confirm-by NAME (a person who read those 5 plans; never "system"). reasoning off: EV_ONTOLOGY_DIR points at an
empty folder for the run (a stand-in; see the runbook). A question whose run folder exists is skipped.
--set offtemplate: the 12 off-template questions (no --src, no --sample, --confirm auto --reasoning on); runs go to
<runs>/<question id>/ for `evaluate offtemplate`. --set synthetic --corpus DIR --question TEXT: one question on a
Claude-written corpus, run to <runs>/effect-<corpus name>/ (for `evaluate leak`)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HAND_N = 5


def questions(args: argparse.Namespace) -> list:
    if args.set == "offtemplate":   # the 12 generality questions on their own corpus; no sample, no src
        from types import SimpleNamespace

        from evaluation.offtemplate import check as ot
        return [SimpleNamespace(id=q.id, question=q.question, corpus_dir=ot.ROOT / "tests/EV2/corpora/rag-claude-s1-mixed")
                for q in ot.load_questions()]
    if args.set == "synthetic":   # one question on a Claude-written corpus (for `evaluate leak`): id effect-<corpus name>
        from types import SimpleNamespace
        if args.corpus is None or not args.question:
            raise SystemExit("plan-runs: --set synthetic needs --corpus and --question")
        return [SimpleNamespace(id=f"effect-{args.corpus.name}", question=args.question, corpus_dir=args.corpus)]
    if args.src is None or args.sample is None:
        raise SystemExit("plan-runs: --src and --sample are required for a real set")
    from evaluation.cli import _real_questions
    ids = json.loads(args.sample.read_text(encoding="utf-8"))["ids"]
    by_id = {q.id: q for q in _real_questions(args.set, args.src, args.corpus)}
    return [by_id[i] for i in ids]


def plan_all(args: argparse.Namespace, qs: list) -> int:
    from evidence.plan import write_plan
    from evidence.planner import critic, propose
    from evidence.stages import gateway_ask
    from evidence.steps import using
    from evidence.words.write import write_words
    from modelcall.cache import JsonlCache
    from modelcall.dspy_lm import RecordedLM
    from modelcall.pins import ORCH_ALIAS
    from webapp.planwire import saved_templates
    args.cache.mkdir(parents=True, exist_ok=True)
    lm = RecordedLM(ORCH_ALIAS, gateway_ask(ORCH_ALIAS), cache=JsonlCache(args.cache / "planner.jsonl"))
    args.plans.mkdir(parents=True, exist_ok=True)
    for q in qs:
        path = args.plans / f"{q.id}.json"
        if path.is_file():
            continue
        with using(lm):
            plan, _how = propose(q.question, [], write_words=lambda text, things: write_words(text, things, lm=lm),
                                 templates=saved_templates())
            write_plan(critic(plan), path)
        print(f"planned {q.id}")
    return 0


def run_all(args: argparse.Namespace, qs: list) -> int:
    import tempfile

    from evidence import planrun
    from evidence.plan import load_plan, write_plan
    from evidence.planner import confirm_all
    who = "system" if args.confirm == "auto" else args.confirm_by
    if args.confirm == "hand" and (not who or who == "system"):
        raise SystemExit("plan-runs: --confirm hand needs --confirm-by NAME, a person (not system)")
    conf = "auto-confirmed" if args.confirm == "auto" else "hand-confirmed"
    pool = qs if args.confirm == "auto" else qs[:HAND_N]
    if args.reasoning == "off":
        os.environ["EV_ONTOLOGY_DIR"] = tempfile.mkdtemp(prefix="no-ontology-")
    out = args.runs if args.set in ("offtemplate", "synthetic") else args.runs / conf / args.reasoning   # offtemplate: <runs>/<qid>/
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for q in pool:
        if (out / q.id).exists():
            print(f"skip {q.id}: {out / q.id} exists")
            continue
        confirmed = args.plans / conf / f"{q.id}.json"
        if not confirmed.is_file():   # one confirmed plan per question and row, shared by the on and off runs
            confirmed.parent.mkdir(parents=True, exist_ok=True)
            write_plan(confirm_all(load_plan(args.plans / f"{q.id}.json"), who), confirmed)
        try:
            kw = {"model": args.model} if args.model else {}
            planrun.run(confirmed, q.corpus_dir, out, cache=args.cache, run_id=q.id, workers=args.workers, **kw)
            print(f"ran {conf}/{args.reasoning}/{q.id}")
        except Exception as exc:   # noqa: BLE001 - recorded; the next question still runs
            bad += 1
            print(f"FAILED {q.id}: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plan-runs.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--set", required=True, choices=("scilead", "scirex", "cochraneforest", "sofc", "offtemplate", "synthetic"))
        p.add_argument("--src", type=Path)
        p.add_argument("--corpus", type=Path)
        p.add_argument("--question")
        p.add_argument("--sample", type=Path)
        p.add_argument("--plans", type=Path, required=True)
        p.add_argument("--cache", type=Path, required=True)
        if name == "run":
            p.add_argument("--runs", type=Path, required=True)
            p.add_argument("--confirm", choices=("auto", "hand"), required=True)
            p.add_argument("--reasoning", choices=("on", "off"), required=True)
            p.add_argument("--confirm-by")
            p.add_argument("--model")
            p.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)
    qs = questions(args)
    return plan_all(args, qs) if args.cmd == "plan" else run_all(args, qs)


if __name__ == "__main__":
    sys.exit(main())
