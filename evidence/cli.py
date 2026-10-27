"""`evidence`: run a protocol over a corpus, replay or re-execute a run, export its provenance, verify its chain.

    evidence run --protocol P --corpus DIR --out runs/evidence [--cache DIR] [--model ALIAS]
                 [--extractors regex-only|llm-only|cascade] [--strategy gaps|all] [--workers N] [--import MODULE] [--run-id ID]
    evidence replay RUN [--cache DIR] [--corpus DIR]
    evidence reexec RUN [--extractor NAME] [--cache DIR] [--corpus DIR]
    evidence prov RUN
    evidence verify RUN
    evidence protocol check P
    evidence propose frame --question Q [--vocab V] --out DIR [--model ALIAS] [--force] [--refresh]
    evidence propose draft DIR [--template P]
    evidence propose critic DIR [--model ALIAS] [--refresh]
    evidence propose cards DIR [--model ALIAS] [--force] [--refresh]
    evidence propose freeze DIR
    evidence propose amend DIR --reason R [--before-main-run]
    evidence vocab build --name N --source DIR --out FILE

`--extractors regex-only` needs no model. `--strategy gaps` (default) is the funnel (docs/evidence-system.md Part D):
screen, then escalate only the gaps; `all` runs every extractor on every document and records the
screen decision. LLM extractors reach LiteLLM through modelcall.openai_model, which
reads the key from $LITELLM_MASTER_KEY only; `--model` (default orch-model, the one model of every extractor
and both baselines) is the alias of the LLM and agentic extractors. `protocol check` validates a protocol file
and prints {id, version, revision, sha256, phases, extractors per type}. `propose` is the proposal flow
(docs/evidence-system.md Part E, evidence/propose): question -> frame -> draft -> critic -> cards (the person
edits decisions.yaml) -> freeze -> amend, all files in one directory; frame, critic and cards make one cached
model call each (`--model`, default orch-model), the rest is deterministic, and nothing runs the protocol.
`vocab build` makes a vocabulary snapshot from local files (evidence/propose/vocab.py). Exit status: 0 ok,
1 a replay mismatch, a cache miss, a broken chain or a failed proposal model call, 2 usage errors, a protocol that does not validate and a
refused proposal step (a decision without a reason, an amendment without a reason or a change, a stale input).
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


def _workers(text: str) -> int:
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


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
    r.add_argument("--strategy", default="gaps", choices=["all", "gaps"],
                   help="gaps: the funnel, escalate only the gaps (default); all: every extractor on every document")
    r.add_argument("--workers", type=_workers, default=3,
                   help="papers whose model calls run at once; outputs do not depend on it")
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
    _propose_parser(sub)
    return p


def _propose_parser(sub: argparse._SubParsersAction) -> None:
    pro = sub.add_parser("propose", help="the proposal flow: question to frozen protocol (Part E)").add_subparsers(
        dest="propose_command", required=True)
    model_help = f"model alias (default {DEFAULT_MODEL})"
    f = pro.add_parser("frame", help="question -> frame.json (one model call)")
    f.add_argument("--question", required=True)
    f.add_argument("--vocab", help="vocabulary snapshot: a path or a name under evidence/vocab/")
    f.add_argument("--out", required=True, type=Path, help="the proposal directory, e.g. proposals/<slug>")
    f.add_argument("--model", default=DEFAULT_MODEL, help=model_help)
    f.add_argument("--kind", choices=("effect", "inventory", "consistency", "best"),
                   help="the question's kind, instead of the model's guess")
    f.add_argument("--force", action="store_true", help="overwrite a frame.json that was edited")
    f.add_argument("--refresh", action="store_true", help="ask the model again instead of using its cached reply")
    d = pro.add_parser("draft", help="frame.json + the example protocol -> draft.yaml, draft.sources.json")
    d.add_argument("dir", type=Path)
    d.add_argument("--template", type=Path, help="example protocol (default: the hand-written protocol of the question's kind, evidence/propose/common.KIND_TEMPLATES)")
    for name, text in (("critic", "deterministic checks and an LLM checklist -> critic.json"),
                       ("cards", "the fixed choice points -> cards.json, decisions.yaml (prefilled)")):
        s = pro.add_parser(name, help=text)
        s.add_argument("dir", type=Path)
        s.add_argument("--model", default=DEFAULT_MODEL, help=model_help)
        s.add_argument("--refresh", action="store_true", help="ask the model again instead of using its cached reply")
        if name == "cards":
            s.add_argument("--force", action="store_true", help="overwrite a decisions.yaml that was edited")
    pro.add_parser("freeze", help="decisions applied -> protocol.yaml, proposal.json").add_argument("dir", type=Path)
    a = pro.add_parser("amend", help="the edited protocol.yaml -> the next revision, a line in amendments.jsonl")
    a.add_argument("dir", type=Path)
    a.add_argument("--reason", required=True)
    a.add_argument("--before-main-run", action="store_true", help="the amendment is made before the main run")
    v = sub.add_parser("vocab", help="vocabulary snapshots").add_subparsers(dest="vocab_command", required=True)
    b = v.add_parser("build", help="build a snapshot from local term files (no network)")
    b.add_argument("--name", required=True)
    b.add_argument("--source", required=True, type=Path, help="directory with sources.json and the term files")
    b.add_argument("--out", required=True, type=Path)


def _propose(args: argparse.Namespace) -> int:
    from .propose import amend, cards, critic, draft, frame, freeze
    from .propose.common import ProposalError
    from .propose.vocab import VocabError
    try:
        if args.propose_command == "frame":
            out = frame.run(args.question, args.out, vocab=args.vocab, alias=args.model, force=args.force,
                            refresh=args.refresh, kind=args.kind)
        elif args.propose_command == "draft":
            out = draft.run(args.dir, template=args.template)
        elif args.propose_command == "critic":
            out = critic.run(args.dir, alias=args.model, refresh=args.refresh)
        elif args.propose_command == "cards":
            out = cards.run(args.dir, alias=args.model, force=args.force, refresh=args.refresh)
        elif args.propose_command == "freeze":
            out = freeze.run(args.dir)
        else:
            print(json.dumps(amend.run(args.dir, args.reason, before_main_run=args.before_main_run), indent=1))
            return 0
    except (ProposalError, VocabError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:   # a failed model call (common.ask redacts the key); nothing was written
        print(f"error: model call failed: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


def _vocab(args: argparse.Namespace) -> int:
    from .propose import vocab
    try:
        data = vocab.build(args.name, args.source)
    except (OSError, ValueError, KeyError) as exc:   # VocabError and pydantic's ValidationError are ValueErrors
        print(f"error: {exc}", file=sys.stderr)
        return 2
    path = vocab.write(data, args.out)
    print(json.dumps({"file": str(path), "name": data["name"], "sha256": data["sha256"], "terms": len(data["terms"])},
                     indent=1))
    return 0


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
                   strategy=args.strategy, workers=args.workers)
        record = read_json(root / RUN_FILE)
        answer = read_json(root / "answer.json")
        summary = ({"label": answer["label"], "counts": answer["counts"]} if "kind" not in answer
                   else {"kind": answer["kind"]})   # effect answers carry no kind; the others no label
        print(json.dumps({"run": str(root), **summary, "cost": record["cost"]}, indent=1))
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
    if args.command == "propose":
        return _propose(args)
    if args.command == "vocab":
        return _vocab(args)
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
    print(json.dumps({"id": protocol.id, "version": protocol.version, "revision": protocol.revision,
                      "sha256": protocol.sha256,
                      "phases": protocol.phases(),
                      "extractors": {t: [r.name for r in s.extractors] for t, s in protocol.evidence_types.items()}},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
