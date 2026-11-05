"""`gold build | triage | pool | draft | status` (C1, M3): the evidence document D and what follows it.

    gold build q01 [--concept concepts/q01/concept.json] [--max-papers 20 | --only-papers p3,p7] [--replace]
    gold triage q01
    gold pool q01 [--sample 50 --seed 0] [--allow-partial]
    gold draft q01 [--allow-partial] [--allow-untriaged]
    gold status [q01] [--json]

Paths come from the environment like every component's (plan, "Environment"): $CORPUS (with its
manifest.json), $GOLD (default gold-data), $CONCEPTS (default concepts). Models: the sub-model
replicas through LiteLLM ($LITELLM_BASE_URL; the key only from $LITELLM_MASTER_KEY at call time).

`gold build` exits 0 when D is complete, 1 while calls failed that a rerun retries, 3 when only
failures a rerun cannot fix are left (gold/build.py `outcome`), 143 when stopped by SIGTERM.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import repo_paths
from typing import Any

from agent.concept import validate_concept

import modelcall
from .build import REPO, BuildSettings, BuildStopped, FolderInUse, QuestionDir, build, live_stage, outcome, read_jsonl
from .chunks import GoldCorpus


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, not {value}")
    return value


def _positive_float(text: str) -> float:
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be positive, not {value}")
    return value


def _gold_root(args: argparse.Namespace) -> Path:
    return Path(args.out or os.environ.get("GOLD") or "gold-data")


def _corpus(args: argparse.Namespace) -> GoldCorpus:
    root = args.corpus or os.environ.get("CORPUS")
    if not root:
        raise SystemExit("gold: give --corpus or set $CORPUS")
    return GoldCorpus(Path(root), Path(args.manifest or Path(root) / "manifest.json"))


def _rotation(args: argparse.Namespace) -> modelcall.Rotation:
    return modelcall.Rotation(aliases=tuple(a.strip() for a in args.models.split(",") if a.strip()))


def _settings(args: argparse.Namespace, **extra: Any) -> BuildSettings:
    try:
        return BuildSettings.from_env(concurrency=args.concurrency, call_timeout_s=args.timeout, **extra)
    except ValueError as exc:
        raise SystemExit(f"gold: {exc}") from None


def question_text(qid: str, concept_path: Path) -> str | None:
    """The question as asked: the concept session's session.json, else questions/questions.json."""
    session = concept_path.parent / "session.json"
    if session.is_file():
        found = json.loads(session.read_text(encoding="utf-8")).get("question")
        if found:
            return str(found)
    questions = repo_paths.QUESTIONS_FILE
    if questions.is_file():
        data = json.loads(questions.read_text(encoding="utf-8"))
        for row in data.get("questions", []) if isinstance(data, dict) else data:
            if row.get("id") == qid:
                return str(row["question"])
    return None


def cmd_build(args: argparse.Namespace) -> int:
    concept_path = Path(args.concept or Path(os.environ.get("CONCEPTS") or "concepts") / args.qid / "concept.json")
    if not concept_path.is_file():
        raise SystemExit(f"gold: no concept at {concept_path}; pick one first (agent concepts pick) or give --concept")
    concept = json.loads(concept_path.read_text(encoding="utf-8"))
    problems = validate_concept(concept)
    if problems:
        raise SystemExit(f"gold: {concept_path} is not a valid concept: {problems[:5]}")
    only = tuple(p.strip() for p in (args.only_papers or "").split(",") if p.strip())
    settings = _settings(args, chunk_chars=args.chunk_chars, max_papers=args.max_papers, only_papers=only)
    try:
        doc = build(args.qid, concept, _corpus(args), _gold_root(args), rotation=_rotation(args), settings=settings,
                    question=args.question or question_text(args.qid, concept_path),
                    log=lambda line: print(line, flush=True), replace=args.replace)
    except FolderInUse as exc:
        raise SystemExit(f"gold: {exc}") from None
    except BuildStopped as exc:
        print(exc, flush=True)
        return 143
    code, advice = outcome(doc)
    if advice:
        print(f"{args.qid}: {advice}", flush=True)
    return code


def cmd_triage(args: argparse.Namespace) -> int:
    from .triage import triage

    counts = triage(args.qid, _gold_root(args), _corpus(args), _rotation(args), settings=_settings(args),
                    batch=args.batch, log=lambda line: print(line, flush=True))
    return 1 if counts["unsorted"] else 0


def cmd_pool(args: argparse.Namespace) -> int:
    from .pool import build_pool

    try:
        strata = build_pool(args.qid, _gold_root(args), _corpus(args), sample=args.sample, seed=args.seed,
                            tiers=tuple(t.strip() for t in args.tiers.split(",") if t.strip()),
                            allow_partial=args.allow_partial)
    except ValueError as exc:
        raise SystemExit(f"gold: {exc}") from None
    print(f"{args.qid}: {strata['records']} review records ({strata['reviewed_tiers']} in {'+'.join(strata['tiers'])} "
          f"or unsorted, {strata['sampled']} sampled of {strata['rest']} others)"
          + (f", PARTIAL: {strata['partial_reason']}" if strata["partial"] else "")
          + f" -> {QuestionDir(_gold_root(args) / args.qid).pool}")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    from .draft import draft_key

    try:
        key = draft_key(args.qid, _gold_root(args), allow_partial=args.allow_partial,
                        allow_untriaged=args.allow_untriaged)
    except ValueError as exc:
        raise SystemExit(f"gold: {exc}") from None
    c = key["counts"]
    print(f"{args.qid}: draft key with {c['rows']} rows, {c['facts']} facts from {c['kept']} of {c['candidates']} "
          f"candidates (skipped {c['skipped']})" + (" PARTIAL" if key["built"]["partial"] else "")
          + f" -> {QuestionDir(_gold_root(args) / args.qid).draft}")
    return 0


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def status(gold_root: Path, qid: str | None = None) -> list[dict[str, Any]]:
    """Per question folder: build stage and progress, D's coverage and counts, triage, pool, draft, key.
    A build that progress.json says is running but whose process is gone is `dead` (same host) or
    `stale` (no progress for twice the call timeout); a draft key or pool made for another concept
    than D's is marked `stale`."""
    from .triage import load_labels

    if qid:
        folders = [gold_root / qid]
    else:
        folders = sorted(p for p in gold_root.glob("*") if p.is_dir() and not p.name.startswith("."))
    out = []
    for folder in folders:
        qdir = QuestionDir(folder)
        progress, doc = _load(qdir.progress) or {}, _load(qdir.doc)
        concept_hash = doc.get("concept_sha256") if doc else None
        labels = load_labels(qdir, concept_hash) if doc else {}
        candidates = len(read_jsonl(qdir.candidates)) if doc else 0
        strata, draft, key = _load(qdir.strata), _load(qdir.draft), _load(qdir.key)
        stage = live_stage(progress) if progress else ("done" if doc else "not started")
        out.append({
            "qid": folder.name, "stage": stage, "progress": progress or None,
            "coverage": doc["coverage"] if doc else None, "counts": doc["counts"] if doc else None,
            "triage": {**{lab: sum(v == lab for v in labels.values()) for lab in ("answers", "context", "irrelevant")},
                       "unsorted": max(0, candidates - len(labels))} if labels else None,
            "pool": {"records": strata["records"], "sampled": strata["sampled"], "partial": strata.get("partial"),
                     "stale": strata.get("concept_sha256", concept_hash) != concept_hash} if strata else None,
            "draft": {**draft["counts"], "partial": draft.get("built", {}).get("partial"),
                      "stale": draft.get("concept_sha256") != concept_hash} if draft else None,
            "key": {"version": key.get("version"), "rows": len(key.get("rows", [])),
                    "stale": key.get("concept_sha256") != concept_hash} if key else None,
        })
    return out


def _status_line(s: dict[str, Any]) -> str:
    parts = [f"{s['qid']:8} {s['stage']}"]
    p = s["progress"] or {}
    if s["stage"] not in ("done", "not started") and p.get("papers"):
        parts.append(f"papers {p['papers']['done']}/{p['papers']['total']}, candidates {p.get('candidates', 0)}")
    if s["coverage"]:
        cov, c = s["coverage"], s["counts"]
        parts.append(f"papers {cov['papers']} (relevant {cov['relevant']}, not {cov['not_relevant']}, "
                     f"no text {cov['no_text']}, error {cov['error']})" + (" partial" if cov.get("partial") else ""))
        parts.append(f"candidates {c['candidates']} (anchored {c['anchored']}), rows {c['rows']}")
    if s["triage"]:
        t = s["triage"]
        parts.append(f"triage answers {t['answers']}, context {t['context']}, irrelevant {t['irrelevant']}"
                     + (f", unsorted {t['unsorted']}" if t["unsorted"] else ""))
    if s["pool"]:
        parts.append(f"pool {s['pool']['records']}" + (" partial" if s["pool"]["partial"] else "")
                     + (" stale" if s["pool"]["stale"] else ""))
    if s["draft"]:
        parts.append(f"draft {s['draft']['rows']} rows" + (" partial" if s["draft"]["partial"] else "")
                     + (" stale" if s["draft"]["stale"] else ""))
    if s["key"]:
        parts.append(f"key {s['key']['version']} {s['key']['rows']} rows" + (" stale" if s["key"]["stale"] else ""))
    if p.get("updated_at") and s["stage"] not in ("done",):
        parts.append(f"updated {p['updated_at']}")
    return " · ".join(parts)


def cmd_status(args: argparse.Namespace) -> int:
    found = status(_gold_root(args), args.qid)
    if args.json:
        print(json.dumps(found, ensure_ascii=False, indent=2))
        return 0
    if not found:
        print(f"no gold folders under {_gold_root(args)}")
    for s in found:
        print(_status_line(s))
    return 0


def _common(p: argparse.ArgumentParser, *, corpus: bool = False, models: bool = False) -> None:
    p.add_argument("--out", type=Path, help="gold working directory (default: $GOLD, else gold-data)")
    if corpus:
        p.add_argument("--corpus", type=Path, help="frozen Markdown corpus (default: $CORPUS)")
        p.add_argument("--manifest", type=Path, help="corpus manifest (default: <corpus>/manifest.json)")
    if models:
        p.add_argument("--models", default=",".join(modelcall.SUB_ALIASES),
                       help="LiteLLM aliases used in turn (default: %(default)s)")
        p.add_argument("--concurrency", type=_positive_int, help="calls in flight (default: $GOLD_CONCURRENCY, else 6)")
        p.add_argument("--timeout", type=_positive_float,
                       help="seconds per call (default: $GOLD_CALL_TIMEOUT_S, else 300)")


def register(subparsers: Any) -> None:
    """Add C1's subcommands to the `gold` parser."""
    p = subparsers.add_parser("build", help="build the evidence document D of one question (resumable)")
    p.add_argument("qid")
    p.add_argument("--concept", type=Path, help="concept brief (default: $CONCEPTS/<qid>/concept.json)")
    p.add_argument("--question", help="question text (default: the concept session's, else questions/questions.json)")
    p.add_argument("--max-papers", type=_positive_int, help="a trial: only the first N papers of the manifest")
    p.add_argument("--only-papers", help="a trial: only these papers (comma-separated ids)")
    p.add_argument("--chunk-chars", type=_positive_int, help="largest chunk (default: $GOLD_CHUNK_CHARS, else 40000)")
    p.add_argument("--replace", action="store_true",
                   help="replace a D built for another concept (moved to superseded/) or over the whole corpus")
    _common(p, corpus=True, models=True)
    p.set_defaults(func=cmd_build)

    p = subparsers.add_parser("triage", help="sort every candidate into answers / context / irrelevant (resumable)")
    p.add_argument("qid")
    p.add_argument("--batch", type=_positive_int, default=20, help="candidates per call (default: %(default)s)")
    _common(p, corpus=True, models=True)
    p.set_defaults(func=cmd_triage)

    p = subparsers.add_parser("pool", help="the review records: answers + context candidates and a sample of the rest")
    p.add_argument("qid")
    p.add_argument("--sample", type=int, default=50, help="irrelevant candidates sampled (default: %(default)s)")
    p.add_argument("--seed", default="0", help="sample and order seed (default: %(default)s)")
    p.add_argument("--tiers", default="answers,context", help="labels reviewed in full (default: %(default)s)")
    p.add_argument("--allow-partial", action="store_true", help="draw from a trial or a D with failed calls")
    _common(p, corpus=True)
    p.set_defaults(func=cmd_pool)

    p = subparsers.add_parser("draft", help="key.draft.json from triage alone (before review)")
    p.add_argument("qid")
    p.add_argument("--allow-partial", action="store_true", help="draft from a trial or a D with failed calls")
    p.add_argument("--allow-untriaged", action="store_true", help="leave candidates without a triage label out")
    _common(p)
    p.set_defaults(func=cmd_draft)

    p = subparsers.add_parser("status", help="build progress, coverage, triage, pool, draft and key per question")
    p.add_argument("qid", nargs="?")
    p.add_argument("--json", action="store_true", help="one JSON list instead of lines")
    _common(p)
    p.set_defaults(func=cmd_status)
