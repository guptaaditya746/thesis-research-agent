"""`evidence`: run a protocol over a corpus, replay or re-execute a run, export its provenance, verify its chain and
its file hashes.

    evidence run (--protocol P | --plan PLAN) --corpus DIR --out runs/evidence [--cache DIR] [--model ALIAS]
                 [--extractors regex-only|llm-only|cascade] [--strategy gaps|all] [--confirm llm|none] [--relink on|off]
                 [--names off|on] [--reason on|off] [--workers N] [--import MODULE] [--run-id ID]
                 [--retry-errors] [--allow-failed-calls]
    evidence estimate --protocol P --corpus DIR [--strategy gaps|all] [--extractors regex-only|llm-only|cascade]
                      [--from-run RUN]
    evidence replay RUN [--cache DIR] [--corpus DIR]
    evidence reexec RUN [--extractor NAME | --all-calls [--times N]] [--cache DIR] [--corpus DIR] [--out DIR]
    evidence program RUN --out FILE [--corpus DIR]
    evidence prov RUN
    evidence verify RUN
    evidence protocol check P
    evidence pack check NAME
    evidence propose frame --question Q --out DIR [--model ALIAS] [--force] [--refresh]
    evidence propose draft DIR [--template P]
    evidence propose critic DIR [--model ALIAS] [--refresh]
    evidence propose cards DIR [--model ALIAS] [--force] [--refresh]
    evidence propose freeze DIR
    evidence propose amend DIR --reason R [--before-main-run]
    evidence tune STEP --train DIR... --test DIR... [--optimizer gepa|miprov2] [--model ALIAS] [--cache DIR]
    evidence fetch --query TEXT --out DIR [--max N] [--category CAT]

`run --plan` is a plan run (evidence/planrun.py): the confirmed plan file (every decision confirmed, else exit 2)
replaces the protocol, which is written from it by code; the run adds the plan's stages and answers the plan's
evidence lines (answer.json: lines, main answer, labels, reruns; records.nq; ontology.json). `--names`, `--confirm`,
`--relink` are fixed for a plan run (off, llm, on); `--reason on|off` and `--links on|off` (plan runs only) switch its
reasoning and its builds-on links.
`estimate` prints the extractor and screen calls (low, high) and the tokens a run would need, from a regex-only
pass over the corpus (no model; nothing is written): `--from-run` takes the tokens per call of a finished run
instead of chars/4. `--extractors regex-only` needs no model. `--strategy gaps` (default) is the funnel (docs/evidence-system.md Part D):
screen, then escalate only the gaps; `all` runs every extractor on every document and records the
screen decision. LLM extractors reach LiteLLM through modelcall.openai_model, which
reads the key from $LITELLM_MASTER_KEY only; `--model` (default orch-model, the one model of every extractor
and both baselines) is the alias of the LLM and agentic extractors. `pack check` reads the domain pack
domains/NAME/, registers its evidence types, checks that it has a type of every role its questions' kinds need and
that every protocol its questions name validates, and prints {pack, sha256, types, kinds, protocols} (exit 2 when
it does not). `protocol check` validates a protocol file
and prints {id, version, revision, sha256, phases, extractors per type}. `propose` is the proposal flow
(docs/evidence-system.md Part E, evidence/propose): question -> frame -> draft -> critic -> cards (the person
edits decisions.yaml) -> freeze -> amend, all files in one directory; frame, critic and cards make one cached
model call each (`--model`, default orch-model), the rest is deterministic, and nothing runs the protocol.
`fetch` writes a demonstration corpus of real arXiv papers (evidence/arxiv.py): manifest.json, papers/ and
source.json with `ground_truth: false`; there is nothing to score it against.
Exit status: 0 ok,
1 a replay mismatch, a cache miss, a broken chain, a run file whose sha256 differs from its manifest.json or a failed proposal model call, 2 usage errors, a protocol that does not validate and a
refused proposal step (a decision without a reason, an amendment without a reason or a change, a stale input).
`run` also exits 2 when the run it wrote has failed extractor calls (calls/*.json status error or partial: the
model gateway or the GLiNER service did not answer): the run stays on disk, and stderr has
`FAIL engine-errors <run dir> <count>`. Those results are in the record cache, so a later run reuses them until it
is given `--retry-errors`. `--allow-failed-calls` exits 0 instead and only warns (the web app counts them itself).
A run dir that exists already is refused with exit 2 (a run dir is never written over); one without run.json is a
killed run, and the message says to move it aside and run again.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from agent.chain import verify
from jsonio import write_json
from modelcall.pins import ORCH_ALIAS

from . import arxiv
from .calls import NotRecorded
from .rundir import ANSWER_FILE, EVENTS_FILE, RUN_FILE, RunDir, RunDirExists, read_json

DEFAULT_MODEL = ORCH_ALIAS  # orch-model; evidence.engine.Settings.model stays None by default


def _workers(text: str) -> int:
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evidence", description=__doc__.split("\n", 1)[0])
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run a protocol over a corpus")
    r.add_argument("--protocol", type=Path, help="the protocol file (or --plan)")
    r.add_argument("--plan", type=Path, help="a confirmed plan file: a plan run (instead of --protocol)")
    r.add_argument("--corpus", required=True, type=Path)
    r.add_argument("--out", default=Path("runs/evidence"), type=Path)
    r.add_argument("--cache", type=Path, help="record cache directory (default OUT/cache)")
    r.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"model alias of the LLM and agentic extractors (default {DEFAULT_MODEL}; overrides the protocol)")
    r.add_argument("--extractors", default="cascade", choices=["cascade", "regex-only", "llm-only"])
    r.add_argument("--strategy", default="gaps", choices=["all", "gaps"],
                   help="gaps: the funnel, escalate only the gaps (default); all: every extractor on every document")
    r.add_argument("--confirm", default="llm", choices=["none", "llm"],
                   help="llm: an item only GLiNER found counts only when the LLM extractor finds it too (default); "
                        "none: keep every item")
    r.add_argument("--relink", default="on", choices=["on", "off"],
                   help="on: links follow an item whose id a later funnel round changed, and the run counts the links "
                        "to no item (default); off: the engine of runs before 1 Nov")
    r.add_argument("--names", default="off", choices=["off", "on"],
                   help="on: group the names of compared things, metrics and datasets across papers (names.json), a "
                        "model check for names no rule joins, and count the names left (unresolved_names); off: as "
                        "before (default)")
    r.add_argument("--reason", default="on", choices=["on", "off"],
                   help="on: the reasoner reads the pack's ontology, so a narrower metric answers a broader question "
                        "metric, and flags links to an item of the wrong kind (reason.json; default); off: as before")
    r.add_argument("--links", default="on", choices=["on", "off"],
                   help="plan runs: off leaves out the builds-on links (no OpenAlex request; default on)")
    r.add_argument("--workers", type=_workers, default=3,
                   help="papers whose model calls run at once; outputs do not depend on it")
    r.add_argument("--import", dest="imports", action="append", default=[], help="module that registers extractors")
    r.add_argument("--run-id")
    r.add_argument("--retry-errors", action="store_true", help="run cached error and partial results again")
    r.add_argument("--allow-failed-calls", action="store_true",
                   help="exit 0 even when extractor calls failed (default: exit 2 with a FAIL engine-errors line)")
    e = sub.add_parser("estimate", help="the calls and tokens a run would need, before it is made")
    e.add_argument("--protocol", required=True, type=Path)
    e.add_argument("--corpus", required=True, type=Path)
    e.add_argument("--strategy", default="gaps", choices=["all", "gaps"])
    e.add_argument("--extractors", default="cascade", choices=["cascade", "regex-only", "llm-only"])
    e.add_argument("--from-run", type=Path, help="a finished run: its tokens per model call replace chars/4")
    e.add_argument("--names", default="off", choices=["on", "off"],
                   help="on: also count the names check's model calls (as the run's --names on; an upper bound)")
    for name, text in (("replay", "rebuild a run from the record cache and check its output hashes"),
                       ("reexec", "run extractors again, bypassing the cache, and compare")):
        s = sub.add_parser(name, help=text)
        s.add_argument("run", type=Path)
        s.add_argument("--cache", type=Path)
        s.add_argument("--corpus", type=Path)
        s.add_argument("--out", type=Path)
        if name == "reexec":
            pick = s.add_mutually_exclusive_group()
            pick.add_argument("--extractor", help="extractor name or id (default: every extractor)")
            pick.add_argument("--all-calls", action="store_true",
                              help="every extractor, and the names check's and the stages' model calls, asked again")
            s.add_argument("--times", type=int, help="with --all-calls and --out: N re-runs, then the re-run measure")
    g = sub.add_parser("program", help="the run's answer as one readable Python program (standard library only)")
    g.add_argument("run", type=Path)
    g.add_argument("--out", required=True, type=Path)
    g.add_argument("--corpus", type=Path)
    sub.add_parser("prov", help="export the run's PROV-O graph (prov.ttl)").add_argument("run", type=Path)
    sub.add_parser("verify", help="check the run's hash chain and file hashes").add_argument("run", type=Path)
    proto = sub.add_parser("protocol", help="check a protocol file").add_subparsers(dest="protocol_command", required=True)
    proto.add_parser("check", help="validate a protocol and print its sha256 and phases").add_argument("protocol", type=Path)
    d = proto.add_parser("diff", help="what differs between two protocols or two runs (exit 0 same, 1 differ, 2 unreadable)")
    d.add_argument("a", type=Path, help="a protocol .yaml or a run directory")
    d.add_argument("b", type=Path, help="a protocol .yaml or a run directory")
    pk = sub.add_parser("pack", help="check a domain pack").add_subparsers(dest="pack_command", required=True)
    pk.add_parser("check", help="check a domain pack's types against its questions and protocols").add_argument("name")
    _propose_parser(sub)
    t = sub.add_parser("tune", help="DSPy tunes one step's instructions (GEPA light, 500 calls) -> steps/tuned/STEP.json")
    t.add_argument("step")
    t.add_argument("--train", required=True, nargs="+", type=Path, help="corpus or real-set folders to tune on")
    t.add_argument("--test", required=True, nargs="+", type=Path, help="folders to score on (disjoint from --train)")
    t.add_argument("--optimizer", default="gepa", choices=["gepa", "miprov2"])
    t.add_argument("--model", default=DEFAULT_MODEL, help="alias of the one model of the tuning (default orch-model)")
    t.add_argument("--cache", type=Path, default=Path("runs/tune-cache"), help="record cache folder of the model calls")
    arxiv.add_parser(sub)
    return p


def _propose_parser(sub: argparse._SubParsersAction) -> None:
    pro = sub.add_parser("propose", help="the proposal flow: question to frozen protocol (Part E)").add_subparsers(
        dest="propose_command", required=True)
    model_help = f"model alias (default {DEFAULT_MODEL})"
    f = pro.add_parser("frame", help="question -> frame.json (one model call)")
    f.add_argument("--question", required=True)
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


def _propose(args: argparse.Namespace) -> int:
    from .propose import amend, cards, critic, draft, frame, freeze
    from .propose.common import ProposalError
    try:
        if args.propose_command == "frame":
            out = frame.run(args.question, args.out, alias=args.model, force=args.force,
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
    except ProposalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:   # a failed model call (common.ask redacts the key); nothing was written
        print(f"error: model call failed: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


def _tune(args: argparse.Namespace) -> int:
    from modelcall.cache import JsonlCache
    from modelcall.dspy_lm import RecordedLM

    from .stages import gateway_ask
    from .steps import tune
    try:
        # check the request before any model is made: overlap and missing examples exit 2 with no key needed
        if args.step in tune.SPECS:
            tune.check_disjoint(tune.sources(args.step, args.train, "train"), tune.sources(args.step, args.test, "test"))
        args.cache.mkdir(parents=True, exist_ok=True)
        lm = RecordedLM(args.model, gateway_ask(args.model), cache=JsonlCache(args.cache / "tune.jsonl"))
        print(json.dumps(tune.tune(args.step, args.train, args.test, lm=lm, optimizer=args.optimizer), indent=1))
    except tune.TuneError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:   # a failed model call or an optimizer over its call cap; nothing was written
        print(f"error: model call failed: {exc}", file=sys.stderr)
        return 1
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
        if (args.protocol is None) == (args.plan is None):
            print("error: give --protocol or --plan (one of them)", file=sys.stderr)
            return 2
        if args.plan is not None:
            from .planrun import check_request
            try:   # a flag a plan run fixes, an unreadable, invalid or unconfirmed plan
                check_request(args.plan, names=args.names, confirm=args.confirm, relink=args.relink)
            except (OSError, ValueError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
        try:
            if args.plan is not None:
                from . import planrun
                root = planrun.run(args.plan, args.corpus, args.out, cache=args.cache, selection=args.extractors,
                                   model=args.model, imports=args.imports, run_id=args.run_id,
                                   retry_errors=args.retry_errors, strategy=args.strategy, workers=args.workers,
                                   reason=args.reason, links=args.links)
            else:
                root = run(args.protocol, args.corpus, args.out, cache=args.cache, selection=args.extractors,
                           model=args.model, imports=args.imports, run_id=args.run_id, retry_errors=args.retry_errors,
                           strategy=args.strategy, workers=args.workers, confirm=args.confirm, relink=args.relink,
                           names=args.names, reason=args.reason)
        except RunDirExists as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        record = read_json(root / RUN_FILE)
        answer = read_json(root / ANSWER_FILE)
        if args.plan is not None:
            summary = {"answer": answer["answer"]["text"], "labels": answer["labels"]}
        else:
            summary = ({"label": answer["label"], "counts": answer["counts"]} if "kind" not in answer
                       else {"kind": answer["kind"]})   # effect answers carry no kind; the others no label
        print(json.dumps({"run": str(root), **summary, "cost": record["cost"]}, indent=1))
        failed = RunDir(root).failed_calls()
        bad_replies = RunDir(root).model_failed_calls()
        if bad_replies:
            print(f"warning: {bad_replies} extractor call(s) got a model reply that did not validate or a prompt over "
                  f"the context window (in {root / 'calls'}); asking again repeats them, so --retry-errors skips them",
                  file=sys.stderr)
        if failed and args.allow_failed_calls:
            print(f"warning: {failed} extractor call(s) failed (status error or partial in {root / 'calls'})",
                  file=sys.stderr)
        elif failed:
            print(f"FAIL engine-errors {root} {failed}", file=sys.stderr)
            print(f"  {failed} extractor call(s) failed (status error or partial in calls/: the model gateway or the "
                  "GLiNER service did not answer). The run is kept, and the failed results are in the record cache: "
                  "once the service answers, run again into a new run dir with --retry-errors.", file=sys.stderr)
            return 2
        return 0
    if args.command == "estimate":
        from .estimate import estimate
        try:
            print(json.dumps(estimate(args.protocol, args.corpus, strategy=args.strategy, selection=args.extractors,
                                      from_run=args.from_run, names=args.names), indent=1))
        except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:   # unreadable protocol, corpus or run
            print(f"error: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "replay":
        from .replay import replay
        new, report = replay(args.run, cache=args.cache, corpus=args.corpus, out_dir=args.out)
        print(json.dumps({"run": str(new), **report}, indent=1))
        return 0 if report["ok"] else 1
    if args.command == "reexec":
        from .replay import reexec
        if args.times is not None:
            return _reexec_times(args)
        new = reexec(args.run, args.extractor, cache=args.cache, corpus=args.corpus, out_dir=args.out,
                     all_calls=args.all_calls)
        report = read_json(new / "reexec.json")
        print(json.dumps({"run": str(new), "summary": report["summary"], "totals": report["totals"]}, indent=1))
        return 0
    if args.command == "program":
        return _program(args)
    if args.command == "prov":
        from .prov import export
        path = export(args.run)
        print(path)
        return 0
    if args.command == "protocol":
        return _protocol_diff(args.a, args.b) if args.protocol_command == "diff" else _protocol_check(args.protocol)
    if args.command == "pack":
        return _pack_check(args.name)
    if args.command == "propose":
        return _propose(args)
    if args.command == "tune":
        return _tune(args)
    if args.command == "fetch":
        return arxiv.run(args)
    return _verify(args.run)


def _reexec_times(args: argparse.Namespace) -> int:
    """`reexec --all-calls --times N --out DIR`: N re-runs with no cache, then the re-run measure (stability.py)."""
    from . import stability
    from .readable import read_refusal
    from .rundir import RUN_CALLS_FILE
    from .replay import reexec
    problem = ("--times needs --all-calls" if not args.all_calls else "--times needs --out" if args.out is None
               else "the run folder is sealed; write the re-runs elsewhere"
               if args.out.resolve().is_relative_to(args.run.resolve())
               else "--times must be at least 1" if args.times < 1 else None)
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    if not (args.run / RUN_CALLS_FILE).is_file():
        print(f"error: {args.run} has no calls.jsonl: its model calls cannot be compared", file=sys.stderr)
        return 2
    try:
        why = read_refusal(args.run, args.corpus)
    except Exception as exc:   # any reason the answer cannot be read is a note; the other measures go on
        why = str(exc) or type(exc).__name__
    if why:
        print(f"note: the final answer of {args.run.name} cannot be compared ({why}); the call and item measures go on")
    news = [reexec(args.run, cache=args.cache, corpus=args.corpus, out_dir=args.out, all_calls=True)
            for _ in range(args.times)]
    try:
        report = stability.measure(args.run, news)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(stability.render(report)))
    write_json(args.out / "stability.json", report)
    return 0


def _verify(run: Path) -> int:
    """The chain (against run.json's head; a failed run has no run.json, so its chain is checked with no head) and
    the manifest's file hashes; a run made before sealing is judged on the chain only."""
    from . import seal
    head = read_json(run / RUN_FILE).get("chain_head") if (run / RUN_FILE).is_file() else None
    report = verify(run / EVENTS_FILE, head=head)
    manifest = seal.check(run)
    sealed = manifest == seal.PRE_EV4 or bool(manifest["intact"])
    print(json.dumps({"ok": report.ok and sealed, "records": report.records, "head": report.head, "chain_head": head,
                      "errors": report.errors, "manifest": manifest}, indent=1))
    return 0 if report.ok and sealed else 1


def pack_check(name: str, root: Path | None = None) -> dict[str, Any]:
    """`evidence pack check NAME` on `root/NAME/` (None: domains/): load the pack, register its types, check it has a
    type of every role its questions' kinds need, and validate every protocol file (each must name the pack). Returns
    {pack, sha256, types, kinds, protocols, question_protocols}; a failure raises (OSError, ValueError, YAMLError)."""
    from . import pack, questions
    from .protocol import load
    root = Path(root) if root is not None else pack.DOMAINS
    p = pack.load_pack(name, root=root)
    pack.register_pack(p)
    qfile = root / name / "questions.yaml"
    entries = questions.load(qfile) if qfile.is_file() else []
    kinds = sorted({q.kind for q in entries})
    pack.check(p, kinds)
    named = {questions.protocol_file(f, qfile) for q in entries for f in (q.protocol, q.agentic_protocol) if f}
    # every protocol of the pack, not only those questions.yaml names (a protocol kept for later must parse too)
    files = sorted({*(root / name / "protocols").glob("*.yaml"), *named})
    for path in files:
        try:
            domain = load(path, domains=root).domain
        except (OSError, ValueError, yaml.YAMLError) as exc:
            raise ValueError(f"{path}: {exc}") from exc
        if domain != name:
            raise ValueError(f"{path}: its domain is not {name!r}")
    return {"pack": p.name, "sha256": p.sha256, "types": {t: d.role.value for t, d in p.types.items()},
            "kinds": kinds, "protocols": len(files), "question_protocols": len(named)}


def _program(args: argparse.Namespace) -> int:
    """`evidence program RUN --out FILE`: write the run's readable program (UTF-8, LF); exit 2 when it cannot be made."""
    import subprocess

    import repo_paths

    from .readable import NotRebuilt, program_of_run
    out = args.out.resolve()
    if out.is_relative_to(args.run.resolve()):
        print("error: the run folder is sealed; write the program elsewhere", file=sys.stderr)
        return 2
    if out.is_relative_to(repo_paths.REPO.resolve()):   # a program quotes papers: inside the repo only when ignored
        try:
            ignored = subprocess.run(["git", "-C", str(repo_paths.REPO), "check-ignore", "-q", str(out)],
                                     capture_output=True).returncode
        except OSError:
            ignored = None
        if ignored == 1:
            print(f"error: {args.out} is in the repository and not git-ignored; a program quotes papers and stays "
                  "local", file=sys.stderr)
            return 2
        if ignored != 0:
            print(f"error: git could not {'be run' if ignored is None else 'check .gitignore'}, so {args.out} may "
                  "not be git-ignored; write the program outside the repository", file=sys.stderr)
            return 2
    try:
        text = program_of_run(args.run, args.corpus)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8", newline="\n")
    except (NotRebuilt, ValueError, OSError) as exc:   # UnicodeError is a ValueError
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(args.out)
    return 0


def _pack_check(name: str) -> int:
    try:
        report = pack_check(name)
    except (OSError, ValueError, yaml.YAMLError) as exc:   # PackError and pydantic's ValidationError are ValueErrors
        print(f"error: pack {name!r}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=1))
    return 0


def _protocol_diff(a: Path, b: Path) -> int:
    from . import lockfile
    try:
        lines = lockfile.diff(a, b)
    except (OSError, ValueError, yaml.YAMLError) as exc:   # a missing file, bad JSON or YAML
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0 if lines == ["same"] else 1


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
