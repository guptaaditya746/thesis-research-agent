"""`synth3` commands about questions: `questions` checks Aditya's file and shows what each one is about;
`draft-sheets` drafts the answer sheets of a domain's folders."""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import modelcall
from modelcall import JsonlCache
from synth3.answers import SYSTEM_ID, from_engine_run, save_answer
from synth3.baseline import BASELINE, baseline_folder
from synth3.cliargs import BadArgument, _seeds, _spec, each_folder
from synth3.drafter import DRAFTER_ALIAS, draft_folder_sheets
from synth3.questions import QUESTIONS, QuestionSet, load_questions
from synth3.sheetfacts import Folder, scope
from synth3.sheets import RESULTS, SHEETS, folders_of
from synth3.spec import SPECS


def _questions(args: argparse.Namespace, spec) -> QuestionSet:
    try:
        return load_questions(args.domain, spec, args.questions_root)
    except (OSError, ValueError) as err:
        raise BadArgument(str(err)) from err


def questions(args: argparse.Namespace) -> int:
    spec = _spec(args)
    qs = _questions(args, spec)
    print(f"{len(qs.questions)} questions in {args.questions_root / (args.domain + '.yaml')}")
    labels = {a.id: a.label for a in spec.arms}
    names = {m.id: m.name for m in spec.measures}
    for q in qs.questions:
        n = scope(spec, q)
        arms = ", ".join(labels[a] for a in n.arms) or "all"
        measures = ", ".join(names[m] for m in n.measures) or "all"
        print(f"{q.id}: arms {arms}; measures {measures}; {len(q.sub_questions)} sub-questions")
    return 0


def draft_sheets(args: argparse.Namespace) -> int:
    spec, seeds = _spec(args), _seeds(args.seeds)
    qs = _questions(args, spec)
    redraft = {x.strip() for x in (args.redraft or "").split(",") if x.strip()}
    unknown = sorted(redraft - {q.id for q in qs.questions})
    if unknown:
        raise BadArgument(f"--redraft names questions that are not in the file: {', '.join(unknown)}")
    from modelcall import gateway   # pydantic-ai is heavy; load it only here
    model = gateway.openai_model(args.model)
    cache = JsonlCache(args.results / args.domain / "drafter-calls.jsonl")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def step(folder: Folder) -> tuple[list[str], bool]:
        out = draft_folder_sheets(folder, qs, model, cache, args.sheets, redraft=redraft, now=now)
        lines = [f"s{folder.seed}: drafted {len(out['drafted'])} (can't tell {len(out['cant_tell'])}), "
                 f"kept {len(out['kept'])}, failed {len(out['failed'])}"]
        lines += [f"  failed: {why}" for why in out["failed"].values()]
        lines += [f"  stale checked sheet: {qid} (fix it on the review page, or pass --redraft {qid})"
                  for qid in out["stale_checked"]]
        return lines, bool(out["failed"])

    return each_folder(args.folders or folders_of(args.domain), seeds, spec, step)


def collect(args: argparse.Namespace) -> int:
    spec = _spec(args)
    if not re.match(SYSTEM_ID, args.system):
        raise BadArgument(f"--system must match {SYSTEM_ID}, got '{args.system}'")
    try:
        q = _questions(args, spec).get(args.question)
    except KeyError as err:
        raise BadArgument(str(err.args[0])) from err

    def step(folder: Folder) -> tuple[list[str], bool]:
        try:
            rec = from_engine_run(args.run_dir, folder, q, args.system)
        except (OSError, ValueError) as err:
            raise BadArgument(str(err)) from err
        return [str(save_answer(args.results, rec))], False

    return each_folder(args.folders or folders_of(args.domain), [args.seed], spec, step)


def baseline(args: argparse.Namespace) -> int:
    spec, seeds = _spec(args), _seeds(args.seeds)
    qs = _questions(args, spec)
    from modelcall import gateway   # pydantic-ai is heavy; load it only here
    model = gateway.openai_model(args.model)
    model_id = modelcall.model_identity([model])
    cache = JsonlCache(args.results / args.domain / "rag-baseline-calls.jsonl")

    def step(folder: Folder) -> tuple[list[str], bool]:
        out = baseline_folder(folder, qs, model, model_id, cache, args.results)
        lines = [f"s{folder.seed}: answered {out['answered']}, skipped {out['skipped']}, "
                 f"failed {len(out['failed'])}"]
        lines += [f"  failed: {why}" for why in out["failed"].values()]
        return lines, bool(out["failed"])

    return each_folder(args.folders or folders_of(args.domain), seeds, spec, step)


def add_question_commands(sub) -> None:
    p = sub.add_parser("questions", help="check a domain's question file and show what each question is about")
    p.add_argument("--domain", required=True)
    p.add_argument("--spec-root", type=Path, default=SPECS)
    p.add_argument("--questions-root", type=Path, default=QUESTIONS)
    p.set_defaults(run=questions)
    d = sub.add_parser("draft-sheets", help="draft the answer sheets of a domain's folders (orch-model; can't-tell "
                                            "sheets by code)")
    d.add_argument("--domain", required=True)
    d.add_argument("--folders", type=Path, default=None, help="holds s<seed>/; default: the domain's built set")
    d.add_argument("--seeds", default="1,2,3,4,5", help="comma-separated, e.g. 1,2,3,4,5")
    d.add_argument("--model", default=DRAFTER_ALIAS)
    d.add_argument("--redraft", default="", help="question ids to draft again past the call cache, e.g. d01,d02")
    d.add_argument("--sheets", type=Path, default=SHEETS)
    d.add_argument("--questions-root", type=Path, default=QUESTIONS)
    d.add_argument("--spec-root", type=Path, default=SPECS)
    d.add_argument("--results", type=Path, default=RESULTS)
    d.set_defaults(run=draft_sheets)
    c = sub.add_parser("collect", help="put one engine run's answer to a question into the judge's shape")
    c.add_argument("--domain", required=True)
    c.add_argument("--seed", type=int, required=True)
    c.add_argument("--question", required=True, help="the question id")
    c.add_argument("--run", dest="run_dir", type=Path, required=True, help="the engine run folder")
    c.add_argument("--system", default="engine", help="lower case letters, digits and '-'")
    c.add_argument("--folders", type=Path, default=None, help="holds s<seed>/; default: the domain's built set")
    c.add_argument("--questions-root", type=Path, default=QUESTIONS)
    c.add_argument("--spec-root", type=Path, default=SPECS)
    c.add_argument("--results", type=Path, default=RESULTS)
    c.set_defaults(run=collect)
    b = sub.add_parser("baseline", help=f"run the {BASELINE} on every question and folder (orch-model; 2 calls "
                                        "per question and folder)")
    b.add_argument("--domain", required=True)
    b.add_argument("--folders", type=Path, default=None, help="holds s<seed>/; default: the domain's built set")
    b.add_argument("--seeds", default="1,2,3,4,5", help="comma-separated, e.g. 1,2,3,4,5")
    b.add_argument("--model", default="orch-model")
    b.add_argument("--questions-root", type=Path, default=QUESTIONS)
    b.add_argument("--spec-root", type=Path, default=SPECS)
    b.add_argument("--results", type=Path, default=RESULTS)
    b.set_defaults(run=baseline)
