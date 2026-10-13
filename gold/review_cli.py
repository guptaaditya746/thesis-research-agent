"""`gold` subcommands of the review and the judge (work package C2), added by `register(subparsers)`.

Order of use (gold/REVIEW.md; labelling README steps 4-11):
  gold push all                    review, overlap and missing-facts records into Argilla
  gold screening-sample; gold screening-push
  (people review in Argilla)
  gold snapshot                    when both have finished the overlap, before discussing it
  gold pull                        every dataset into $GOLD/<qid>/review/ (and an overlap snapshot)
  gold export all [--adjudicator NAME]   key.json + export.json; adjudicate, pull, export again
  gold agreement                   report.json per question and overall
  gold judge-sample; gold judge-push; (people answer); gold pull; gold judge-agreement
  gold judge FACT_JSON QUOTE       one verdict, e.g. to try a prompt
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from . import agreement, argilla_io, export, judge, review, screening_check

DEFAULT_SEED = "gold-v1"


def _root(args: argparse.Namespace) -> Path:
    return review.gold_root(args.gold)


def _env_path(name: str, default: str | None = None) -> Path | None:
    value = os.environ.get(name) or default
    return Path(value) if value else None


def _add(sub: Any, name: str, func: Any, help: str, *, argilla: bool = False, corpus: bool = False,
         concepts: bool = False) -> argparse.ArgumentParser:
    p = sub.add_parser(name, help=help, description=help)
    p.set_defaults(func=func)
    p.add_argument("--gold", type=Path, default=None, help="gold working directory (default: $GOLD or gold-data)")
    if argilla:
        p.add_argument("--name", default=argilla_io.DEFAULT_NAME, help="dataset name prefix (default: %(default)s)")
        p.add_argument("--workspace", default=os.environ.get("ARGILLA_WORKSPACE", argilla_io.DEFAULT_WORKSPACE),
                       help="Argilla workspace (default: $ARGILLA_WORKSPACE or %(default)s)")
    if corpus:
        p.add_argument("--corpus", type=Path, default=_env_path("CORPUS"), help="frozen corpus (default: $CORPUS)")
    if concepts:
        p.add_argument("--concepts", type=Path, default=_env_path("CONCEPTS", "concepts"),
                       help="concept sessions (default: $CONCEPTS or concepts)")
        p.add_argument("--questions", type=Path, default=Path("questions/questions.json"),
                       help="question list (default: %(default)s)")
    return p


def _pull(args: argparse.Namespace, datasets: tuple[str, ...] = argilla_io.DATASETS) -> dict[str, int]:
    pulled = argilla_io.pull(argilla_io.client(), name=args.name, workspace=args.workspace, datasets=datasets)
    counts = review.store(_root(args), pulled)
    for path in review.snapshot(_root(args), pulled.get("overlap", [])):
        print(f"snapshot {path}")
    return counts


def _need_corpus(args: argparse.Namespace) -> review.Corpus:
    if args.corpus is None:
        raise SystemExit("gold: give --corpus or set $CORPUS")
    return review.Corpus(args.corpus)


# --- Argilla ----------------------------------------------------------------------------------------------

def cmd_push(args: argparse.Namespace) -> int:
    root, corpus = _root(args), _need_corpus(args)
    every = sorted(review.questions(args.questions)) or review.question_ids(root)
    overlap = review.overlap_questions(root, every, share=args.overlap_share, seed=args.seed)
    batches: dict[str, list[dict[str, Any]]] = {"review": [], "overlap": [], "missing": []}
    for qid in review.select(root, args.qid):
        items = {item["id"]: item for item in review.pool(root, qid)}
        if not items:
            print(f"SKIP {qid}: no pool.jsonl in {review.qdir(root, qid)}")
            continue
        question = review.question_text(qid, questions_file=args.questions, concepts=args.concepts)
        concept_md = argilla_io.concept_markdown(review.concept(args.concepts, qid))
        target = "overlap" if qid in overlap else "review"
        for cid in review.seeded_order(items, f"{args.seed}:order:{qid}"):  # strata mixed, order fixed
            item = items[cid]
            batches[target].append(argilla_io.review_record(
                item, question=question, concept_md=concept_md, passage_md=argilla_io.candidate_passage(corpus, item)))
        scope = argilla_io.scope_markdown(review.read_json(review.qdir(root, qid) / "doc.json"), review.screening(root, qid))
        batches["missing"].append(argilla_io.missing_record(qid, question=question, concept_md=concept_md, scope_md=scope))
        print(f"{qid}: {len(items)} records -> {target}")
    api = argilla_io.client()
    for dataset, records in batches.items():
        n = argilla_io.push(api, dataset, records, name=args.name, workspace=args.workspace)
        print(f"{args.name}-{dataset}: {n} records pushed")
    print(f"overlap questions: {', '.join(overlap) or 'none'}")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    for dataset, n in _pull(args).items():
        print(f"{args.name}-{dataset}: {n} records")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    counts = _pull(args, ("overlap",))
    print(f"{args.name}-overlap: {counts.get('overlap', 0)} records")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    if args.pull:
        _pull(args, ("review", "overlap", "missing", "screening"))
    root, corpus, failed = _root(args), review.Corpus(args.corpus), 0
    if args.corpus is None:
        print("WARN no --corpus or $CORPUS: missing-fact lines cannot be anchored and will be rejected")
    for qid in review.select(root, args.qid):
        done = export.export(root, qid, corpus=corpus, concepts=args.concepts, adjudicator=args.adjudicator)
        for problem in done.problems:
            print(f"  {qid}: {problem}")
        if done.key is None:
            failed += 1
            print(f"FAIL {qid}: no key written")
            continue
        c = done.key["review"]
        print(f"{qid}: key.json rows={c['rows']} facts={c['facts']} kept={c['kept']}/{c['records']} "
              f"added={c['added']} rejected={c['added_rejected']} unreviewed={c['unreviewed']} "
              f"disagreements={c['disagreements']} (unresolved {c['unresolved']})")
    return 1 if failed else 0


def cmd_agreement(args: argparse.Namespace) -> int:
    if args.pull:
        _pull(args, ("review", "overlap", "missing", "screening"))
    root = _root(args)
    overall = agreement.write_reports(root, review.select(root, args.qid), adjudicator=args.adjudicator)
    k = overall["kappa"]
    print(f"overlap: reviewers={k['reviewers']} items={k['items']} questions={k['questions']}")
    for field in agreement.FIELDS:
        print(f"  {field}: kappa={k[field]['kappa']} 95%={k[field].get('kappa_95')} items={k[field]['items']}")
    print(f"triage: estimated missed={overall['triage']['estimated_missed']} "
          f"bounds={overall['triage']['estimated_missed_bounds']}")
    s = overall["screening"]["overall"]
    print(f"screening: checked={s['checked']} found relevant={s['found_relevant']} "
          f"estimated missed papers={s['estimated_missed_papers']} bounds={s['estimated_missed_papers_bounds']}")
    print(f"wrote {root / 'report.json'}")
    return 0


# --- screening check ------------------------------------------------------------------------------------

def cmd_screening_sample(args: argparse.Namespace) -> int:
    root = _root(args)
    for qid in review.select(root, args.qid):
        s = screening_check.sample(root, qid, size=args.size, seed=args.seed)
        print(f"{qid}: {s['sampled']} of {s['not_relevant']} not relevant drawn ({s['unread']} unread)")
    return 0


def cmd_screening_push(args: argparse.Namespace) -> int:
    root, corpus = _root(args), _need_corpus(args)
    records = []
    for qid in review.select(root, args.qid):
        question = review.question_text(qid, questions_file=args.questions, concepts=args.concepts)
        concept_md = argilla_io.concept_markdown(review.concept(args.concepts, qid))
        records += screening_check.records(root, qid, corpus, question=question, concept_md=concept_md)
    n = argilla_io.push(argilla_io.client(), "screening", records, name=args.name, workspace=args.workspace)
    print(f"{args.name}-screening: {n} records pushed")
    return 0


# --- judge ---------------------------------------------------------------------------------------------

def cmd_judge_sample(args: argparse.Namespace) -> int:
    rows, manifest = judge.sample_pairs(args.runs, size=args.size, seed=args.seed)
    judge.write_sample(_root(args), rows, manifest)
    print(f"population {manifest['population']} -> sampled {manifest['sampled']} ({len(rows)} pairs)")
    return 0


def cmd_judge_push(args: argparse.Namespace) -> int:
    rows, _ = judge.load_sample(_root(args))
    if not rows:
        raise SystemExit("gold: no judge sample; run `gold judge-sample` first")
    records = judge.records(rows, _need_corpus(args))
    n = argilla_io.push(argilla_io.client(), "judge", records, name=args.name, workspace=args.workspace)
    print(f"{args.name}-judge: {n} records pushed")
    return 0


def cmd_judge_agreement(args: argparse.Namespace) -> int:
    if args.pull:
        _pull(args, ("judge",))
    root = _root(args)
    report = judge.calibration_report(root, _need_corpus(args), judge=judge.Judge(root), seed=args.seed)
    t = report["test"]
    print(f"answered={report['answered']} split={report['split']} partial counts as "
          f"{report['calibration']['partial_counts_as']}")
    print(f"test: kappa={t['kappa']} weighted={t['weighted_kappa']} yes-precision={t['precision_judge_yes']}")
    print(report["advice"])
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    fact = json.loads(args.fact)
    verdict = judge.Judge(_root(args)).support(fact, args.quote, context=args.context)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0


def register(sub: Any) -> None:
    """Add the review and judge subcommands to the `gold` parser's subparsers."""
    p = _add(sub, "push", cmd_push, "push review, overlap and missing-facts records to Argilla",
             argilla=True, corpus=True, concepts=True)
    p.add_argument("qid", help="question id, comma-separated ids, or all")
    p.add_argument("--overlap-share", type=float, default=review.OVERLAP_SHARE,
                   help="share of questions two people review (default: %(default)s; fixed at the first push)")
    p.add_argument("--seed", default=DEFAULT_SEED)

    _add(sub, "pull", cmd_pull, "pull every dataset's responses into $GOLD", argilla=True)
    _add(sub, "snapshot", cmd_snapshot, "snapshot the overlap before adjudication", argilla=True)

    p = _add(sub, "export", cmd_export, "write key.json and export.json from the pulled reviews",
             argilla=True, corpus=True, concepts=True)
    p.add_argument("qid", help="question id, comma-separated ids, or all")
    p.add_argument("--adjudicator", help="user whose answer settles disagreements")
    p.add_argument("--pull", action="store_true", help="pull from Argilla first")

    p = _add(sub, "agreement", cmd_agreement, "kappa, triage miss and screening false negatives -> report.json",
             argilla=True)
    p.add_argument("qid", nargs="?", default="all")
    p.add_argument("--adjudicator", help="as for export")
    p.add_argument("--pull", action="store_true", help="pull from Argilla first")

    p = _add(sub, "screening-sample", cmd_screening_sample, "sample papers screened not relevant")
    p.add_argument("qid", nargs="?", default="all")
    p.add_argument("--size", type=int, default=screening_check.DEFAULT_SIZE)
    p.add_argument("--seed", default=DEFAULT_SEED)

    p = _add(sub, "screening-push", cmd_screening_push, "push the screening sample to Argilla",
             argilla=True, corpus=True, concepts=True)
    p.add_argument("qid", nargs="?", default="all")

    p = _add(sub, "judge-sample", cmd_judge_sample, "sample fact-quote pairs from runs for judge calibration")
    p.add_argument("--runs", type=Path, default=_env_path("RUNS", "runs"), help="runs root (default: $RUNS or runs)")
    p.add_argument("--size", type=int, default=judge.SAMPLE_SIZE)
    p.add_argument("--seed", default=judge.SAMPLE_SEED)

    _add(sub, "judge-push", cmd_judge_push, "push the judge sample to Argilla", argilla=True, corpus=True)

    p = _add(sub, "judge-agreement", cmd_judge_agreement, "calibrate the judge against people -> judge-report.json",
             argilla=True, corpus=True)
    p.add_argument("--seed", default=judge.SAMPLE_SEED)
    p.add_argument("--pull", action="store_true", help="pull the judge dataset first")

    p = _add(sub, "judge", cmd_judge, "one judge verdict: does QUOTE support FACT_JSON ({\"s\",\"p\",\"o\"})?")
    p.add_argument("fact", help='e.g. \'{"s": "p12", "p": "evaluatesOn", "o": "HotpotQA"}\'')
    p.add_argument("quote")
    p.add_argument("--context", help="text around the quote (see judge.context_for)")
