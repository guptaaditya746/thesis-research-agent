"""`agent` command line."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import kg
from .canonical import canonical, file_sha256, sha256_hex
from .chain import verify
from .rundir import RunDir


def cmd_check_run(args: argparse.Namespace) -> int:
    problems = RunDir(args.run_dir).validate(complete=args.complete)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print(f"PASS {args.run_dir}")
    return 1 if problems else 0


def cmd_verify_chain(args: argparse.Namespace) -> int:
    run = RunDir(args.run_dir)
    report = verify(run.events, run.claims, head=args.head)
    for error in report.errors:
        print(f"FAIL {error}")
    if report.ok:
        print(f"PASS records={report.records} claims={report.claims} head={report.head}")
    return 0 if report.ok else 1


def _corpus_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--corpus", type=Path, default=os.environ.get("CORPUS"),
                        help="frozen corpus directory (default: $CORPUS)")
    parser.add_argument("--manifest", type=Path, help="corpus manifest (default: <corpus>/manifest.json)")


def _corpus(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.corpus is None:
        raise SystemExit("agent: give --corpus or set $CORPUS")
    return Path(args.corpus), Path(args.manifest or Path(args.corpus) / "manifest.json")


def cmd_run(args: argparse.Namespace) -> int:
    from .loop import research_run  # imports LiteLLM and mini-swe-agent: slow, so only here
    from .rundir import BUDGET, git_head

    corpus, manifest = _corpus(args)
    concept = json.loads(args.concept.read_text(encoding="utf-8"))
    agent_root_sha = (file_sha256(args.agent_root / "agent-root.sha256") if args.agent_root
                      else sha256_hex(b""))  # no agent root (tests, laptops): hash of nothing
    _, outcome, head = research_run(
        runs_root=args.runs_root, run_id=args.run_id, concept=concept, corpus=corpus, manifest=manifest,
        condition=args.condition, temperature=args.temperature, seed=args.seed,
        git_commit=git_head(Path(__file__).resolve().parents[1]), agent_root_manifest_sha256=agent_root_sha,
        sandbox_mode=args.sandbox, agent_root=args.agent_root, base_url=args.base_url,
        budget={**BUDGET, "steps": args.steps, "tokens": args.tokens}, broker=args.broker, extra_path=tuple(args.path_extra))
    print(f"run {args.run_id}: exit={outcome.exit_status} steps={outcome.steps} tokens={outcome.tokens} "
          f"rows={outcome.answer_rows} head={head.get('head')}")
    return 0 if outcome.exit_status == "submitted" else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from .verify import verify_run

    corpus, manifest = _corpus(args)
    report = verify_run(RunDir(args.run_dir), corpus, manifest)
    for error in report.errors:
        print(f"FAIL {error}")
    s = report.stats
    print(f"steps={s.get('steps', 0)} model_calls={s.get('model_calls', 0)} commands={s.get('commands', 0)} "
          f"claims={s.get('claims_accepted', 0)} accepted / {s.get('claims_rejected', 0)} rejected "
          f"claim_steps={s.get('claim_steps', 0)} tokens={s.get('tokens', 0)} "
          f"(claim steps {s.get('claim_step_tokens', 0)}) time={s.get('seconds', 0)}s "
          f"facts={s.get('facts', 0)} (with claims {s.get('facts_with_claims', 0)})")
    if report.ok:
        print(f"PASS {args.run_dir} records={s.get('records')} head={s.get('head')}")
    return 0 if report.ok else 1


def cmd_pairs(args: argparse.Namespace) -> int:
    from .pairs import write_pairs

    n = write_pairs(RunDir(args.run_dir))
    print(f"wrote {n} pairs to {args.run_dir / 'pairs.jsonl'}")
    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    from .timeline import write_timeline

    print(f"wrote {write_timeline(RunDir(args.run_dir))}")
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    try:
        path, graph = kg.write(RunDir(args.run_dir), args.manifest)
    except (OSError, ValueError, KeyError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(f"PASS edges={len(graph['edges'])} nodes={len(graph['nodes'])} -> {path}")
    return 0


def cmd_export_prov(args: argparse.Namespace) -> int:
    from . import prov  # rdflib loads slowly; only these subcommands need it

    try:
        path, graph = prov.write(RunDir(args.run_dir))
    except (OSError, ValueError, KeyError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(f"PASS triples={len(graph)} -> {path}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    from . import prov, queries

    run = RunDir(args.run_dir)
    if not (run.root / prov.TTL_FILE).is_file():
        print(f"FAIL {run.root / prov.TTL_FILE} is missing; run `agent export-prov` first")
        return 1
    graph = prov.load(run)
    try:
        if args.n == 1:
            rows = queries.edge_to_passage(graph, args.edge)
        elif args.n == 2:
            rows = queries.fact_producers(graph, args.fact, args.claim)
        elif args.n == 3:
            rows = queries.claims_from(graph, args.step, args.agent)
        elif args.n == 4:
            rows = queries.unresolved_anchors(graph, args.corpus, args.manifest)
        else:
            rows = queries.unsourced_facts(graph)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}")
        return 1
    for row in rows:
        print(canonical(row))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent")
    sub = parser.add_subparsers(dest="command", required=True)
    chain = sub.add_parser("verify-chain", help="verify the hash chain of events.jsonl and claims.jsonl")
    chain.add_argument("run_dir", type=Path)
    chain.add_argument("--head", help="expected chain head, e.g. from the broker's line in the Slurm log")
    chain.set_defaults(func=cmd_verify_chain)
    check = sub.add_parser("check-run", help="validate a run directory's layout and config")
    check.add_argument("run_dir", type=Path)
    check.add_argument("--complete", action="store_true", help="also require answer.json")
    check.set_defaults(func=cmd_check_run)

    run = sub.add_parser("run", help="run the agent on one concept (row 1.8)")
    run.add_argument("--concept", type=Path, required=True, help="concept brief JSON, e.g. agent/concepts/*.json")
    run.add_argument("--run-id", required=True)
    run.add_argument("--runs-root", type=Path, default=Path("runs"))
    _corpus_args(run)
    run.add_argument("--condition", choices=("claim_on", "claim_off"), default="claim_on")
    run.add_argument("--temperature", type=float, required=True)
    run.add_argument("--seed", type=int, required=True)
    run.add_argument("--base-url", default="http://127.0.0.1:4000/v1", help="LiteLLM proxy; key from $LITELLM_MASTER_KEY")
    run.add_argument("--sandbox", choices=("landlock", "unsandboxed"), default="landlock",
                     help="unsandboxed runs commands without Landlock/seccomp: tests and machines without Landlock only")
    run.add_argument("--agent-root", type=Path, help="pinned toolchain ($AGENT_ROOT); its agent-root.sha256 is hashed")
    run.add_argument("--steps", type=int, default=150)
    run.add_argument("--tokens", type=int, default=400_000)
    run.add_argument("--broker", choices=("auto", "process", "inprocess"), default="auto")
    run.add_argument("--path-extra", action="append", default=[], help="extra directory on the sandbox PATH")
    run.set_defaults(func=cmd_run)

    ver = sub.add_parser("verify", help="verify a finished run: chain, anchors, answer claim ids (row 1.11)")
    ver.add_argument("run_dir", type=Path)
    _corpus_args(ver)
    ver.set_defaults(func=cmd_verify)

    pairs = sub.add_parser("pairs", help="write pairs.jsonl: answer facts with their claims' quotes (row 1.12)")
    pairs.add_argument("run_dir", type=Path)
    pairs.set_defaults(func=cmd_pairs)

    timeline = sub.add_parser("timeline", help="write timeline.html: the run's steps as static HTML (row 1.14)")
    timeline.add_argument("run_dir", type=Path)
    timeline.set_defaults(func=cmd_timeline)

    graph = sub.add_parser("graph", help="claims (both origins) -> knowledge graph graph.json")
    graph.add_argument("run_dir", type=Path)
    graph.add_argument("--manifest", type=Path, default=Path("corpus/manifest.json"))
    graph.set_defaults(func=cmd_graph)
    export = sub.add_parser("export-prov", help="events, claims and graph.json -> PROV-O graph.ttl")
    export.add_argument("run_dir", type=Path)
    export.set_defaults(func=cmd_export_prov)
    query = sub.add_parser("query", help="provenance queries 1-5 on graph.ttl; one JSON object per result")
    query.add_argument("n", type=int, choices=range(1, 6), metavar="N",
                       help="1 edge->passage, 2 fact->command+model call, 3 claims of a step/agent, "
                            "4 anchors that no longer resolve, 5 facts with no claim")
    query.add_argument("run_dir", type=Path)
    query.add_argument("--edge", help="query 1: one KG edge id, e.g. edge-000001")
    query.add_argument("--fact", help="query 2: one answer fact id, e.g. f1")
    query.add_argument("--claim", help="query 2: one claim id, e.g. claim-000001")
    query.add_argument("--step", type=int, help="query 3: step id")
    query.add_argument("--agent", help="query 3: agent id, e.g. main or sub-01")
    query.add_argument("--corpus", type=Path, default=Path("corpus"), help="query 4: corpus directory")
    query.add_argument("--manifest", type=Path, default=Path("corpus/manifest.json"), help="query 4")
    query.set_defaults(func=cmd_query)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
