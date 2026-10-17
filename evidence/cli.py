"""`evidence`: run a protocol over a corpus, replay or re-execute a run, export its provenance, verify its chain.

    evidence run --protocol P --corpus DIR --out runs/evidence [--cache DIR] [--model ALIAS]
                 [--extractors regex-only|llm-only|cascade] [--strategy all|gaps] [--import MODULE] [--run-id ID]
    evidence replay RUN [--cache DIR] [--corpus DIR]
    evidence reexec RUN [--extractor NAME] [--cache DIR] [--corpus DIR]
    evidence prov RUN
    evidence verify RUN
    evidence protocol check P

`--extractors regex-only` needs no model. `--strategy gaps` is the funnel (docs/evidence-system.md Part D):
screen, then escalate only the gaps; `all` (default) runs every extractor on every document and records the
screen decision. LLM extractors reach LiteLLM through gold/llm.openai_model, which
reads the key from $LITELLM_MASTER_KEY only; `--model` (default orch-model, the one model of every extractor
and both baselines) is the alias of the LLM and agentic extractors. `protocol check` validates a protocol file
and prints {id, version, sha256, phases, extractors per type}; the proposal flow (docs/evidence-system.md
Part E) will hang its subcommands beside it. Exit status: 0 ok, 1 a replay mismatch, a cache miss or a broken
chain, 2 usage errors and a protocol that does not validate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from agent.chain import verify

from .calls import NotRecorded
from .rundir import EVENTS_FILE, RUN_FILE, read_json

DEFAULT_MODEL = "orch-model"  # agent/rundir.ORCHESTRATOR's alias; evidence.engine.Settings.model stays None by default


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evidence", description=__doc__.split("\n", 1)[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run a protocol over a corpus")
    r.add_argument("--protocol", required=True, type=Path)
    r.add_argument("--corpus", required=True, type=Path)
    r.add_argument("--out", default=Path("runs/evidence"), type=Path)
    r.add_argument("--cache", type=Path, help="record cache directory (default OUT/cache)")
    r.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"model alias of the LLM and agentic extractors (default {DEFAULT_MODEL}; overrides the protocol)")
    r.add_argument("--extractors", default="cascade", choices=["cascade", "regex-only", "llm-only"])
    r.add_argument("--strategy", default="all", choices=["all", "gaps"],
                   help="all: every extractor on every document (default); gaps: the funnel, escalate only the gaps")
    r.add_argument("--import", dest="imports", action="append", default=[], help="module that registers extractors")
    r.add_argument("--run-id")
    r.add_argument("--retry-errors", action="store_true", help="run cached error results again")
    for name, text in (("replay", "rebuild a run from the record cache and check its output hashes"),
                       ("reexec", "run extractors again, bypassing the cache, and compare")):
        s = sub.add_parser(name, help=text)
        s.add_argument("run", type=Path)
        s.add_argument("--cache", type=Path)
        s.add_argument("--corpus", type=Path)
        s.add_argument("--out", type=Path)
        if name == "reexec":
            s.add_argument("--extractor", help="extractor name or id (default: every extractor)")
    sub.add_parser("prov", help="export the run's PROV-O graph (prov.ttl)").add_argument("run", type=Path)
    sub.add_parser("verify", help="check the run's hash chain").add_argument("run", type=Path)
    proto = sub.add_parser("protocol", help="check a protocol file").add_subparsers(dest="protocol_command", required=True)
    proto.add_parser("check", help="validate a protocol and print its sha256 and phases").add_argument("protocol", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _dispatch(args)
    except NotRecorded as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "run":
        from .engine import run
        root = run(args.protocol, args.corpus, args.out, cache=args.cache, selection=args.extractors,
                   model=args.model, imports=args.imports, run_id=args.run_id, retry_errors=args.retry_errors,
                   strategy=args.strategy)
        record = read_json(root / RUN_FILE)
        answer = read_json(root / "answer.json")
        print(json.dumps({"run": str(root), "label": answer["label"], "counts": answer["counts"],
                          "cost": record["cost"]}, indent=1))
        return 0
    if args.command == "replay":
        from .replay import replay
        new, report = replay(args.run, cache=args.cache, corpus=args.corpus, out_dir=args.out)
        print(json.dumps({"run": str(new), **report}, indent=1))
        return 0 if report["ok"] else 1
    if args.command == "reexec":
        from .replay import reexec
        new = reexec(args.run, args.extractor, cache=args.cache, corpus=args.corpus, out_dir=args.out)
        report = read_json(new / "reexec.json")
        print(json.dumps({"run": str(new), "summary": report["summary"], "totals": report["totals"]}, indent=1))
        return 0
    if args.command == "prov":
        from .prov import export
        path = export(args.run)
        print(path)
        return 0
    if args.command == "protocol":
        return _protocol_check(args.protocol)
    report = verify(args.run / EVENTS_FILE, head=read_json(args.run / RUN_FILE).get("chain_head"))
    print(json.dumps({"ok": report.ok, "records": report.records, "head": report.head, "errors": report.errors}, indent=1))
    return 0 if report.ok else 1


def _protocol_check(path: Path) -> int:
    from .protocol import load
    try:
        protocol = load(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:   # pydantic's ValidationError is a ValueError
        print(f"error: {path}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"id": protocol.id, "version": protocol.version, "sha256": protocol.sha256,
                      "phases": protocol.phases(),
                      "extractors": {t: [r.name for r in s.extractors] for t, s in protocol.evidence_types.items()}},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
