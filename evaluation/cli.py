"""`evaluate` command line: score a run, run the two baselines, compare corpora.

    evaluate score --run RUN --corpus CORPUS [--baseline ANSWER.json ...] [--reexec R.json] [--oracle O.json]
                   [--question-id ID] --out DIR
    evaluate oracle --protocol P --corpus CORPUS --out DIR
    evaluate rag-baseline --corpus CORPUS --out DIR [--model ALIAS] [--retrieval global|per_paper] [--k N]
                          [--oracle-passages] [--question-id ID]
    evaluate agent-baseline --corpus CORPUS --out DIR [--model ALIAS] [--sandbox ...] [--steps N] [--tokens N]
                            [--question-id ID]
    evaluate compare REPORT [REPORT ...] [--corpora DIR] --out DIR
    evaluate shift --base REPORT --variant REPORT --variant-json variant.json --out DIR
    evaluate benchmark REPORT [REPORT ...] --out DIR
    evaluate review --csv REVIEW.csv

`oracle` (synthesis on perfect evidence) and `rag-baseline --oracle-passages` (the baseline on the passages
needed to interpret the values) are diagnostics that read ground_truth.json; `score --oracle` attributes each system's
wrong studies to upstream or downstream errors with the oracle's answer.json. `score --question-id` names the question of
the default pack's questions.yaml the run and the answers answer (default its default question, the corpus's own);
its kind picks how B and C are scored. `rag-baseline --question-id` and `agent-baseline --question-id` answer that
question: its text is asked and its kind picks the answer.json shape (default: the default question, as before). The
BM25 baseline's answers say `system: bm25-answer-baseline` (spec section 6.1); the command keeps its name (D36).

`shift` (the controlled variant, F3/F4) and `benchmark` (the B11 record per extractor id) read report.json
files written by `score` (a directory holding one is accepted too).

Model calls go to the LiteLLM gateway ($LITELLM_BASE_URL, default http://127.0.0.1:4000/v1); the
key is read from $LITELLM_MASTER_KEY when a model is made and is never printed or written. `--model`
(default orch-model, the one model of every extractor and both baselines) is the model of the RAG
baseline's answering call, of the mapping call of both baselines and of the agent baseline's agent.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from agent.rundir import ORCHESTRATOR

from . import report as rep

DEFAULT_ALIAS = ORCHESTRATOR["alias"]  # the agent's model, so both baselines and the agent share one model


def _write_answer(answer: dict[str, Any], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "answer.json"
    path.write_text(json.dumps(answer, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")
    return path


def _question(args: argparse.Namespace) -> dict[str, Any]:
    """The baseline's question keyword: `question_id` (checked here, so a bad id stops before any call), else
    `question` from --question-file or --question, else the default question."""
    from .baselines.common import DEFAULT_QUESTION, kind_params

    if args.question_id is not None:
        if args.question or args.question_file:
            raise SystemExit(f"evaluate {args.cmd}: give --question-id or --question/--question-file, not both")
        try:
            kind_params(args.question_id)
        except ValueError as exc:
            raise SystemExit(f"evaluate {args.cmd}: {exc}") from None
        return {"question_id": args.question_id}
    if args.question_file:
        return {"question": args.question_file.read_text(encoding="utf-8").strip()}
    return {"question": args.question or DEFAULT_QUESTION}


def _model(alias: str) -> tuple[Any, str]:
    """The pydantic-ai model for an alias, and the identity its cache keys use (the pinned weights for orch-model)."""
    from modelcall import openai_model

    pinned = f"{ORCHESTRATOR['name']}@{ORCHESTRATOR['revision']}" if alias == ORCHESTRATOR["alias"] else alias
    return openai_model(alias), pinned


def _cache(args: argparse.Namespace, system: str) -> Any:
    from modelcall import JsonlCache

    return JsonlCache(args.cache or args.out / f"{system}-calls.jsonl")


def cmd_score(args: argparse.Namespace) -> int:
    from .score import score, score_answers

    if args.run is None and not args.baseline:
        raise SystemExit("evaluate score: give --run and/or --baseline")
    try:
        result = (score(args.run, args.corpus, args.baseline, args.reexec, args.oracle, args.question_id) if args.run
                  else score_answers(args.corpus, args.baseline, args.oracle, args.question_id))
    except ValueError as exc:   # an unknown question id, a run whose question cannot be told, or of another kind
        raise SystemExit(f"evaluate score: {exc}") from None
    # where corpus.json is, relative to the report, so the pair moves together (compare resolves it from there)
    result["corpus_dir"] = Path(os.path.relpath(args.corpus.resolve(), args.out.resolve())).as_posix()
    js, md = rep.write_report(result, args.out)
    print(f"wrote {js} and {md}")
    return 0


def cmd_oracle(args: argparse.Namespace) -> int:
    from .oracle import run

    out = run(args.protocol, args.corpus, args.out)
    answer = json.loads((out / "answer.json").read_text(encoding="utf-8"))
    print(f"{out}: label={answer['label']} studies={len(answer['studies'])}")
    return 0


def cmd_rag(args: argparse.Namespace) -> int:
    from .baselines.rag import ORACLE_SYSTEM, rag_baseline

    question = _question(args)
    model, model_id = _model(args.model)
    # the default cache file keeps the command's name (rag-baseline-calls.jsonl), not the system id
    # (bm25-answer-baseline): an old output folder's cached answering calls still hit (D36)
    cache_name = ORACLE_SYSTEM if args.oracle_passages else args.cmd
    if args.oracle_passages and (args.k is not None or args.retrieval != "global" or args.max_chars != 1500):
        raise SystemExit("evaluate rag-baseline: --oracle-passages takes no --k, --retrieval or --max-chars")
    answer = rag_baseline(args.corpus, model=model, model_id=model_id, **question, k=args.k,
                          mode=args.retrieval, max_chars=args.max_chars, cache=_cache(args, cache_name),
                          seed=args.seed, oracle=args.oracle_passages, max_tokens=args.max_tokens)
    print(f"{_write_answer(answer, args.out)}: {_summary(answer)}")
    return 0


def _summary(answer: dict[str, Any]) -> str:
    """One line about a baseline's answer: the label of an effect answer, else the kind and its winner or size."""
    if "kind" not in answer:
        return f"label={answer['label']} studies={len(answer['studies'])}"
    if answer["kind"] == "inventory":
        return f"kind=inventory entries={len(answer['entries'])}"
    winner = f" winner={answer['winner']}" if answer["kind"] == "best" else ""
    return f"kind={answer['kind']}{winner} studies={len(answer['studies'])}"


def cmd_agent(args: argparse.Namespace) -> int:
    from agent.cli import stop_on_sigterm
    from evidence.agentic.runner import AgentSettings, ResearchAgentRunner

    from .baselines.agent import BUDGET, agent_baseline

    question = _question(args)
    stop_on_sigterm()
    settings = AgentSettings(model=args.model, temperature=args.temperature, seed=args.agent_seed,
                             sandbox_mode=args.sandbox, base_url=args.base_url,
                             agent_root=str(args.agent_root) if args.agent_root else None)
    runner = ResearchAgentRunner(settings, work_dir=args.out / "agent-runs")
    budget = {"steps": args.steps or BUDGET["steps"], "tokens": args.tokens or BUDGET["tokens"]}
    concept = json.loads(args.concept.read_text(encoding="utf-8")) if args.concept else None
    model, model_id = _model(args.model)
    try:
        answer = agent_baseline(args.corpus, runner=runner, model=model, model_id=model_id, **question,
                                concept=concept, budget=budget, cache=_cache(args, "agent-baseline"),
                                run_id=args.run_id)
    except RuntimeError as exc:  # already redacted (agent_baseline, common.cached_reply)
        print(f"FAIL {exc}")
        return 1
    print(f"{_write_answer(answer, args.out)}: {_summary(answer)} agent exit={answer['agent']['exit_status']}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    reports = []
    for path in args.reports:
        path = path / "report.json" if path.is_dir() else path
        reports.append({**json.loads(path.read_text(encoding="utf-8")), "_report_dir": str(path.parent)})
    js, md = rep.write_compare(rep.compare(reports, args.corpora), args.out)
    print(f"wrote {js} and {md}")
    return 0


def _report(path: Path) -> dict[str, Any]:
    path = path / "report.json" if path.is_dir() else path
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_shift(args: argparse.Namespace) -> int:
    from .shift import shift, write_shift

    spec = json.loads(args.variant_json.read_text(encoding="utf-8"))
    try:
        result = shift(_report(args.base), _report(args.variant), spec)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    js, md = write_shift(result, args.out)
    verdict = ", ".join(f"{s['system']}={'yes' if s['shifted_as_expected'] else 'no'}" for s in result["systems"])
    print(f"wrote {js} and {md}: shifted as expected: {verdict or 'no system in both reports'}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from .benchmark import benchmark, write_benchmark

    records = benchmark([_report(p) for p in args.reports])
    if not records:
        raise SystemExit("evaluate benchmark: no report has an `extractors` section (score a run, not answers only)")
    paths = write_benchmark(records, args.out)
    print(f"wrote {len(paths) - 1} benchmark.json record(s) and {paths[-1]}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from .review import render, summarise

    try:
        summary = summarise(args.csv)
    except ValueError as exc:
        raise SystemExit(f"evaluate review: {exc}") from None
    print(render(summary))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evaluate", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="score a run (A, B, C, locate, cascade, cost, stability) and baseline answers")
    s.add_argument("--run", type=Path, help="run directory written by `evidence run`")
    s.add_argument("--corpus", type=Path, required=True, help="corpus directory with ground_truth.json")
    s.add_argument("--baseline", type=Path, action="append", default=[], help="a baseline's answer.json (repeatable)")
    s.add_argument("--reexec", type=Path, help="re-execution report (default: <run>/reexec.json if present)")
    s.add_argument("--oracle", type=Path, help="an oracle's answer.json: attribute wrong studies upstream/downstream")
    s.add_argument("--question-id",
                   help="the question id (domains/rag/questions.yaml) the run and the answers answer; its kind picks B "
                        "and C (default: the question the run's protocol asks, else the one every --baseline "
                        "answer asks; refused when that cannot be told, and an unknown id is refused)")
    s.add_argument("--out", type=Path, required=True)
    s.set_defaults(func=cmd_score)

    o = sub.add_parser("oracle", help="diagnostic: the protocol's synthesis on the ground truth's facts -> a run dir")
    o.add_argument("--protocol", type=Path, required=True)
    o.add_argument("--corpus", type=Path, required=True, help="corpus directory with ground_truth.json")
    o.add_argument("--out", type=Path, required=True, help="the run directory to write")
    o.set_defaults(func=cmd_oracle)

    def common(q: argparse.ArgumentParser) -> None:
        q.add_argument("--corpus", type=Path, required=True, help="reads manifest.json and papers/ only")
        q.add_argument("--out", type=Path, required=True)
        q.add_argument("--model", default=DEFAULT_ALIAS,
                       help=f"LiteLLM alias of the answer and mapping calls and of the agent (default {DEFAULT_ALIAS})")
        q.add_argument("--question", help="default: the default pack's default question")
        q.add_argument("--question-file", type=Path)
        q.add_argument("--question-id", help="a question id of domains/rag/questions.yaml: its text is asked and "
                       "its kind picks the answer's shape (not with --question or --question-file; default: the "
                       "default pack's default question)")
        q.add_argument("--cache", type=Path, help="JsonlCache file (default <out>/<name>-calls.jsonl, name "
                       "rag-baseline, rag-oracle-passages or agent-baseline)")
        q.add_argument("--seed", type=int, default=0, help="seed of the answer/mapping call")

    r = sub.add_parser("rag-baseline", help="BM25 passages + an answer with citations + the mapping call -> answer.json")
    common(r)
    r.add_argument("--retrieval", choices=("global", "per_paper"), default="global",
                   help="global: top k passages of the whole corpus (default); per_paper: top k of every paper "
                        "(every paper seen)")
    r.add_argument("--k", type=int, help="passages in all (global, default 8) or per paper (per_paper, default 2)")
    r.add_argument("--max-chars", type=int, default=1500, help="passage size limit")
    r.add_argument("--max-tokens", type=int, help="answer call's token limit (default 4096 global, 16384 per_paper)")
    r.add_argument("--oracle-passages", action="store_true",
                   help="diagnostic: the paragraphs needed to interpret the true values instead of BM25 (reads "
                        "ground_truth.json); --k, --retrieval and --max-chars do not apply and are rejected")
    r.set_defaults(func=cmd_rag)

    a = sub.add_parser("agent-baseline", help="the research agent with the question only -> answer.json")
    common(a)
    a.add_argument("--sandbox", choices=("landlock", "unsandboxed"), default="landlock")
    a.add_argument("--agent-root", type=Path, help="pinned toolchain ($AGENT_ROOT)")
    a.add_argument("--base-url", default="http://127.0.0.1:4000/v1", help="LiteLLM proxy for the agent")
    a.add_argument("--temperature", type=float, default=0.7)
    a.add_argument("--agent-seed", type=int, default=1234)
    a.add_argument("--steps", type=int)
    a.add_argument("--tokens", type=int)
    a.add_argument("--concept", type=Path, help="a picked concept brief instead of the question-only one")
    a.add_argument("--run-id", default="agent-baseline")
    a.set_defaults(func=cmd_agent)

    c = sub.add_parser("compare", help="per-level table over several corpora's report.json")
    c.add_argument("reports", type=Path, nargs="+", help="report.json files or directories holding one")
    c.add_argument("--corpora", type=Path, help="directory holding the corpus directories, where a report's own "
                   "corpus path is dead (Selection and Matched read corpus.json)")
    c.add_argument("--out", type=Path, required=True)
    c.set_defaults(func=cmd_compare)

    sh = sub.add_parser("shift", help="a counterfactual variant: did the answer shift as variant.json predicts")
    sh.add_argument("--base", type=Path, required=True, help="report.json of the base corpus (or its directory)")
    sh.add_argument("--variant", type=Path, required=True, help="report.json of the variant corpus (or its directory)")
    sh.add_argument("--variant-json", type=Path, required=True, help="variant.json written by `synth variant`")
    sh.add_argument("--out", type=Path, required=True)
    sh.set_defaults(func=cmd_shift)

    b = sub.add_parser("benchmark", help="the B11 benchmark record per extractor id, pooled over reports")
    b.add_argument("reports", type=Path, nargs="+", help="report.json files or directories holding one")
    b.add_argument("--out", type=Path, required=True, help="writes <out>/<extractor_id>/benchmark.json and benchmark.md")
    b.set_defaults(func=cmd_benchmark)

    rv = sub.add_parser("review", help="summarise a filled-in fidelity review sheet (synth review CSV)")
    rv.add_argument("--csv", type=Path, required=True, help="review-s<seed>.csv with the three checks ticked yes/no")
    rv.set_defaults(func=cmd_review)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)
