"""`agent verify <run>` (row 1.11): one check of a finished run, plus its cost figures.

Checks, all reported (not only the first):
- the run directory is complete and valid (RunDir.validate with answer.json);
- the hash chain of events.jsonl, and claims.jsonl as its copy (agent/chain.py);
- the corpus manifest is the one in config.json, and every accepted claim's anchor resolves at
  its recorded offsets in the frozen corpus file (status "ok", agent/anchor.py);
- every claim id an answer fact cites is an accepted claim of this run;
- for a baseline run with an attach step (2.5): the step finished (attach.json), answer.json is the
  one it wrote, every fact has origin attach and cites only attach claims.

Figures: steps (model replies), commands, claims (accepted / rejected), claim steps (commands that
sent at least one claim), tokens (sum of total_tokens over model calls), and wall time from the
first record's start to the last record's end. With an attach step, the same figures for the
attach step alone (`attach`) and for the run without it (`without_attach`), so cost can be reported
with and without it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .anchor import Selector, read_text, resolve
from .canonical import file_sha256
from .chain import verify as verify_chain
from .concept import claim_ids
from .rundir import ATTACH_FILE, RunDir


@dataclass
class RunReport:
    errors: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _time(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _records(path: Path) -> list[dict[str, Any]]:
    out = []
    for raw in path.read_bytes().splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass  # reported by the chain check
    return out


def is_attach(record: dict[str, Any]) -> bool:
    """A record of the baseline's attach step (2.5): its model calls, commands, claims and coverage."""
    return (record.get("custom_metadata") or {}).get("origin") == "attach"


ATTACH_COST = ("steps", "model_calls", "commands", "claims_accepted", "claims_rejected", "coverage", "tokens",
               "prompt_tokens", "completion_tokens", "seconds")


def stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    """cost() of all records; with an attach step also `attach` (its own cost) and `without_attach`."""
    out = cost(records)
    attach = [r for r in records if is_attach(r)]
    if attach:
        mine, rest = cost(attach), cost([r for r in records if not is_attach(r)])
        out["attach"] = {k: mine[k] for k in ATTACH_COST}
        out["without_attach"] = {k: rest[k] for k in ATTACH_COST}
    return out


def cost(records: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [r for r in records if r["subtype"] == "ai_model_invocation"]
    tools = [r for r in records if r["subtype"] == "agent_tool"]
    claims = [r for r in records if r["subtype"] == "claim"]
    usage = [r["generated"].get("usage") or {} for r in calls]
    starts = [_time(r["started_at"]) for r in records if r.get("started_at")]
    ends = [_time(r["ended_at"]) for r in records if r.get("ended_at")]
    return {
        "steps": len({r["step_id"] for r in calls}), "model_calls": len(calls), "commands": len(tools),
        "claims": len(claims), "claims_accepted": sum(r["status"] == "accepted" for r in claims),
        "claims_rejected": sum(r["status"] == "rejected" for r in claims),
        "claim_steps": sum(bool(r["custom_metadata"].get("claim_step")) for r in tools),
        "claim_step_tokens": sum((r["generated"].get("usage") or {}).get("total_tokens", 0) for r in calls
                                 if r["step_id"] in {t["step_id"] for t in tools
                                                     if t["custom_metadata"].get("claim_step")}),
        "coverage": len([r for r in records if r["subtype"] == "coverage"]),
        "tokens": sum(u.get("total_tokens", 0) for u in usage),
        "prompt_tokens": sum(u.get("prompt_tokens", 0) for u in usage),
        "completion_tokens": sum(u.get("completion_tokens", 0) for u in usage),
        "seconds": round((max(ends) - min(starts)).total_seconds(), 3) if starts and ends else 0.0,
    }


def verify_run(run: RunDir, corpus: Path, manifest: Path) -> RunReport:
    report = RunReport()
    report.errors += [f"run: {p}" for p in run.validate(complete=True)]
    chain = verify_chain(run.events, run.claims)
    report.errors += [f"chain: {e}" for e in chain.errors]
    records = _records(run.events)
    report.stats = stats(records) | {"records": chain.records, "head": chain.head}

    hashes: dict[str, str] = {}
    try:
        config = run.load_config()
        if file_sha256(manifest) != config["hashes"]["corpus_manifest_sha256"]:
            report.errors.append(f"corpus: {manifest} is not the manifest recorded in config.json")
        papers = json.loads(Path(manifest).read_text(encoding="utf-8"))["papers"]
        hashes = {f"{p['id']}.md": p["markdown_sha256"] for p in papers if p.get("failure") is None}
    except (OSError, ValueError, KeyError) as exc:
        report.errors.append(f"corpus: cannot read the manifest ({exc})")

    accepted: set[str] = set()
    texts: dict[str, str] = {}
    for record in records:
        if record["subtype"] != "claim" or record["status"] != "accepted":
            continue
        claim_id = record["generated"].get("claim_id")
        if claim_id in accepted:
            report.errors.append(f"claim {claim_id}: id used twice")
        accepted.add(claim_id)
        try:
            selector = Selector(**record["used"]["anchor"])
        except (KeyError, TypeError) as exc:
            report.errors.append(f"claim {claim_id}: no usable anchor ({exc})")
            continue
        if selector.file not in hashes:
            report.errors.append(f"claim {claim_id}: {selector.file} is not in the manifest")
            continue
        if selector.file not in texts:
            try:
                texts[selector.file] = read_text(Path(corpus) / selector.file)
            except OSError as exc:
                report.errors.append(f"claim {claim_id}: cannot read {selector.file} ({exc})")
                continue
        result = resolve(selector, texts[selector.file], hashes[selector.file])
        if result.status != "ok":
            report.errors.append(f"claim {claim_id}: anchor {result.status} in {selector.file} ({result.reason})")

    try:
        answer = json.loads(run.answer.read_bytes())
        cited = claim_ids(answer)
        facts = [f for r in answer["rows"] for f in r["facts"]]
        report.stats |= {"rows": len(answer["rows"]), "facts": len(facts),
                         "facts_with_claims": sum(bool(f["claims"]) for f in facts)}
        report.errors += [f"answer: {c} is not an accepted claim of this run" for c in sorted(cited - accepted)]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.errors.append(f"answer: cannot check claim ids ({exc})")
        answer = None
    report.errors += _attach_problems(run, records, answer)
    return report


def _attach_problems(run: RunDir, records: list[dict[str, Any]], answer: dict[str, Any] | None) -> list[str]:
    """The attach step (2.5): finished if it started; every fact attach-origin, citing only attach claims."""
    try:
        config = run.load_config()
    except (OSError, ValueError):
        return []
    done = (run.root / ATTACH_FILE).is_file()
    if "attach" not in config:
        return ["attach: attach.json exists but config.json has no attach section"] if done else []
    if not done:
        return ["attach: the attach step started but did not finish (no attach.json)"]
    problems = []
    origin = {r["generated"].get("claim_id"): r["custom_metadata"].get("origin") for r in records
              if r["subtype"] == "claim" and r["status"] == "accepted"}
    summary = json.loads((run.root / ATTACH_FILE).read_bytes())
    if file_sha256(run.answer) != summary.get("answer_sha256"):
        problems.append("attach: answer.json is not the answer the attach step wrote")
    for fact in [f for r in (answer or {}).get("rows", []) for f in r["facts"]]:
        if fact["origin"] != "attach":
            problems.append(f"attach: fact {fact['id']} has origin {fact['origin']}, not attach")
        problems += [f"attach: fact {fact['id']} cites {c}, which is not an attach claim" for c in fact["claims"]
                     if origin.get(c) != "attach"]
    return problems
