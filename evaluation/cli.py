"""`evaluate` command line: score a run, run the two baselines, compare corpora.

    evaluate score --run RUN --corpus CORPUS [--baseline ANSWER.json ...] [--reexec R.json] --out DIR
    evaluate rag-baseline --corpus CORPUS --out DIR [--model ALIAS] [--retrieval global|per_paper] [--k N]
    evaluate agent-baseline --corpus CORPUS --out DIR [--model ALIAS] [--sandbox ...] [--steps N] [--tokens N]
    evaluate compare REPORT [REPORT ...] --out DIR

Model calls go to the LiteLLM gateway ($LITELLM_BASE_URL, default http://127.0.0.1:4000/v1); the
key is read from $LITELLM_MASTER_KEY when a model is made and is never printed or written. `--model`
(default orch-model, the one model of every extractor and both baselines) is the model of the RAG
baseline's answering call, of the mapping call of both baselines and of the agent baseline's agent.
"""
from __future__ import annotations

import argparse
import json
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


def _question(args: argparse.Namespace) -> str:
    from .baselines.common import DEFAULT_QUESTION

    if args.question_file:
        return args.question_file.read_text(encoding="utf-8").strip()
    return args.question or DEFAULT_QUESTION


def _model(alias: str) -> tuple[Any, str]:
    """The pydantic-ai model for an alias, and the identity its cache keys use (the pinned weights for orch-model)."""
    from gold.llm import openai_model

    pinned = f"{ORCHESTRATOR['name']}@{ORCHESTRATOR['revision']}" if alias == ORCHESTRATOR["alias"] else alias
    return openai_model(alias), pinned


def _cache(args: argparse.Namespace, system: str) -> Any:
    from gold.llm import JsonlCache

    return JsonlCache(args.cache or args.out / f"{system}-calls.jsonl")


def cmd_score(args: argparse.Namespace) -> int:
    from .score import score, score_answers

    if args.run is None and not args.baseline:
        raise SystemExit("evaluate score: give --run and/or --baseline")
    result = (score(args.run, args.corpus, args.baseline, args.reexec) if args.run
              else score_answers(args.corpus, args.baseline))
    js, md = rep.write_report(result, args.out)
    print(f"wrote {js} and {md}")
    return 0


def cmd_rag(args: argparse.Namespace) -> int:
    from .baselines.rag import rag_baseline

    model, model_id = _model(args.model)
    answer = rag_baseline(args.corpus, model=model, model_id=model_id, question=_question(args), k=args.k,
                          mode=args.retrieval, max_chars=args.max_chars, cache=_cache(args, "rag-baseline"),
                          seed=args.seed)
    print(f"{_write_answer(answer, args.out)}: label={answer['label']} studies={len(answer['studies'])}")
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    from agent.cli import stop_on_sigterm
    from evidence.agentic.runner import AgentSettings, ResearchAgentRunner

    from .baselines.agent import BUDGET, agent_baseline

    stop_on_sigterm()
    settings = AgentSettings(model=args.model, temperature=args.temperature, seed=args.agent_seed,
                             sandbox_mode=args.sandbox, base_url=args.base_url,
                             agent_root=str(args.agent_root) if args.agent_root else None)
    runner = ResearchAgentRunner(settings, work_dir=args.out / "agent-runs")
    budget = {"steps": args.steps or BUDGET["steps"], "tokens": args.tokens or BUDGET["tokens"]}
    concept = json.loads(args.concept.read_text(encoding="utf-8")) if args.concept else None
    model, model_id = _model(args.model)
    try:
        answer = agent_baseline(args.corpus, runner=runner, model=model, model_id=model_id, question=_question(args),
                                concept=concept, budget=budget, cache=_cache(args, "agent-baseline"),
                                run_id=args.run_id)
    except RuntimeError as exc:  # already redacted (agent_baseline, common.cached_reply)
        print(f"FAIL {exc}")
        return 1
    print(f"{_write_answer(answer, args.out)}: label={answer['label']} studies={len(answer['studies'])} "
          f"agent exit={answer['agent']['exit_status']}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    reports = []
    for path in args.reports:
        path = path / "report.json" if path.is_dir() else path
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    js, md = rep.write_compare(rep.compare(reports), args.out)
    print(f"wrote {js} and {md}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evaluate", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="score a run (A, B, C, locate, cascade, cost, stability) and baseline answers")
    s.add_argument("--run", type=Path, help="run directory written by `evidence run`")
    s.add_argument("--corpus", type=Path, required=True, help="corpus directory with ground_truth.json")
    s.add_argument("--baseline", type=Path, action="append", default=[], help="a baseline's answer.json (repeatable)")
    s.add_argument("--reexec", type=Path, help="re-execution report (default: <run>/reexec.json if present)")
    s.add_argument("--out", type=Path, required=True)
    s.set_defaults(func=cmd_score)

    def common(q: argparse.ArgumentParser) -> None:
        q.add_argument("--corpus", type=Path, required=True, help="reads manifest.json and papers/ only")
        q.add_argument("--out", type=Path, required=True)
        q.add_argument("--model", default=DEFAULT_ALIAS,
                       help=f"LiteLLM alias of the answer and mapping calls and of the agent (default {DEFAULT_ALIAS})")
        q.add_argument("--question", help="default: the RAG factuality question")
        q.add_argument("--question-file", type=Path)
        q.add_argument("--cache", type=Path, help="JsonlCache file (default <out>/<system>-calls.jsonl)")
        q.add_argument("--seed", type=int, default=0, help="seed of the answer/mapping call")

    r = sub.add_parser("rag-baseline", help="BM25 passages + an answer with citations + the mapping call -> answer.json")
    common(r)
    r.add_argument("--retrieval", choices=("global", "per_paper"), default="global",
                   help="global: top k passages of the whole corpus (default); per_paper: top k of every paper "
                        "(every paper seen)")
    r.add_argument("--k", type=int, help="passages in all (global, default 8) or per paper (per_paper, default 2)")
    r.add_argument("--max-chars", type=int, default=1500, help="passage size limit")
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
    c.add_argument("--out", type=Path, required=True)
    c.set_defaults(func=cmd_compare)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)
