"""`agent` command line."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import kg
from jsonio import canonical, file_sha256, sha256_hex
from .chain import verify
from .rundir import BUDGET as RUN_BUDGET, BUDGET_M1 as RUN_BUDGET_M1, RunDir

DECODING_CHOICES = ("structured_outputs", "guided_json", "free")  # loop.DECODINGS, without importing the loop


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


def stop_on_sigterm() -> None:
    """SIGTERM (the batch runner or Slurm at the job limit, row 2.9) ends the run cleanly (agent/stopping.py)."""
    from . import stopping

    stopping.install()


def cmd_run(args: argparse.Namespace) -> int:
    import dataclasses

    from .loop import budget_for, research_run, settings_for  # imports LiteLLM and mini-swe-agent: slow, so only here
    from .rundir import git_head
    from .spawn import SpawnSettings

    stop_on_sigterm()

    corpus, manifest = _corpus(args)
    concept = json.loads(args.concept.read_text(encoding="utf-8"))
    agent_root_sha = (file_sha256(args.agent_root / "agent-root.sha256") if args.agent_root
                      else sha256_hex(b""))  # no agent root (tests, laptops): hash of nothing
    settings = settings_for(args.prompt_version)  # v1: the loop of the M1-real runs
    if args.conclude_decoding:
        settings = dataclasses.replace(settings, conclude_decoding=args.conclude_decoding)
    budget = budget_for(args.prompt_version)  # v1: the M1-real runs' 150 steps / 400k tokens
    budget |= {k: v for k, v in (("steps", args.steps), ("tokens", args.tokens)) if v is not None}
    spawn_budget = {k: v for k, v in (("steps", args.spawn_steps), ("tokens", args.spawn_tokens)) if v is not None}
    if spawn_budget and args.spawn != "on":
        print("FAIL --spawn-steps and --spawn-tokens need --spawn on")
        return 1
    try:  # each subagent's budget: provisional, like the run's (frozen after the Slurm test)
        spawn = SpawnSettings(enabled=args.spawn == "on", **spawn_budget)
    except ValueError as exc:
        print(f"FAIL {exc}")
        return 1
    if spawn.enabled:
        from . import prompts
        try:  # v1 (the M1-real runs) has no spawn block
            prompts.load(args.prompt_version, args.condition, spawn=True)
        except ValueError as exc:
            print(f"FAIL {exc}")
            return 1
    _, outcome, head = research_run(
        runs_root=args.runs_root, run_id=args.run_id, concept=concept, corpus=corpus, manifest=manifest,
        condition=args.condition, temperature=args.temperature, seed=args.seed,
        git_commit=git_head(Path(__file__).resolve().parents[1]), agent_root_manifest_sha256=agent_root_sha,
        sandbox_mode=args.sandbox, agent_root=args.agent_root, base_url=args.base_url,
        budget=budget, broker=args.broker, extra_path=tuple(args.path_extra),
        prompt_version=args.prompt_version, settings=settings, spawn=spawn)
    # steps and tokens are the agent's own (its budget); with subagents the run's total is reported too.
    subagents = (f" subagents={outcome.subagents} run_tokens={outcome.tokens + outcome.subagent_tokens}"
                 if args.spawn == "on" else "")
    print(f"run {args.run_id}: exit={outcome.exit_status} steps={outcome.steps} tokens={outcome.tokens} "
          f"rows={outcome.answer_rows} answer={outcome.answer_from}{subagents} head={head.get('head')}")
    return 0 if outcome.exit_status == "submitted" else 1


def cmd_attach(args: argparse.Namespace) -> int:
    from .attach import ATTACH_BUDGET, AttachError, attach_run  # imports the loop: slow, so only here

    stop_on_sigterm()
    corpus, manifest = _corpus(args)
    budget = {**ATTACH_BUDGET, **{k: v for k, v in (("steps", args.steps_per_fact), ("tokens", args.tokens_per_fact))
                                  if v is not None}}
    try:
        summary = attach_run(args.run_dir, corpus, manifest, base_url=args.base_url, sandbox_mode=args.sandbox,
                             agent_root=args.agent_root, budget=budget, broker=args.broker,
                             extra_path=tuple(args.path_extra), prompt_version=args.prompt_version,
                             conclude_decoding=args.conclude_decoding)
    except AttachError as exc:
        print(f"FAIL {exc}")
        return 1
    c = summary["cost"]
    print(f"attach {summary['run_id']}: facts={len(summary['facts'])} attached={summary['attached']} "
          f"(from claims {summary['attached_from_claim']}) no_source={summary['no_source']} tokens={c['tokens']} "
          f"time={c['seconds']}s head={summary['chain_head']}")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    from .batch import Batch, Manifest, job_deadline

    try:
        manifest = Manifest.load(args.manifest)
        batch = Batch(manifest, deadline=job_deadline(args.deadline, args.time_limit), margin_s=args.margin,
                      min_start_s=args.min_start, corpus=args.corpus)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}")
        return 1
    if args.status:
        for key in batch.status():
            runs = ", ".join(f"{a['run_id']}={a['state']}" for a in key["attempts"]) or "not started"
            print(f"{key['key']} seed={key['seed']}: {runs}")
        return 0
    return batch.run()


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
    if "attach" in s:
        a, w = s["attach"], s["without_attach"]
        print(f"attach step: steps={a['steps']} model_calls={a['model_calls']} commands={a['commands']} "
              f"claims={a['claims_accepted']} accepted / {a['claims_rejected']} rejected tokens={a['tokens']} "
              f"time={a['seconds']}s")
        print(f"without attach: steps={w['steps']} tokens={w['tokens']} time={w['seconds']}s; "
              f"with attach: tokens={s.get('tokens', 0)} time={s.get('seconds', 0)}s")
    for agent_id, a in s.get("agents", {}).items():  # row 2.12: the totals above are the run's, these each agent's
        print(f"agent {agent_id}: steps={a['steps']} model_calls={a['model_calls']} commands={a['commands']} "
              f"claims={a['claims_accepted']} accepted / {a['claims_rejected']} rejected tokens={a['tokens']}")
    if report.ok:
        print(f"PASS {args.run_dir} records={s.get('records')} head={s.get('head')}")
    return 0 if report.ok else 1


def _claim_text(verdict: dict | None) -> str:
    """A claim verdict of reexec.json as one phrase: 'accepted claim-000002', 'rejected not_found', 'not sent'."""
    return "not sent" if verdict is None else f"{verdict['status']} {verdict['claim_id'] or verdict['reason']}"


def cmd_reexec(args: argparse.Namespace) -> int:
    from .reexec import ReexecError, parse_steps, reexec_run

    stop_on_sigterm()
    corpus, manifest = _corpus(args)
    try:
        steps = parse_steps(args.steps) if args.steps else None
        report = reexec_run(args.run_dir, corpus, manifest, steps=steps, sandbox_mode=args.sandbox,
                            agent_root=args.agent_root, extra_path=tuple(args.path_extra), keep_scratch=args.keep_scratch)
    except (ReexecError, ValueError, OSError) as exc:
        print(f"FAIL {exc}")
        return 2
    for d in report["differing"]:
        print(f"DIFF step {d['step']} ({d['agent_id']}) line {d['first_diff_line']}: recorded {d['recorded_line']!r}, "
              f"now {d['now_line']!r} -> {d['output_file']}")
    for d in report["differing_claims"]:
        print(f"DIFF claim {d['n']} of step {d['step']} ({d['agent_id']}): recorded {_claim_text(d['recorded'])}, "
              f"now {_claim_text(d['now'])}")
    if report["toolchain_differs"]:
        t = report["toolchain"]["agent_root_manifest_sha256"]
        print(f"WARN toolchain differs: agent root manifest sha256 {t['now']} now, {t['run']} in the run; a differing "
              "output may come from it")
    for error in report["errors"]:
        print(f"FAIL {error}")
    c = report["claims"]
    print(f"reexec {report['run_id']}: {report['identical']}/{report['steps']} outputs identical, "
          f"{len(report['differing'])} differing; claims {c.get('same_as_recorded', 0)}/{c.get('sent', 0)} as recorded, "
          f"{len(report['differing_claims'])} differing -> {args.run_dir / 'reexec.json'}")
    return 2 if report["errors"] else (1 if report["differing"] or report["differing_claims"] else 0)


def cmd_replay(args: argparse.Namespace) -> int:
    from .replay import replay_run

    report = replay_run(args.run_dir)
    for error in report["errors"][:50]:
        print(f"FAIL {error}")
    if len(report["errors"]) > 50:
        print(f"... and {len(report['errors']) - 50} more in replay.json")
    skipped = ", ".join(f"{k} {n}" for k, n in sorted(report["skipped"].items()))
    # PARTIAL: the research loop replays, but some calls (subagents', or an attach step without its
    # attach-trajectory.json) are not in a trajectory.
    verdict = "FAIL" if not report["ok"] else ("PASS" if report["complete"] else "PARTIAL")
    source = "trajectory.json" + (" and attach-trajectory.json" if report["scope"] == "research+attach" else "")
    print(f"{verdict} replay {report['run_id']}: {report['matched']}/{report['calls']} model "
          f"calls rebuilt from {source}, {report['outputs_ok']}/{report['commands']} outputs match"
          + (f"; {report['unchecked_calls']} calls not checked (not in the trajectory: {skipped})" if skipped else "")
          + f" -> {args.run_dir / 'replay.json'}")
    return 0 if report["ok"] else 1


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


def cmd_concepts_propose(args: argparse.Namespace) -> int:
    from . import concept_step
    from .loop import OrchestratorModel  # LiteLLM and mini-swe-agent: slow, so only here
    from .rundir import git_head

    question = args.question if args.question is not None else args.question_file.read_text(encoding="utf-8")
    model = OrchestratorModel(base_url=args.base_url, temperature=args.temperature, seed=args.seed)
    try:
        session, proposal = concept_step.propose(
            args.root, args.question_id, question, model, temperature=args.temperature, seed=args.seed,
            git_commit=git_head(Path(__file__).resolve().parents[1]), base_url=args.base_url,
            prompt_version=args.prompt_version, max_briefs=args.max_briefs)
    except (concept_step.ConceptStepError, ValueError) as exc:
        print(f"FAIL {exc}")
        for problem in getattr(exc, "problems", []):
            print(f"  - {problem}")
        return 1
    print(concept_step.show(proposal["briefs"]))
    if proposal["capped_from"]:
        print(f"\n(the model gave {proposal['capped_from']} briefs; the first {len(proposal['briefs'])} are kept)")
    print(f"\nPick one: agent concepts pick {session.root} --choice N")
    return 0


def cmd_concepts_pick(args: argparse.Namespace) -> int:
    import sys

    from . import concept_step

    session = concept_step.Session(args.session_dir)
    try:
        briefs = session.load(concept_step.PROPOSAL_FILE)["briefs"]
    except OSError as exc:
        print(f"FAIL no proposal in {args.session_dir} ({exc})")
        return 1
    choice = args.choice
    if choice is None:
        print(concept_step.show(briefs))
        if not sys.stdin.isatty():
            print("FAIL no --choice given and no terminal to ask on")
            return 1
        while choice is None:
            answer = input(f"\nPick a concept [1-{len(briefs)}]: ").strip()
            if answer.isdigit() and 1 <= int(answer) <= len(briefs):
                choice = int(answer)
    try:
        concept, sha = concept_step.pick(args.session_dir, choice, picked_by=args.picked_by, reason=args.reason,
                                         replace=args.replace, force=args.force)  # gold: $GOLD
    except (concept_step.ConceptStepError, ValueError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(f"PASS picked [{choice}] {concept['title']} (by {args.picked_by})\nconcept.json sha256={sha} -> "
          f"{session.path(concept_step.CONCEPT_FILE)}")
    return 0


def _questions(path: Path) -> list[dict] | None:
    from . import concept_step

    try:
        return concept_step.load_questions(path)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}")
        return None


def _summary(results: list, ok_states: tuple[str, ...]) -> int:
    """Print the count per state; 0 when every question ended in one of `ok_states` with no problems."""
    counts: dict[str, int] = {}
    for r in results:
        counts[r.state] = counts.get(r.state, 0) + 1
    bad = [r for r in results if r.state not in ok_states or r.problems]
    print(("PASS " if not bad else "FAIL ") + ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
          + (f" (needs action: {', '.join(r.id for r in bad)})" if bad else ""))
    return 1 if bad else 0


def cmd_concepts_propose_all(args: argparse.Namespace) -> int:
    from . import concept_step
    from .loop import OrchestratorModel  # LiteLLM and mini-swe-agent: slow, so only here
    from .rundir import git_head

    questions = _questions(args.questions)
    if questions is None:
        return 1
    model = OrchestratorModel(base_url=args.base_url, temperature=args.temperature, seed=args.seed)
    print(f"proposing for {len(questions)} questions into {args.root} (temperature {args.temperature}, "
          f"seed {args.seed}, {args.base_url})", flush=True)
    results = concept_step.propose_all(
        questions, args.root, model, temperature=args.temperature, seed=args.seed,
        git_commit=git_head(Path(__file__).resolve().parents[1]), base_url=args.base_url,
        prompt_version=args.prompt_version, max_briefs=args.max_briefs, log=lambda line: print(line, flush=True))
    for r in results:
        for problem in r.problems[:10]:
            print(f"  {r.id}: {problem}")
    return _summary(results, ("proposed", "skipped"))


def cmd_concepts_pick_all(args: argparse.Namespace) -> int:
    from . import concept_step

    questions = _questions(args.questions)
    if questions is None:
        return 1
    results = concept_step.pick_all(questions, args.root, rule=args.rule, picked_by=args.picked_by,
                                    reason=args.reason)
    for r in results:
        print(r.line())
    print(f"picks: {Path(args.root) / concept_step.PICKS_FILE}")
    return _summary(results, ("picked", "skipped"))


def cmd_concepts_status(args: argparse.Namespace) -> int:
    from . import concept_step

    questions = _questions(args.questions)
    if questions is None:
        return 1
    results = concept_step.status(questions, args.root)
    for r in results:
        print(r.line())
        for problem in r.problems:
            print(f"  {r.id}: {problem}")
    return _summary(results, ("picked",))


def cmd_concepts_check(args: argparse.Namespace) -> int:
    from . import concept_step

    problems = concept_step.check_session(args.session_dir)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print(f"PASS {args.session_dir} concept.json sha256={file_sha256(Path(args.session_dir) / 'concept.json')}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    from .concept_step import PICKED_BY, QUESTIONS_FILE  # standard library and agent core only: cheap

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
    run.add_argument("--steps", type=int, help=f"step budget (default {RUN_BUDGET['steps']}; "
                                                f"{RUN_BUDGET_M1['steps']} with --prompt-version v1)")
    run.add_argument("--tokens", type=int, help=f"token budget (default {RUN_BUDGET['tokens']:,}; "
                                                 f"{RUN_BUDGET_M1['tokens']:,} with --prompt-version v1)")
    run.add_argument("--prompt-version", default="v2",
                     help="agent/prompts/system-<version>.txt; v1 reproduces the M1-real runs: their loop settings "
                          "and, unless --steps/--tokens say otherwise, their budget (150 steps / 400,000 tokens)")
    run.add_argument("--conclude-decoding", choices=DECODING_CHOICES,
                     help="how conclude replies are decoded (default: the prompt version's; structured_outputs is "
                          "vLLM >= 0.10's extra_body key, guided_json older vLLM's, free no schema)")
    run.add_argument("--broker", choices=("auto", "process", "inprocess"), default="auto")
    run.add_argument("--path-extra", action="append", default=[], help="extra directory on the sandbox PATH")
    run.add_argument("--spawn", choices=("on", "off"), default="off",
                     help="the spawn command: subagents on sub-model-1/-2 with their own budget (row 2.12; "
                          "recorded in config.json; off for the 72 runs unless decided otherwise)")
    run.add_argument("--spawn-steps", type=int, help="each subagent's step budget, with --spawn on (default 15)")
    run.add_argument("--spawn-tokens", type=int, help="each subagent's token budget, with --spawn on (default 300,000)")
    run.set_defaults(func=cmd_run)

    attach = sub.add_parser("attach", help="baseline attach step: one quote or 'no source found' per answer fact (row 2.5)")
    attach.add_argument("run_dir", type=Path, help="a finished claim_off run")
    _corpus_args(attach)
    attach.add_argument("--base-url", help="LiteLLM proxy (default: the run's); key from $LITELLM_MASTER_KEY")
    attach.add_argument("--sandbox", choices=("landlock", "unsandboxed"), help="default: the run's sandbox mode")
    attach.add_argument("--agent-root", type=Path, help="default: the run's agent root")
    attach.add_argument("--steps-per-fact", type=int)
    attach.add_argument("--tokens-per-fact", type=int)
    attach.add_argument("--prompt-version", help="agent/prompts/attach-<version>.txt (default: the run's prompt version)")
    attach.add_argument("--conclude-decoding", choices=DECODING_CHOICES,
                        help="how conclude replies are decoded (default: the run's)")
    attach.add_argument("--broker", choices=("auto", "process", "inprocess"), default="auto")
    attach.add_argument("--path-extra", action="append", default=[], help="extra directory on the sandbox PATH")
    attach.set_defaults(func=cmd_attach)

    batch = sub.add_parser("batch", help="run a run manifest inside the job time limit; skip finished runs (row 2.9)")
    batch.add_argument("manifest", type=Path, help="run manifest, e.g. agent/manifests/m4-72.json")
    batch.add_argument("--deadline", help="job end: ISO time or epoch seconds (also read: $SLURM_JOB_END_TIME)")
    batch.add_argument("--time-limit", type=float, help="job end in seconds from now")
    batch.add_argument("--margin", type=float, default=300, help="stop a running run this many seconds before the end")
    batch.add_argument("--min-start", type=float, default=900, help="start no run with less time than this left")
    batch.add_argument("--corpus", type=Path, help="default: the manifest's corpus, else $CORPUS")
    batch.add_argument("--status", action="store_true", help="list every run key and its attempts; run nothing")
    batch.set_defaults(func=cmd_batch)

    ver = sub.add_parser("verify", help="verify a finished run: chain, anchors, answer claim ids (row 1.11)")
    ver.add_argument("run_dir", type=Path)
    _corpus_args(ver)
    ver.set_defaults(func=cmd_verify)

    reexec = sub.add_parser("reexec", help="run a run's recorded commands again in a fresh scratch dir and compare "
                                           "outputs; claims go to a dry broker (row 2.13, C5)")
    reexec.add_argument("run_dir", type=Path)
    _corpus_args(reexec)
    reexec.add_argument("--steps", help="only these step ids, e.g. 1,2,5-7 (default: every command)")
    reexec.add_argument("--sandbox", choices=("landlock", "unsandboxed"), help="default: the run's sandbox mode")
    reexec.add_argument("--agent-root", type=Path, help="default: the run's agent root")
    reexec.add_argument("--path-extra", action="append", default=[], help="extra directory on the sandbox PATH")
    reexec.add_argument("--keep-scratch", action="store_true", help="keep the fresh scratch directory")
    reexec.set_defaults(func=cmd_reexec)
    replay = sub.add_parser("replay", help="rebuild the conversation from trajectory.json and out/ and check every "
                                           "recorded prompt hash (row 2.13, C6)")
    replay.add_argument("run_dir", type=Path)
    replay.set_defaults(func=cmd_replay)

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

    concepts = sub.add_parser("concepts", help="concept step: propose briefs for a question, pick one (rows 2.1-2.3)")
    csub = concepts.add_subparsers(dest="concepts_command", required=True)
    concepts_root = Path(os.environ.get("CONCEPTS") or "concepts")
    base_url = os.environ.get("LITELLM_BASE_URL") or "http://127.0.0.1:4000/v1"

    def model_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--temperature", type=float, required=True)
        p.add_argument("--seed", type=int, required=True)
        p.add_argument("--base-url", default=base_url,
                       help="LiteLLM proxy (default: $LITELLM_BASE_URL); key from $LITELLM_MASTER_KEY")
        p.add_argument("--prompt-version", default="v1")
        p.add_argument("--max-briefs", type=int, default=5)

    def questions_arg(p: argparse.ArgumentParser, required: bool) -> None:
        p.add_argument("questions", type=Path, **({} if required else {"nargs": "?"}),
                       default=QUESTIONS_FILE, help="questions file (default: questions/questions.json)")
        p.add_argument("--root", type=Path, default=concepts_root, help="concept sessions directory (default: $CONCEPTS)")

    propose = csub.add_parser("propose", help="ask orch-model for 1-5 concept briefs (corpus-blind)")
    propose.add_argument("question_id", help="e.g. q01; the session goes to <root>/<question_id>/")
    given = propose.add_mutually_exclusive_group(required=True)
    given.add_argument("--question", help="the question text")
    given.add_argument("--question-file", type=Path, help="file holding the question text")
    propose.add_argument("--root", type=Path, default=concepts_root, help="concept sessions directory (default: $CONCEPTS)")
    model_args(propose)
    propose.set_defaults(func=cmd_concepts_propose)
    propose_all = csub.add_parser("propose-all", help="propose for every question without a proposal (row 2.3)")
    questions_arg(propose_all, required=True)
    model_args(propose_all)
    propose_all.set_defaults(func=cmd_concepts_propose_all)
    pick = csub.add_parser("pick", help="pick one proposed brief; writes concept.json and concept.sha256")
    pick.add_argument("session_dir", type=Path, help="e.g. concepts/q01")
    pick.add_argument("--choice", type=int, help="brief number (asked on the terminal when left out)")
    pick.add_argument("--picked-by", choices=PICKED_BY, default="user", help="who picked (recorded as the agent)")
    pick.add_argument("--reason", default="", help="why this brief (recorded)")
    pick.add_argument("--replace", action="store_true",
                      help="change an earlier pick; refused once $GOLD/<question id>/ holds anything of its gold build")
    pick.add_argument("--force", action="store_true",
                      help="with --replace: replace even though gold exists (the pick records its files; move that "
                           "gold aside or rebuild it)")
    pick.set_defaults(func=cmd_concepts_pick)
    pick_all = csub.add_parser("pick-all", help="pick by a rule in every proposed question not yet picked")
    questions_arg(pick_all, required=False)
    pick_all.add_argument("--rule", choices=("first",), default="first", help="first: brief 1")
    pick_all.add_argument("--picked-by", choices=PICKED_BY, default="provisional-first")
    pick_all.add_argument("--reason", help="recorded with each pick (default: the rule's reason)")
    pick_all.set_defaults(func=cmd_concepts_pick_all)
    cstatus = csub.add_parser("status", help="one line per question: none, failed, proposed, picked or stale")
    questions_arg(cstatus, required=False)
    cstatus.set_defaults(func=cmd_concepts_status)
    ccheck = csub.add_parser("check", help="verify a concept session: chain, pick record, concept hash")
    ccheck.add_argument("session_dir", type=Path)
    ccheck.set_defaults(func=cmd_concepts_check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
