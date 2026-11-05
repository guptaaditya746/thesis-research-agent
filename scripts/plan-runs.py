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
Claude-written corpus, run to <runs>/effect-<corpus name>/ (for `evaluate leak`)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HAND_N = 5
AUTO, HAND = "auto-confirmed", "hand-confirmed"


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
    from evidence.plan import load_plan, write_plan
    from evidence.planner import critic, propose
    from evidence.planner.plan import check_plan
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
    flagged = 0
    for q in qs:
        path = args.plans / f"{q.id}.json"
        if not path.is_file():
            with using(lm):
                # propose puts the field ontology's other names into the word list (planner.with_ontology_names)
                plan, _how = propose(q.question, [], write_words=lambda text, things: write_words(text, things, lm=lm),
                                     templates=saved_templates())
                write_plan(critic(plan), path)
            print(f"planned {q.id}")
        # the web app refuses such a plan; here it is kept (a saved plan stays replayable) and named, exit 1
        problems = check_plan(load_plan(path), saved_templates())
        if problems:
            flagged += 1
            print(f"plan problems {q.id}: " + "; ".join(problems), file=sys.stderr)
    if flagged:
        print(f"FAIL plan check: {flagged} of {len(qs)} plans have problems (above); their lines will fail or find "
              "nothing", file=sys.stderr)
    return 1 if flagged else 0


def _show(plan, path: Path) -> None:
    """Each decision and the word list of a hand-confirmed plan, for the person to read before the run."""
    print(f"== {path}\n   question: {plan.question}")
    for d in plan.decisions:
        flag = f"  [critic: {d.flag_reason}]" if d.flagged else ""
        print(f"   decision {d.id} ({d.type}) = {json.dumps(d.value, ensure_ascii=False)}: {d.reason}{flag}")
    for thing, names in plan.words.things.items():
        extra = plan.words.ontology_names.get(thing, [])
        print(f"   words {thing}: {', '.join(names)}" + (f" | ontology: {', '.join(extra)}" if extra else ""))
    print(f"   cues: {', '.join(plan.words.cues)}")


def confirm_hand(args: argparse.Namespace, qs: list) -> int:
    """The hand row's confirmed plans: an existing file is kept (the person may have edited it); a missing one is
    written with every decision confirmed by --by. Each is printed."""
    from evidence.plan import load_plan, write_plan
    from evidence.planner import confirm_all
    if not args.by or args.by == "system":
        raise SystemExit("plan-runs: confirm needs --by NAME, a person (not system)")
    folder = args.plans / HAND
    folder.mkdir(parents=True, exist_ok=True)
    missing = [q.id for q in qs[:HAND_N] if not (folder / f"{q.id}.json").is_file()
               and not (args.plans / f"{q.id}.json").is_file()]
    if missing:   # before any file is written
        raise SystemExit(f"plan-runs: no plan for {', '.join(missing)} in {args.plans}: run `plan-runs.py plan` first")
    for q in qs[:HAND_N]:
        path = folder / f"{q.id}.json"
        if path.is_file():
            print(f"kept {path} (already confirmed)")
        else:
            write_plan(confirm_all(load_plan(args.plans / f"{q.id}.json"), args.by), path)
            print(f"wrote {path}")
        _show(load_plan(path), path)
    print(f"To change a decision or a word, edit the files under {folder} before `plan-runs.py run --confirm hand`.")
    return 0


def sealed_complete(folder: Path) -> bool:
    """The run folder is sealed with status `complete` (its manifest.json says so)."""
    from evidence.seal import MANIFEST_FILE
    try:
        return json.loads((folder / MANIFEST_FILE).read_text(encoding="utf-8")).get("status") == "complete"
    except (OSError, ValueError, AttributeError):
        return False


def has_unchecked(folder: Path) -> bool:
    """The run left items unchecked by a failed model call: any note in stage_report.json, or a recheck find whose
    call failed or whose reply did not parse (recheck_report.json)."""
    def read(name: str) -> dict:
        try:
            data = json.loads((folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
    if any(notes for docs in read("stage_report.json").values() if isinstance(docs, dict) for notes in docs.values()):
        return True
    return any(str(u.get("why", "")).startswith(("failed call:", "unparseable reply:"))
               for doc in read("recheck_report.json").values() if isinstance(doc, dict)
               for u in doc.get("unchecked") or [])


def set_aside(folder: Path, tag: str = "failed") -> Path:
    """Move a run folder to <name>.<tag>-<n> (n = 1, 2, ...): `failed` for a failed or unsealed run, `redo` for a
    complete one run again for its unchecked items; returns the new path."""
    n = 1
    while (target := folder.with_name(f"{folder.name}.{tag}-{n}")).exists():
        n += 1
    folder.rename(target)
    return target


def run_all(args: argparse.Namespace, qs: list) -> int:
    from evidence import planrun
    from evidence.plan import load_plan, write_plan
    from evidence.planner import confirm_all
    who = "system" if args.confirm == "auto" else args.confirm_by
    conf = AUTO if args.confirm == "auto" else HAND
    pool = qs if args.confirm == "auto" else qs[:HAND_N]
    written = all((args.plans / HAND / f"{q.id}.json").is_file() for q in pool)   # `confirm` wrote them all
    if args.confirm == "hand" and (who == "system" or (not who and not written)):
        raise SystemExit("plan-runs: --confirm hand needs --confirm-by NAME, a person (not system), or the hand "
                         "plans written by `plan-runs.py confirm`")
    out = args.runs if args.set in ("offtemplate", "synthetic") else args.runs / conf / args.reasoning   # offtemplate: <runs>/<qid>/
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for q in pool:
        folder = out / q.id
        retry = False
        if folder.exists():
            if sealed_complete(folder) and not (args.redo_unchecked and has_unchecked(folder)):
                print(f"skip {q.id}: {folder} is complete")
                continue
            if sealed_complete(folder):
                print(f"moved {folder} (complete, items unchecked) to {set_aside(folder, 'redo').name}; running {q.id} again")
            else:
                print(f"moved {folder} (failed or unsealed) to {set_aside(folder).name}; running {q.id} again")
            retry = True
        confirmed = args.plans / conf / f"{q.id}.json"
        if not confirmed.is_file():   # one confirmed plan per question and row, shared by the on and off runs
            confirmed.parent.mkdir(parents=True, exist_ok=True)
            write_plan(confirm_all(load_plan(args.plans / f"{q.id}.json"), who), confirmed)
        try:
            kw = {"model": args.model} if args.model else {}
            planrun.run(confirmed, q.corpus_dir, out, cache=args.cache, run_id=q.id, workers=args.workers,
                        reasoning=args.reasoning, links=args.links, retry_errors=retry, **kw)
            print(f"ran {conf}/{args.reasoning}/{q.id}")
        except Exception as exc:   # noqa: BLE001 - recorded; the next question still runs
            bad += 1
            print(f"FAILED {q.id}: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plan-runs.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "confirm", "run"):
        p = sub.add_parser(name)
        p.add_argument("--set", required=True, choices=("scilead", "scirex", "cochraneforest", "sofc", "offtemplate", "synthetic"))
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
            p.add_argument("--reasoning", choices=("on", "off"), required=True)
            p.add_argument("--links", choices=("on", "off"), default="on")
            p.add_argument("--redo-unchecked", action="store_true",
                           help="also rerun a complete run whose reports list items a failed call left unchecked")
            p.add_argument("--confirm-by")
            p.add_argument("--model")
            p.add_argument("--workers", type=int, default=3)
    args = ap.parse_args(argv)
    qs = questions(args)
    return {"plan": plan_all, "confirm": confirm_hand, "run": run_all}[args.cmd](args, qs)


if __name__ == "__main__":
    sys.exit(main())
