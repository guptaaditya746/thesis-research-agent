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
    evaluate losses --scores DIR --out DIR
    evaluate review --csv REVIEW.csv
    evaluate scirex corpus --jsonl F --out DIR [--limit N]
    evaluate scirex score --run R --corpus C --out D [--estimate ESTIMATE.json]
    evaluate scilead ids --data DIR --out ids.txt
    evaluate scilead score --run R --corpus C --data DIR --out D
    evaluate yun corpus --repo DIR --ei DIR --out C
    evaluate yun score --run R --corpus C --out D
    evaluate edits apply --corpus C --edits F --out DIR
    evaluate edits check --original R --runs DIR --edits F --out D [--corpora DIR]
    evaluate sheet --run R --corpus C (--sample N | --papers N) [--seed 0] --out F.csv
    evaluate sheet-summary F.csv [--out D]
    evaluate wholerun --set scilead|scirex|cochraneforest|sofc --src DIR --runs DIR --out DIR [--corpus DIR]
                      [--confirm auto|hand|both] [--reasoning on|off|both] [--system engine|rag|both]
                      [--sample 10] [--seed 0] [--model ALIAS] [--cache F]
    evaluate tune-split --set S --src DIR [--corpus DIR] [--fraction 0.2] [--seed 0]
    evaluate leak --run R --corpus C [--tuned-dir DIR] [--corpora DIR ...] --out D
    evaluate offtemplate --runs DIR --out D
    evaluate links --run R [--corpus C --question-id ID] [--references F.json | --build-references] --out D

`wholerun` (evaluation/wholerun_cmd.py) scores the plan runs of one real set under `--runs`
(<runs>/<auto-confirmed|hand-confirmed>/<on|off>/<question id>/): two confirmation rows, both reasoning settings, a
fixed sample (sample.json), the RAG baseline (global and per_paper, same model) beside them with wins, losses, ties
and the paired interval, the line "left out: N of M (no open full text)", and how many questions got a fresh query.
It starts no run. `leak` splits extraction recall into "on the list" and "unseen" (Claude-written corpora only).
`offtemplate` reports the fresh-query share and the match rate of the 12 off-template questions
(<runs>/<question id>/plan.json). `links` scores chaining with the existing scorer and builds-on by recall of OpenAlex
references (`--references`: {paper id: [work ids]}).

`oracle` (synthesis on perfect evidence) and `rag-baseline --oracle-passages` (the baseline on the passages
needed to interpret the values) are diagnostics that read ground_truth.json; `score --oracle` attributes each system's
wrong studies to upstream or downstream errors with the oracle's answer.json. `score --question-id` names the question of
the default pack's questions.yaml the run and the answers answer (default its default question, the corpus's own);
its kind picks how B and C are scored. `rag-baseline --question-id` and `agent-baseline --question-id` answer that
question: its text is asked and its kind picks the answer.json shape (default: the default question, as before). The
BM25 baseline's answers say `system: bm25-answer-baseline` (spec section 6.1); the command keeps its name (D36).

`scirex` is a real-paper check (D21, evaluation/realpapers/scirex.py): `corpus` turns SciREX JSON lines into a corpus
plus the gold only `score` reads; `score` writes real.json and real.md, never a report.json. `--limit` is chosen with
`evidence estimate` on the corpus; give its saved output as `--estimate` so real.md reports it.

`scilead` is a real-paper check (D42, evaluation/realpapers/scilead.py) on the unpacked SciLead release (`--data`):
`ids` writes the papers' arXiv ids for `evidence fetch --ids` and prints the papers with none; `score` scores a run
of domains/ml/protocols/values.yaml on the fetched corpus: values found and linked, "best" per leaderboard and
pairwise order, in real.json and real.md.

`yun` is a real-paper check (D42, evaluation/realpapers/yun.py) on Yun et al. 2024 and Evidence Inference 2.0:
`corpus` turns a checkout of hyesunyun/llm-meta-analysis (`--repo`) and Evidence Inference's annotations/ folder
(`--ei`) into a corpus plus the gold only `score` reads; `score` scores a drug-trials run (its comparisons.json) on
A names, A values, B and C separately, in real.json and real.md.

`edits` is the arXiv edit test (spec 6.12 item 3, evaluation/realpapers/edits.py): `apply` writes one corpus per
edit of the edits file (`DIR/<edit id>`); run the engine on each with `--run-id <edit id>` under one folder, then
`check` compares the original run with `DIR/<edit id>` per edit (item, link, answer) into real.json and real.md.
`sheet` writes a hand-check CSV of a run's items with their source sentences (N random items, or every item of the
first N papers); `sheet-summary` prints the marked rows' precision with its Wilson 95% interval and, with `--out`,
writes real.json and real.md labelled "demonstration, not an evaluation".

`shift` (the controlled variant, F3/F4) and `benchmark` (the B11 record per extractor id) read report.json
files written by `score` (a directory holding one is accepted too).

`losses` (spec 6.16, evaluation/losses.py) reads every report.json one or two folders under `--scores` and writes
losses.json and losses.md: per domain, each question's headline per system with its model calls and tokens, the
engine's losses first, each with one cause. The web app reads them from `<scores root>/losses/`.

Model calls go to the LiteLLM gateway ($LITELLM_BASE_URL, default http://127.0.0.1:4000/v1); the
key is read from $LITELLM_MASTER_KEY when a model is made and is never printed or written. `--model`
(default orch-model, the one model of every extractor and both baselines) is the model of the RAG
baseline's answering call, of the mapping call of both baselines and of the agent baseline's agent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from agent.rundir import ORCHESTRATOR

from . import report as rep
from .realpapers import SETS, WHOLE_RUN_SETS, real_set

DEFAULT_ALIAS = ORCHESTRATOR["alias"]  # the agent's model, so both baselines and the agent share one model


def _write_answer(answer: dict[str, Any], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "answer.json"
    path.write_text(json.dumps(answer, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")
    return path


def _question(args: argparse.Namespace) -> dict[str, Any]:
    """The baseline's question keywords: `question_id` and the questions file of the pack that has it (checked
    here, so a bad id stops before any call), else
    `question` from --question-file or --question, else the default question."""
    from evidence.questions import find

    from .baselines.common import DEFAULT_QUESTION, kind_params

    if args.question_id is not None:
        if args.question or args.question_file:
            raise SystemExit(f"evaluate {args.cmd}: give --question-id or --question/--question-file, not both")
        try:
            _, questions = find(args.question_id)
            kind_params(args.question_id, questions)
        except ValueError as exc:
            raise SystemExit(f"evaluate {args.cmd}: {exc}") from None
        return {"question_id": args.question_id, "questions": questions}
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


def cmd_losses(args: argparse.Namespace) -> int:
    from .losses import losses, read_reports, write_losses

    reports = read_reports(args.scores)
    if not reports:
        raise SystemExit(f"evaluate losses: no report.json one or two folders under {args.scores}")
    try:
        result = losses(reports)
    except KeyError as exc:   # a new kind's score without its headline
        raise SystemExit(f"evaluate losses: {exc.args[0]}") from None
    js, md = write_losses(result, args.out)
    lost = sum(r["engine_loss"] for rows in result["domains"].values() for r in rows)
    print(f"wrote {js} and {md}: {len(reports)} report(s), {lost} engine loss(es)")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from .review import render, summarise

    try:
        summary = summarise(args.csv)
    except ValueError as exc:
        raise SystemExit(f"evaluate review: {exc}") from None
    print(render(summary))
    return 0


def cmd_real(args: argparse.Namespace) -> int:
    """`evaluate <set> <step>` of a real-paper set (realpapers.SETS): a prepare step prints what its adapter returns;
    a check step writes the adapter's result as real.json and real.md into --out."""
    from .realpapers.common import write_real

    rs = real_set(args.cmd)
    check = rs.check is not None and args.real_step == rs.check.name
    step = rs.check if check else rs.prepare
    assert step is not None
    run = rs.module().check_step if check else rs.module().prepare_step
    try:
        result = run(**{d: getattr(args, d) for d in step.dests if not (check and d == "out")})
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"evaluate {args.cmd} {args.real_step}: {exc}") from None
    if not check:
        print(result)
        return 0
    js, md = write_real(result, args.out, rs.title)
    print(json.dumps({"real_json": str(js), "real_md": str(md), **{k: result[k] for k in rs.summary}}))
    return 0


def cmd_sheet(args: argparse.Namespace) -> int:
    from .realpapers.sheet import sheet, write_sheet

    try:
        rows = sheet(args.run, args.corpus, sample=args.sample, papers=args.papers, seed=args.seed)
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"evaluate sheet: {exc}") from None
    print(json.dumps({"rows": len(rows), "out": str(write_sheet(rows, args.out))}))
    return 0


def cmd_sheet_summary(args: argparse.Namespace) -> int:
    from .realpapers.common import write_real
    from .realpapers.sheet import TITLE, summarise

    try:
        result = summarise(args.csv)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"evaluate sheet-summary: {exc}") from None
    if args.out:
        write_real({**result, "sheet": str(args.csv), "label": "demonstration, not an evaluation"}, args.out, TITLE)
    print(json.dumps(result))
    return 0


def cmd_tune_split(args: argparse.Namespace) -> int:
    """Hold out questions of one real set for tuning (written once to <corpus>/tune_split.json)."""
    from .wholerun import TUNE_FILE, tune_split_questions

    corpus = args.corpus if args.corpus is not None else Path(args.src) / "corpus"
    path = corpus / TUNE_FILE
    if path.exists():
        raise SystemExit(f"evaluate tune-split: {path} exists; it is written once (move it aside to redo)")
    questions = real_set(args.set).questions(args.src, args.corpus)
    split = tune_split_questions(questions, args.fraction, args.seed, path)
    from .wholerun import question_papers
    gave = sum(1 for q in questions if q.id in split["questions"] and set(question_papers(q)) & set(split["papers"]))
    print(f"wrote {path}: kept {len(split['kept_questions'])} questions, held {len(split['questions'])} for tuning "
          f"({gave} of them give papers to the slice; {len(split['papers'])} papers held out, {len(split['rest'])} rest). "
          "A held question whose papers all belong to kept questions is still scored by `evaluate wholerun`.")
    return 0


def cmd_wholerun(args: argparse.Namespace) -> int:
    from . import wholerun_cmd as wc

    rs = real_set(args.set)
    questions = rs.questions(args.src, args.corpus)
    confirm = {"auto": ("auto-confirmed",), "hand": ("hand-confirmed",)}.get(args.confirm, wc.CONFIRMATIONS)
    reasoning = ("on", "off") if args.reasoning == "both" else (args.reasoning,)
    systems = ("engine", "rag") if args.system == "both" else (args.system,)
    rag = None
    if "rag" in systems:
        from modelcall import JsonlCache

        from .baselines.real import rag_real
        model, model_id = _model(args.model)
        cache = JsonlCache(args.cache or args.out / "rag-real-calls.jsonl")

        def rag(q: Any, mode: str) -> Any:   # the engine's corpus and model are the question's own
            return rag_real(q, model=model, model_id=model_id, mode=mode, engine_corpus=q.corpus_dir,
                            engine_model_id=model_id, cache=cache, seed=args.seed)
    try:
        report = wc.wholerun(questions, args.runs, args.out, set_name=args.set, n=args.sample, seed=args.seed,
                             left_out=rs.left_out(args.src, args.corpus, questions), reasoning=reasoning,
                             confirm=confirm, systems=systems, rag_answer=rag, rag_model=args.model)
    except (ValueError, FileNotFoundError) as exc:   # a refused run, or a corpus manifest that is not there
        print(f"evaluate wholerun: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.out / 'wholerun.json'}: {len(report['sample']['ids'])} questions; {report['left_out']}")
    return 0


def cmd_leak(args: argparse.Namespace) -> int:
    from . import wholerun_cmd as wc

    try:
        split = wc.leak(args.run, args.corpus, args.out, tuned_dir=args.tuned_dir, corpora=args.corpora)
    except ValueError as exc:
        raise SystemExit(f"evaluate leak: {exc}") from None
    print(f"wrote {args.out / 'leak.json'}: " + "; ".join(f"{k} recall={v['recall']}" for k, v in split.items()))
    return 0


def cmd_offtemplate(args: argparse.Namespace) -> int:
    from . import wholerun_cmd as wc

    report = wc.offtemplate(args.runs, args.out)
    print(f"wrote {args.out / 'offtemplate.json'}: {report['summary']}")
    return 0


def cmd_links(args: argparse.Namespace) -> int:
    from . import wholerun_cmd as wc

    try:
        result = wc.links(args.run, args.out, corpus=args.corpus, question_id=args.question_id,
                          references=args.references, build=args.build_references)
    except ValueError as exc:
        raise SystemExit(f"evaluate links: {exc}") from None
    status = (result.get("builds_on") or {}).get("status")
    print(f"wrote {args.out / 'links.json'}" + (f": {status}" if status else ""))
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
                   help="the question id (any pack's domains/<pack>/questions.yaml) the run and the answers answer; its kind picks B "
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
        q.add_argument("--question-id", help="a question id of any pack's domains/<pack>/questions.yaml: its text is asked and "
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

    lo = sub.add_parser("losses", help="the losses-first table: per domain, each question's headline and cost per "
                                       "system, the engine's losses first with their cause")
    lo.add_argument("--scores", type=Path, required=True,
                    help="the scores root: every <group>/report.json and <group>/<name>/report.json under it")
    lo.add_argument("--out", type=Path, required=True, help="writes <out>/losses.json and losses.md "
                                                            "(the web app reads <scores root>/losses/)")
    lo.set_defaults(func=cmd_losses)

    rv = sub.add_parser("review", help="summarise a filled-in fidelity review sheet (synth review CSV)")
    rv.add_argument("--csv", type=Path, required=True, help="review-s<seed>.csv with the three checks ticked yes/no")
    rv.set_defaults(func=cmd_review)

    for rs in SETS.values():   # the real-paper sets with steps: `evaluate <set> <step>` (realpapers.SETS)
        steps = [st for st in (rs.prepare, rs.check) if st is not None]
        if not steps:
            continue
        rsub = sub.add_parser(rs.name, help=rs.help).add_subparsers(dest="real_step", required=True)
        for st in steps:
            sp = rsub.add_parser(st.name, help=st.help)
            for flag, kw in st.args:
                sp.add_argument(flag, **kw)
            sp.set_defaults(func=cmd_real)

    sh2 = sub.add_parser("sheet", help="a hand-check CSV: items with their source sentences, to mark right or wrong")
    sh2.add_argument("--run", type=Path, required=True, help="run directory written by `evidence run`")
    sh2.add_argument("--corpus", type=Path, required=True, help="the run's corpus (manifest.json and papers/)")
    pick = sh2.add_mutually_exclusive_group(required=True)
    pick.add_argument("--sample", type=int, help="N random items of the run")
    pick.add_argument("--papers", type=int, help="every item of the first N papers in manifest order")
    sh2.add_argument("--seed", type=int, default=0, help="seed of --sample (default 0)")
    sh2.add_argument("--out", type=Path, required=True, help="the CSV to write")
    sh2.set_defaults(func=cmd_sheet)

    ssum = sub.add_parser("sheet-summary", help="precision of a marked hand-check sheet, with its Wilson 95%% interval")
    ssum.add_argument("csv", type=Path, help="the sheet with right_or_wrong filled in (blank rows are not counted)")
    ssum.add_argument("--out", type=Path, help="also write real.json and real.md (demonstration, not an evaluation)")
    ssum.set_defaults(func=cmd_sheet_summary)

    w = sub.add_parser("wholerun", help="score the plan runs of one real set, with the RAG baseline beside them")
    w.add_argument("--set", choices=WHOLE_RUN_SETS, required=True)
    w.add_argument("--src", type=Path, required=True, help="the set's source (release) folder")
    w.add_argument("--runs", type=Path, required=True, help="<runs>/<auto-confirmed|hand-confirmed>/<on|off>/<qid>/; the hand row is the first 5 questions of sample.json")
    w.add_argument("--corpus", type=Path, help="the set's corpus folder (default <src>/corpus)")
    w.add_argument("--confirm", choices=("auto", "hand", "both"), default="both")
    w.add_argument("--reasoning", choices=("on", "off", "both"), default="both")
    w.add_argument("--system", choices=("engine", "rag", "both"), default="both")
    w.add_argument("--sample", type=int, default=10, help="questions in the fixed sample (default 10)")
    w.add_argument("--seed", type=int, default=0)
    w.add_argument("--model", default=DEFAULT_ALIAS, help="the RAG baseline's model: the engine's (default orch-model)")
    w.add_argument("--cache", type=Path, help="JsonlCache file of the RAG calls (default <out>/rag-real-calls.jsonl)")
    w.add_argument("--out", type=Path, required=True)
    w.set_defaults(func=cmd_wholerun)

    ts = sub.add_parser("tune-split", help="hold out whole questions of a real set for tuning (tune_split.json)")
    ts.add_argument("--set", choices=WHOLE_RUN_SETS, required=True)
    ts.add_argument("--src", type=Path, required=True, help="the set's source (release) folder")
    ts.add_argument("--corpus", type=Path, help="the set's corpus folder (default <src>/corpus); gets tune_split.json")
    ts.add_argument("--fraction", type=float, default=0.2)
    ts.add_argument("--seed", type=int, default=0)
    ts.set_defaults(func=cmd_tune_split)

    lk = sub.add_parser("leak", help="extraction recall split: names on the word list vs unseen")
    lk.add_argument("--run", type=Path, required=True, help="a plan run (its plan.json holds the word list)")
    lk.add_argument("--corpus", type=Path, required=True, help="a Claude-written corpus with ground_truth.json")
    lk.add_argument("--tuned-dir", type=Path, help="the tuned steps' folder (default evidence/steps/tuned); the run is "
                    "refused when a tuned word writer saw corpora that share condition names with --corpus")
    lk.add_argument("--corpora", type=Path, action="append", default=[],
                    help="a folder holding the corpora the tuned files list (repeatable; default tests/EV2/corpora)")
    lk.add_argument("--out", type=Path, required=True)
    lk.set_defaults(func=cmd_leak)

    ot = sub.add_parser("offtemplate", help="the generality check: fresh-query share and off-template match rate")
    ot.add_argument("--runs", type=Path, required=True, help="<runs>/<question id>/plan.json per off-template question")
    ot.add_argument("--out", type=Path, required=True)
    ot.set_defaults(func=cmd_offtemplate)

    ln = sub.add_parser("links", help="chaining against the synthetic truth network; builds-on by OpenAlex references")
    ln.add_argument("--run", type=Path, required=True)
    ln.add_argument("--corpus", type=Path, help="the synthetic corpus (chaining)")
    ln.add_argument("--question-id", help="the chaining question's id (chaining)")
    ln.add_argument("--references", type=Path, help="JSON {paper id: [OpenAlex work ids]} (builds-on)")
    ln.add_argument("--build-references", action="store_true",
                    help="build <out>/openalex-references.json from the run's recorded openalex.jsonl (offline; needs "
                    "--corpus) and score builds-on with it")
    ln.add_argument("--out", type=Path, required=True)
    ln.set_defaults(func=cmd_links)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)
