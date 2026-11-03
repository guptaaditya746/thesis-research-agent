"""Open claim records (Task 5.1).

`find_claims` finds candidate sentences by regex (a subject word and a cue word in one sentence; both come from the
run's locked word list, never from code), then asks the DSPy step `ReadClaim` to confirm and read each one as a
`ClaimRecord`. `group_relations` puts the run's distinct verbs into groups with one `GroupRelations` call; a verb the
model cannot place gets its own group `other: <verb>` and is shown, never dropped. Grouping is a counts-as decision:
`grouped_line` is the text the answer shows, and a rerun with groups off just reads the raw `relation`.

Model calls go through `Step`. With a `ctx` (a `StageContext`) the step is given `ctx.dspy_lm(purpose)` per call, so
worker threads of two papers never record a call under each other's ctx (no lock); without one it runs on the
thread's model (`evidence.steps.using`) or the process default."""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from typing import Any, Literal

import dspy

from agent.anchor import selector_at
from .contract import DocumentRef, Span
from .extractors import base
from .records import ClaimRecord, item
from .steps import Step

__all__ = ["GroupRelations", "ReadClaim", "apply_groups", "candidate_sentences", "claim_stage", "count_by_group", "cue_words",
           "find_claims", "grouped_line", "group_relations", "run_step"]


class ReadClaim(dspy.Signature):
    """Read one sentence of a paper as a claim the authors make.

    Set is_claim to false when the sentence does not state a result or property of its subject (a question, a
    plan, a citation of other work, a definition). Otherwise fill: subject (the thing the claim is about, as
    written), relation (the paper's own verb or phrase, copied from the sentence), object (what the relation points
    at, or null), setting (conditions the sentence names, such as dataset or model, or empty), strength ("hedged" when the
    sentence softens it with words like suggests, may, appears; else "firm") and direction. Set direction only
    when the claim compares the subject with something else, and say whether the comparison turns out better
    for the subject (improves), worse (worsens) or the same (no_effect), judged by what is good for the measure:
    "shortens delays" is improves, "lengthens delays" is worsens. For any claim that is not a comparison direction
    is null.

    Example: "Method A shortens the delay." -> subject "Method A", relation "shortens", object "the delay", strength
    "firm", direction "improves".
    Example: "Our dataset is the largest of its kind." -> relation "is the largest", object "of its kind", direction null.
    Example: "The results suggest Method A may help." -> strength "hedged", direction null (nothing is compared)."""
    sentence: str = dspy.InputField(desc="one sentence of the paper, verbatim")
    is_claim: bool = dspy.OutputField(desc="true when the sentence states a claim of the authors")
    subject: str = dspy.OutputField(desc="what the claim is about, as written; empty when not a claim")
    relation: str = dspy.OutputField(desc="the paper's own verb or phrase, copied from the sentence")
    object: str | None = dspy.OutputField(desc="what the relation points at, or null")
    setting: dict[str, str] = dspy.OutputField(desc="named conditions such as dataset or model; {} when none")
    strength: Literal["firm", "hedged"] = dspy.OutputField(desc="hedged when the sentence softens the claim")
    direction: Literal["improves", "worsens", "no_effect"] | None = dspy.OutputField(
        desc="only for a comparison: better, worse or the same for the subject; otherwise null")


class GroupRelations(dspy.Signature):
    """Group verbs that make the same kind of claim.

    Put each verb of the list into exactly one group and name the group with one plain word or short phrase (the
    group's name). Verbs that mean the same thing go together, verbs that mean the opposite never do. Use only verbs
    from the list, copied exactly. Leave a verb out when you cannot place it.

    Example: ["speeds up", "accelerates", "slows"] -> {"faster": ["speeds up", "accelerates"], "slower": ["slows"]}."""
    verbs: list[str] = dspy.InputField(desc="the distinct verbs the papers use")
    groups: dict[str, list[str]] = dspy.OutputField(desc="group name -> the verbs placed in it")


_READ = Step(ReadClaim, "claims.read_claim")
_GROUP = Step(GroupRelations, "claims.group_relations")


def run_step(step: Step, ctx: Any | None, purpose: str, **inputs: Any) -> dspy.Prediction:
    """Run `step`; with a `ctx` on `ctx.dspy_lm(purpose)`, given to this call only."""
    if ctx is None:
        return step(**inputs)
    return step(lm=ctx.dspy_lm(purpose), **inputs)


def cue_words(cues: list[str]) -> list[str]:
    """The bare cue words of the locked list: "improves: outperforms" and "outperforms" both give "outperforms"."""
    return [c.split(": ", 1)[1] if ": " in c else c for c in cues]


def _stem(cue: str) -> str:
    low = cue.casefold().strip()
    for suffix in ("ing", "ed", "es", "s", "e"):
        if low.endswith(suffix) and len(low) - len(suffix) >= 4:
            return low[: -len(suffix)]
    return low


def _cue_pattern(cues: list[str]) -> re.Pattern[str]:
    parts = [re.escape(_stem(c)).replace(r"\ ", r"\s+") for c in cue_words(cues) if c.strip()]
    return re.compile(r"(?i)\b(?:%s)\w{0,3}\b" % "|".join(sorted(set(parts), key=len, reverse=True))) if parts else re.compile(r"(?!)")


_SKIP = re.compile(r"(?i)\bwhether\b|\?")


def candidate_sentences(text: str, config: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(start, end) of each sentence with a subject word and a cue word. config: {"subject": regex, "cues": [...]}."""
    subject = re.compile(config["subject"])
    cue = _cue_pattern(list(config["cues"]))
    return [(s, e) for s, e in base.sentences(text) if subject.search(text[s:e]) and cue.search(text[s:e])
            and not _SKIP.search(text[s:e])]


def find_claims(doc_text: str, document: DocumentRef, config: Mapping[str, Any], ctx: Any | None = None) -> list[ClaimRecord]:
    """The claims of one paper: regex candidates, each confirmed and read by `ReadClaim`. Deterministic given the
    recorded replies, so safe to run twice (the warm pass). A candidate the model rejects is dropped."""
    records: list[ClaimRecord] = []
    for s, e in candidate_sentences(doc_text, config):
        sentence = doc_text[s:e]
        out = run_step(_READ, ctx, "claims.read_claim", sentence=sentence)
        if not out.is_claim or not str(out.relation).strip():
            continue
        records.append(ClaimRecord(
            subject=str(out.subject).strip(), relation=str(out.relation).strip(),
            object=(str(out.object).strip() or None) if out.object is not None else None,
            setting={str(k): str(v) for k, v in (out.setting or {}).items()}, strength=out.strength,
            direction=out.direction,
            span=Span.of("claim", selector_at(doc_text, s, e, file=document.file, sha256=document.sha256))))
    return records


def claim_stage(config: Mapping[str, Any] | None = None):
    """An `after_document` stage function: `stages.register("claims", "after_document", claim_stage(...))`. Cues come
    from the confirmed plan's word list (`ctx.plan.words.cues`); the "subject" regex defaults to the plan's compiled
    subject (evidence.words.compile.compile_words: any name of any thing); `config` may give either instead."""
    def stage(doc, ctx):
        cfg = dict(config or {})
        if "cues" not in cfg:
            cfg["cues"] = ctx.plan.words.cues
        if "subject" not in cfg:
            from .words.compile import compile_words
            cfg["subject"] = compile_words(ctx.plan.words, metric_things=set(ctx.plan.measures))["subject"]
        return [item(r) for r in find_claims(doc.text, doc.doc, cfg, ctx=ctx)]
    return stage


def group_relations(verbs: list[str], ctx: Any | None = None) -> dict[str, str]:
    """{verb: group} for the run's distinct verbs, from one recorded call. A verb the model leaves out, or places in
    a group that is not a plain name, gets `other: <verb>`; a verb placed twice keeps its first group."""
    distinct = sorted({v.strip() for v in verbs if v.strip()}, key=str.casefold)
    if not distinct:
        return {}
    placed: dict[str, str] = {}
    out = run_step(_GROUP, ctx, "claims.group_relations", verbs=distinct)
    for name, members in (out.groups or {}).items():
        group = str(name).strip()
        if not group or group.startswith("other:"):
            continue
        for verb in members:
            if verb in distinct and verb not in placed:
                placed[verb] = group
    return {v: placed.get(v, f"other: {v}") for v in distinct}


def apply_groups(records: list[ClaimRecord], mapping: Mapping[str, str]) -> list[ClaimRecord]:
    """The records with `relation_group` filled from `mapping` (the paper's own `relation` is kept). A verb not in the
    mapping gets `other: <verb>`."""
    return [r.model_copy(update={"relation_group": mapping.get(r.relation, f"other: {r.relation}")}) for r in records]


def count_by_group(records: list[ClaimRecord]) -> dict[str, int]:
    """Claims per relation group (raw relation when a record has no group): what a query on a group counts."""
    return dict(Counter(r.relation_group or r.relation for r in records))


def grouped_line(mapping: Mapping[str, str]) -> str:
    """The counts-as line of the answer: "grouped: accelerates, speeds up → faster", one clause per group; unplaced verbs
    ("other: <verb>") are listed too."""
    by_group: dict[str, list[str]] = {}
    for verb, group in mapping.items():
        by_group.setdefault(group, []).append(verb)
    clauses = [f"{', '.join(sorted(vs, key=str.casefold))} → {g}" for g, vs in sorted(by_group.items())]
    return "grouped: " + "; ".join(clauses)
