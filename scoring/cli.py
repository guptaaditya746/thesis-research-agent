"""`score` command line (milestone 4; scoring/README.md).

  score run <run> [--key <key.json>]                      -> <run>/score.json
  score batch <runs_root> --gold $GOLD [--manifest m.json] -> <runs_root>/report/scores.jsonl, batch.json
  score report <runs_root>                                -> <runs_root>/report/report.json, report.md, *.csv
  score store <runs_root> [--path $RUNS/.oxigraph]        -> every run's graph.ttl in the SPARQL store
  score sparql <query-file> [--run ID] [--path ...]        -> {vars, rows} as JSON

The judge (gold/judge.py) is used unless --no-judge; its cache and calibration live in $GOLD (`--gold`
sets it). It judges each quote with the context it was calibrated on, which needs the corpus: with
the judge on, `run` and `batch` refuse to start without --corpus or $CORPUS. `run` without --key
takes $GOLD/<qid>/key.json, else key.draft.json, for the run's question (by run id or concept hash).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .judge import Judge


class Usage(ValueError):
    pass


def _runs_env() -> Path:
    return Path(os.environ.get("RUNS", "runs"))


def _gold_env() -> Path:
    return Path(os.environ.get("GOLD", "gold-data"))


def _judge_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--gold", type=Path, default=_gold_env(),
                        help="gold directory: keys, judge cache and calibration (default: $GOLD)")
    parser.add_argument("--corpus", type=Path, default=os.environ.get("CORPUS") or None,
                        help="frozen corpus (default: $CORPUS): `agent verify` and the judge's context")
    parser.add_argument("--corpus-manifest", type=Path, help="default: <corpus>/manifest.json")
    parser.add_argument("--no-judge", action="store_true",
                        help="no LLM judge: soft matches and support verdicts stay pending")
    parser.add_argument("--workers", type=int, default=6, help="parallel judge calls (3 per sub-model replica)")


def _judge(args: argparse.Namespace) -> Judge | None:
    from .judge import load

    if args.no_judge:
        return None
    os.environ["GOLD"] = str(args.gold)  # gold.judge keeps its cache and calibration in $GOLD
    judge = load(workers=args.workers)
    if judge is not None and args.corpus is None and judge.has("support_pair"):
        raise Usage("the judge needs the corpus (--corpus or $CORPUS) to see each quote with the context it was "
                    "calibrated on; or pass --no-judge")
    return judge


def cmd_run(args: argparse.Namespace) -> int:
    from agent.rundir import RunDir

    from .batch import key_for
    from .run_score import ScoreError, line, score_run

    try:
        key = args.key
        if key is None:
            found = key_for(args.gold, RunDir(args.run_dir))
            if found is None:
                raise ScoreError(f"no key yet: no key.json or key.draft.json in {args.gold} for this run's question")
            key = found.path
        score = score_run(args.run_dir, key, judge=_judge(args), corpus=args.corpus,
                          manifest=args.corpus_manifest, gold=args.gold)
    except (ScoreError, Usage, OSError, ValueError, KeyError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(line(score))
    print(f"wrote {Path(args.run_dir) / 'score.json'} (key {key})")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    from .batch import BATCH_FILE, REPORT_DIR, SCORES_FILE, score_batch

    try:
        summary = score_batch(args.runs_root, args.gold, manifest=args.manifest, corpus=args.corpus,
                              corpus_manifest=args.corpus_manifest, force=args.force, judge=_judge(args),
                              include_all=args.all)
    except (Usage, OSError, ValueError) as exc:
        print(f"FAIL {exc}")
        return 1
    c = summary["counts"]
    out = Path(args.runs_root) / REPORT_DIR
    print(f"scored {c['scored']}, reused {c['reused']}, skipped {c['skipped']}, failed {c['failed']}"
          + (" (PROVISIONAL: draft keys used)" if summary["provisional"] else ""))
    print(f"wrote {out / SCORES_FILE} and {out / BATCH_FILE}")
    return 1 if c["failed"] else 0


def cmd_report(args: argparse.Namespace) -> int:
    from .batch import REPORT_DIR
    from .report import RESAMPLES, SEED, ReportError, write

    try:
        report = write(args.runs_root, seed=SEED if args.seed is None else args.seed,
                       resamples=RESAMPLES if args.resamples is None else args.resamples)
    except ReportError as exc:
        print(f"FAIL {exc}")
        return 1
    p, c = report["primary"], report["completeness"]
    if p["computed"]:
        print(f"primary: support share claim_on - claim_off = {p['mean_difference']:.3f} over {p['n_pairs']} "
              f"questions, Wilcoxon p = {p['p_value']:.4g}")
    else:
        print(f"primary: not computed ({p['reason']})")
    if report["provisional"]:
        print("PROVISIONAL: draft keys used; do not report these numbers")
    if c["pending_support_runs"] or c["pending_soft_runs"]:
        print(f"INCOMPLETE: judge decisions pending in {len(set(c['pending_support_runs'] + c['pending_soft_runs']))} "
              "runs; run `score batch` with the judge")
    if c["unverified_runs"] or c["verify_failed_runs"]:
        print(f"UNVERIFIED: {len(c['unverified_runs'])} runs not verified, {len(c['verify_failed_runs'])} failed")
    if c["key_problem_runs"]:
        print(f"KEY PROBLEMS: {len(c['key_problem_runs'])} runs scored against keys that do not validate")
    if c["settings_differ"]:
        print(f"SETTINGS DIFFER: {', '.join(c['settings_differ'])}")
    print(f"wrote {Path(args.runs_root) / REPORT_DIR}/report.json, report.md and CSV tables")
    return 0


def cmd_store(args: argparse.Namespace) -> int:
    from .store import RunStore

    result = RunStore(args.path).load_tree(args.runs_root)
    for path in result["duplicates"]:
        print(f"skipped {path}: a run with this id is already loaded")
    print(f"{len(result['runs'])} runs with graph.ttl, {len(result['loaded'])} (re)loaded -> {args.path}")
    return 0


def cmd_sparql(args: argparse.Namespace) -> int:
    from .store import RunStore

    try:
        result = RunStore(args.path).query(Path(args.query_file).read_text(encoding="utf-8"), run_id=args.run)
    except (OSError, ValueError, SyntaxError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="score", description="Score runs against answer keys; the M4 report.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="score one run against an answer key -> <run>/score.json")
    run.add_argument("run_dir", type=Path)
    run.add_argument("--key", type=Path, help="key.json, or key.draft.json (provisional); default: the run's "
                                              "question's key in --gold")
    _judge_args(run)
    run.set_defaults(func=cmd_run)

    batch = sub.add_parser("batch", help="score every finished run; write report/scores.jsonl")
    batch.add_argument("runs_root", type=Path, help="where report/ goes (the web app reads $RUNS/report/)")
    batch.add_argument("--manifest", type=Path, help="the run manifest agent batch ran ($RUNS/<name>/manifest.json "
                                                     "from scripts/e2e-batch.sh): its runs_root holds the attempts; "
                                                     "without it every batch run below runs_root, keyed by concept")
    batch.add_argument("--all", action="store_true", help="without --manifest: also runs whose id is not a batch key")
    batch.add_argument("--force", action="store_true", help="rescore runs that already have a current score.json")
    _judge_args(batch)
    batch.set_defaults(func=cmd_batch)

    report = sub.add_parser("report", help="report.json, report.md and CSV tables from report/scores.jsonl")
    report.add_argument("runs_root", type=Path)
    report.add_argument("--seed", type=int, default=None, help="bootstrap seed (default: the pre-registered one)")
    report.add_argument("--resamples", type=int, default=None, help="bootstrap resamples (default 2000)")
    report.set_defaults(func=cmd_report)

    store = sub.add_parser("store", help="load every run's graph.ttl into the pyoxigraph store")
    store.add_argument("runs_root", type=Path)
    store.add_argument("--path", type=Path, default=_runs_env() / ".oxigraph", help="store (default: $RUNS/.oxigraph)")
    store.set_defaults(func=cmd_store)

    sparql = sub.add_parser("sparql", help="run a read-only SPARQL query on the store; JSON out")
    sparql.add_argument("query_file", type=Path)
    sparql.add_argument("--run", help="restrict the default graph to one run id")
    sparql.add_argument("--path", type=Path, default=_runs_env() / ".oxigraph", help="store (default: $RUNS/.oxigraph)")
    sparql.set_defaults(func=cmd_sparql)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
