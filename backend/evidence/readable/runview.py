"""Read a finished run's answer: its kind, rules, plan, names, answer, items and (when readable) paper texts.

`read_run` refuses, with a plain reason, every run a readable program does not rebuild yet. `view_of` is the
projection of an answer that a rebuild must equal (item ids left out); `answer_text` and `headline` are the text and
the one-line result shown for it."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import reasoner, written
from ..contract import Item
from ..kindtext import kind_lines, plan_names
from ..pack import RoleMap
from ..plan import Plan, load_plan
from ..protocol import Protocol, parse
from ..rundir import ANSWER_FILE, PLAN_FILE, PROTOCOL_FILE, REASON_FILE, Corpus, PaperIndex, RunDir

__all__ = ["KIND_NOT_REBUILT", "KINDS", "LINES", "NAME_GROUPS", "NO_RULES", "NO_WRITTEN", "NOT_COMPLETE",
           "NOT_FOUND_AGAIN", "SUBSETS", "WRITER_FAILED", "NotRebuilt", "RunAnswer", "answer_text", "checked_view",
           "headline", "read_refusal", "read_run", "view_of"]

KINDS = ("effect", "consistency", "inventory", "best", "written")
NOT_COMPLETE = "the run is not complete (state {state})"
NO_RULES = "the run has no protocol.yaml (a baseline run): there are no rules to rebuild"
LINES = ("a plan answered by its lines (the plan page's own answer) is not rebuilt by a readable program yet; "
         "choose a fixed kind or a written answer")
KIND_NOT_REBUILT = "the kind {kind} is not rebuilt by a readable program yet"
SUBSETS = "an answer by subsets (the protocol's moderators) is not rebuilt by a readable program yet"
NAME_GROUPS = ("a {kind} run with the names step on is not rebuilt by a readable program yet (its rules read the "
               "name groups)")
NO_WRITTEN = "the run has no written answer"
WRITER_FAILED = "the written answer's model call failed: {reason}; run it again with retry"
NOT_FOUND_AGAIN = "the {what} the run used for {paper} could not be found again"
WRITTEN_FILE = f"{written.STAGE}.json"


class NotRebuilt(ValueError):
    """The run cannot be rebuilt by a readable program; the message says why."""


@dataclass(frozen=True)
class RunAnswer:
    run: Path
    kind: str
    protocol: Protocol
    roles: RoleMap
    plan: Plan | None
    names: dict[str, str]
    answer: dict[str, Any]
    items: dict[str, list[Item]]
    texts: dict[str, str] | None
    record: dict[str, Any]
    outputs: dict[str, str]
    inferred: Any | None = None


def _group(run: RunDir, corpus: Path | str) -> dict[str, list[Item]]:
    """The run's items by paper: by the corpus manifest when it reads, else by each item's first span file stem."""
    try:
        return PaperIndex.of_corpus(corpus).group(run.items())
    except (OSError, ValueError, KeyError):
        by: dict[str, list[Item]] = {}
        for item in run.items():
            file = str(item.spans[0].selector.get("file", "")) if item.spans else ""
            by.setdefault(Path(file).stem, []).append(item)
        return by


def _texts(corpus: Path | str) -> dict[str, str] | None:
    try:
        papers = Corpus(corpus)
        return {p.id: papers.text(p) for p in papers.papers}
    except (OSError, ValueError, KeyError):
        return None


def read_run(run: Path | str, corpus: Path | str | None = None, *, texts: bool = True) -> RunAnswer:
    """The run's answer, or NotRebuilt (refusals checked in the order of their texts above)."""
    rd = RunDir(run)
    if rd.state != "complete":
        raise NotRebuilt(NOT_COMPLETE.format(state=rd.state))
    protocol_file = rd.file(PROTOCOL_FILE)
    if not protocol_file.is_file():
        raise NotRebuilt(NO_RULES)
    settings = rd.settings
    plan = load_plan(rd.file(PLAN_FILE)) if rd.file(PLAN_FILE).is_file() else None
    if plan is not None and plan.answer_by == "lines":
        raise NotRebuilt(LINES)
    protocol = parse(protocol_file.read_text(encoding="utf-8"), settings.domains if settings is not None else None)
    kind = "written" if plan is not None and plan.answer_by == "written" else protocol.kind
    if kind not in KINDS:
        raise NotRebuilt(KIND_NOT_REBUILT.format(kind=kind))
    if kind in ("effect", "consistency") and protocol.synthesis is not None and protocol.synthesis.moderators:
        raise NotRebuilt(SUBSETS)
    if kind in ("best", "inventory") and settings is not None and settings.names == "on":
        raise NotRebuilt(NAME_GROUPS.format(kind=kind))
    if kind == "written":
        out = rd.try_json(WRITTEN_FILE)
        if not isinstance(out, dict):
            raise NotRebuilt(NO_WRITTEN)
        if "failed" in out:
            raise NotRebuilt(WRITER_FAILED.format(reason=out["failed"]))
        answer = out
    else:
        whole = rd.json(ANSWER_FILE) or {}
        answer = (whole.get("synthesis") or {}) if plan is not None else whole
    where = corpus if corpus is not None else (settings.corpus if settings is not None else None)
    if where is None:
        raise ValueError(f"run {run} names no corpus (run.json settings); give the corpus")
    record = rd.record or {}
    reason = rd.try_json(REASON_FILE)
    roles = rd.roles()
    assert roles is not None
    return RunAnswer(run=Path(run), kind=kind, protocol=protocol, roles=roles, plan=plan,
                     names=plan_names(plan) if plan is not None else {}, answer=answer, items=_group(rd, where),
                     texts=_texts(where) if texts else None, record=record,
                     outputs=dict(record.get("outputs") or {}),
                     inferred=reasoner.from_json(reason) if isinstance(reason, dict) else None)


def read_refusal(run: Path | str, corpus: Path | str | None = None) -> str | None:
    """Why `read_run` refuses the run, None when it does not."""
    try:
        read_run(run, corpus, texts=False)
    except NotRebuilt as exc:
        return str(exc)
    return None


def _pick(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: source.get(k) for k in keys}


def _effect_view(answer: dict[str, Any]) -> dict[str, Any]:
    studies = []
    for s in answer.get("studies", []):
        treatment, control = s.get("treatment") or {}, s.get("control") or {}
        claim = s.get("author_claim") or {}
        studies.append({"document": s.get("document"), "direction": s.get("direction"), "delta": s.get("delta"),
                        "metric": s.get("metric"), "treatment_value": treatment.get("value"),
                        "control_value": control.get("value"), "claim": claim.get("direction"),
                        "claim_agrees": claim.get("agrees_with_data"), "reason": s.get("reason"),
                        "flags": s.get("flags"), "duplicate_of": s.get("duplicate_of")})
    return {**_pick(answer, ("label", "counts", "supporting", "contradicting", "neutral", "undetermined",
                             "duplicates", "flags")), "studies": studies}


def view_of(kind: str, answer: dict[str, Any]) -> dict[str, Any]:
    """The projection of the kind's answer that a rebuild must equal (item ids left out)."""
    if kind == "effect":
        return _effect_view(answer)
    if kind == "consistency":
        return {**_pick(answer, ("metric", "agreeing", "disagreeing", "undetermined")),
                "studies": [_pick(s, ("document", "claim", "direction", "agrees", "reason"))
                            for s in answer.get("studies", [])]}
    if kind == "best":
        return {**_pick(answer, ("metric", "wins", "winner", "tied")),
                "studies": [_pick(s, ("document", "winner", "tied", "values", "reason"))
                            for s in answer.get("studies", [])]}
    if kind == "inventory":
        return {"target": answer.get("target"),
                "entries": [_pick(e, ("name", "aliases", "papers")) for e in answer.get("entries", [])]}
    if kind == "written":
        return {"status": answer.get("status"), "answer_text": answer.get("answer_text"),
                "tries": [t.get("problems") for t in answer.get("tries", [])],
                "sentences": answer.get("sentences"), "fact_texts": [f.get("text") for f in answer.get("facts", [])]}
    raise NotRebuilt(KIND_NOT_REBUILT.format(kind=kind))


def checked_view(ra: RunAnswer) -> dict[str, Any]:
    return view_of(ra.kind, ra.answer)


def answer_text(ra: RunAnswer) -> str:
    if ra.kind == "written":
        return ra.answer["answer_text"]
    return "\n".join(line.text for line in kind_lines(ra.protocol, ra.answer, ra.names))


def _count(value: Any) -> Any:
    return len(value) if isinstance(value, (list, tuple)) else value


def headline(ra: RunAnswer) -> str:
    a = ra.answer
    if ra.kind == "effect":
        return str(a.get("label"))
    if ra.kind == "consistency":
        return f"agreeing {_count(a.get('agreeing'))}, disagreeing {_count(a.get('disagreeing'))}"
    if ra.kind == "best":
        if a.get("winner"):
            return str(a["winner"])
        return f"tie: {', '.join(a['tied'])}" if a.get("tied") else "none"
    if ra.kind == "inventory":
        return ", ".join(e["name"] for e in a.get("entries", []))
    return str(a.get("status"))
