"""Link setting sets (plan v2 step 3): are two setting sets the same on the dimensions that matter?

    links = run(spec, rows, cfg, lm=None, verifier=None)      # run.py writes <qid>/links.jsonl

Only pairs Answer must compare are judged (code picks them, capped by `cfg.links.max_pairs`):
  question pairs  QUESTION vs every setting set of a candidate row (checked quote, spec subject), on the fixed
                  dimensions the row itself does not carry (row-level slots are compared by Answer per row).
  set pairs       two setting sets of different papers that both hold candidate rows of one subject, on the open
                  dimensions (so Answer can put their rows in one cell). Two sets of one paper were read as distinct
                  combinations: "different" by code, no call.
Per pair (docs/prompt-writing.md): one generator call (LinkSettings: verdict, differing dimensions, a quote from
each side) and one separate blind verifier call (VerifyLink: verdict and differing dimensions, no generator output).
Code checks: verdict on the list; differing keys are judged keys; "same" has none, "different" has some; each quote
lies inside one of its side's setting quotes (anchor normalisation; the question side: inside the question text).
Failed checks: one repair call with them, then "unknown". Accepted verdict = the generator's when the checks pass and
the verifier gives the same verdict, else "unknown" (disagreement kept: both verdicts stay in the Link).
Code only, no call: identical stated values on every judged dimension -> "same"; nothing stated on one side ->
"unknown". Pairs over the cap -> "unknown" (by="cap").
"""
from __future__ import annotations

import json
import logging
from itertools import combinations
from typing import Literal

import dspy
from pydantic import BaseModel, Field

from evqa.contracts import QUESTION, Dimension, Link, LinkConfig, Row, RunConfig, Setting, SettingSet, Spec
from evqa.extract import anchor
from evqa.llm import service_failed

log = logging.getLogger(__name__)
NOT_STATED = "not stated"
VERDICTS = ("same", "different", "unknown")
from evqa.spec.dimensions_v3 import ROW_FIELDS   # dimensions a Row carries itself; Answer checks them per row


class LinkDraft(BaseModel):
    verdict: Literal["same", "different", "unknown"] = "unknown"
    differs_on: list[str] = Field(default_factory=list)
    quote_a: str = ""
    quote_b: str = ""


class LinkSettings(dspy.Signature):
    """Decide whether two setting sets describe the same conditions on the listed dimensions.

    Input: dimensions is a JSON list of {key, question}; set_a and set_b are JSON lists of {dimension, value,
    quote}, each quote copied from that side's source. feedback lists failed checks of an earlier reply, if any.
    Output: verdict "same" (every listed dimension means the same condition on both sides), "different" (at least
    one listed dimension clearly differs), or "unknown" (a side does not state a dimension, or the wording does not
    settle it). differs_on lists the dimension keys that differ (empty unless different). quote_a and quote_b are
    copied from one quote of set_a and of set_b that support the verdict ("" for unknown).

    Medicine: dimensions [{"key":"population"}], set_a [{"dimension":"population","value":"adults with asthma",
    "quote":"adults with asthma were enrolled"}], set_b [{"dimension":"population","value":"asthmatic adults",
    "quote":"We recruited asthmatic adults"}] -> {"verdict":"same","differs_on":[],"quote_a":"adults with asthma",
    "quote_b":"asthmatic adults"}.
    Materials: dimensions [{"key":"processing"}], set_a value "annealed at 600 C", set_b value "as-cast" ->
    {"verdict":"different","differs_on":["processing"],"quote_a":"annealed at 600 C","quote_b":"as-cast"}.
    ML: dimensions [{"key":"prompting"}], set_a value "few-shot", set_b value "not stated" ->
    {"verdict":"unknown","differs_on":[],"quote_a":"","quote_b":""}.
    A narrower condition is not the same as a broader one (children with asthma vs patients with asthma: different).
    """
    dimensions: str = dspy.InputField()
    set_a: str = dspy.InputField()
    set_b: str = dspy.InputField()
    feedback: str = dspy.InputField()
    link: LinkDraft = dspy.OutputField()


class VerifyVerdict(BaseModel):
    verdict: Literal["same", "different", "unknown"] = "unknown"
    differs_on: list[str] = Field(default_factory=list)


class VerifyLink(dspy.Signature):
    """Independently check whether two setting sets describe the same conditions on the listed dimensions.

    Input: dimensions is a JSON list of {key, question}; set_a and set_b are JSON lists of {dimension, value, quote}.
    Output: verdict "same", "different" or "unknown" and differs_on, the differing dimension keys. Judge only from the
    values and quotes given; a missing or vague value gives "unknown"; a narrower condition is different from a
    broader one. Example: temperature "500 C" vs "500 degrees Celsius" -> same; dataset "test split" vs "validation
    split" -> different, ["dataset"]; population "adults" vs "not stated" -> unknown.
    """
    dimensions: str = dspy.InputField()
    set_a: str = dspy.InputField()
    set_b: str = dspy.InputField()
    verdict: VerifyVerdict = dspy.OutputField()


# ---------------------------------------------------------------- pairs
def candidates(spec: Spec, rows: list[Row]) -> list[Row]:
    """Rows Answer could use: checked quote, not dropped, with a setting set, of a spec subject (any if none)."""
    labels = {s.label.lower() for s in spec.subjects}
    return [r for r in rows if r.quote_ok and not r.dropped and r.setting_set is not None
            and (not labels or r.subject.lower() in labels)]


def fixed_dims(spec: Spec) -> list[Dimension]:
    """Fixed dimensions the question links decide (row-level slots are compared per row by Answer)."""
    return [d for d in spec.dimensions if d.fixed_value and d.key not in ROW_FIELDS]


def open_dims(spec: Spec) -> list[Dimension]:
    return [d for d in spec.dimensions if not d.fixed_value and d.key not in ROW_FIELDS]


def question_set(spec: Spec) -> SettingSet:
    return SettingSet(id=QUESTION, paper="", settings=[Setting(dimension=d.key, value=d.fixed_value, quote=d.quote)
                                                       for d in fixed_dims(spec)])


def pairs(spec: Spec, rows: list[Row]) -> list[tuple[SettingSet, SettingSet, list[Dimension]]]:
    """The pairs Answer must compare, in a fixed order: question pairs first, then cross-paper set pairs."""
    cand = candidates(spec, rows)
    sets: dict[str, SettingSet] = {}
    subjects: dict[str, set[str]] = {}
    for r in cand:
        sets.setdefault(r.setting_set.id, r.setting_set)
        subjects.setdefault(r.setting_set.id, set()).add(r.subject.lower())
    out: list[tuple[SettingSet, SettingSet, list[Dimension]]] = []
    fixed, open_ = fixed_dims(spec), open_dims(spec)
    if fixed:
        q = question_set(spec)
        out += [(q, sets[k], fixed) for k in sorted(sets)]
    if open_:
        for a, b in combinations(sorted(sets), 2):
            if subjects[a] & subjects[b]:
                out.append((sets[a], sets[b], open_))
    return out


# ---------------------------------------------------------------- checks
def _view(s: SettingSet, dims: list[Dimension]) -> list[dict]:
    keys = [d.key for d in dims]
    by = {x.dimension: x for x in s.settings}
    return [{"dimension": k, "value": by[k].value if k in by else NOT_STATED, "quote": by[k].quote if k in by else ""}
            for k in keys]


def _inside(quote: str, side: SettingSet, question: str) -> bool:
    n = anchor.normalize(quote)
    if not n:
        return False
    if side.id == QUESTION:
        return n in anchor.normalize(question)
    return any(n in anchor.normalize(x.quote) for x in side.settings if x.quote)


def check(draft: LinkDraft, a: SettingSet, b: SettingSet, dims: list[Dimension], question: str) -> list[str]:
    keys = {d.key for d in dims}
    fails = []
    if draft.verdict not in VERDICTS:
        fails.append(f"verdict {draft.verdict!r} is not same, different or unknown")
    if set(draft.differs_on) - keys:
        fails.append(f"differs_on has keys that were not judged: {sorted(set(draft.differs_on) - keys)}")
    if draft.verdict == "same" and draft.differs_on:
        fails.append("verdict same but differs_on is not empty")
    if draft.verdict == "different" and not draft.differs_on:
        fails.append("verdict different but differs_on is empty")
    if draft.verdict in ("same", "different"):
        if not _inside(draft.quote_a, a, question):
            fails.append("quote_a is not inside a quote of set_a")
        if not _inside(draft.quote_b, b, question):
            fails.append("quote_b is not inside a quote of set_b")
    return fails


def by_code(a: SettingSet, b: SettingSet, dims: list[Dimension]) -> Link | None:
    """The cases code decides without a call (module doc), else None."""
    keys = [d.key for d in dims]
    if a.id != QUESTION and a.paper == b.paper:
        return Link(a=a.id, b=b.id, dimensions=keys, verdict="different", by="code",
                    note="two setting sets of one paper are distinct combinations")
    va, vb = _view(a, dims), _view(b, dims)
    if any(x["value"] == NOT_STATED for x in va) or any(x["value"] == NOT_STATED for x in vb):
        if all(x["value"] == NOT_STATED for x in vb) or all(x["value"] == NOT_STATED for x in va):
            return Link(a=a.id, b=b.id, dimensions=keys, verdict="unknown", by="code",
                        note="one side states none of the dimensions")
        return None
    if all(anchor.normalize(x["value"]).lower() == anchor.normalize(y["value"]).lower() for x, y in zip(va, vb, strict=True)):
        return Link(a=a.id, b=b.id, dimensions=keys, verdict="same", by="code", note="identical stated values")
    return None


# ---------------------------------------------------------------- calls
def judge(a: SettingSet, b: SettingSet, dims: list[Dimension], question: str, lm: dspy.BaseLM,
          verifier: dspy.BaseLM | None, use_verifier: bool = True) -> Link:
    keys = [d.key for d in dims]
    link = Link(a=a.id, b=b.id, dimensions=keys)
    dims_j = json.dumps([{"key": d.key, "question": d.question} for d in dims])
    sa, sb = json.dumps(_view(a, dims)), json.dumps(_view(b, dims))
    feedback, draft, fails = "", None, ["no reply"]
    for attempt in range(2):
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                out = dspy.Predict(LinkSettings)(dimensions=dims_j, set_a=sa, set_b=sb, feedback=feedback,
                                                 config={"attempt": attempt} if attempt else {})
            draft = out.link if isinstance(out.link, LinkDraft) else LinkDraft.model_validate(out.link)
            fails = check(draft, a, b, dims, question)
        except Exception as exc:   # noqa: BLE001 - an unreadable reply is one failed attempt
            if service_failed(exc):
                raise
            draft, fails = None, [f"unreadable reply: {type(exc).__name__}"]
        if not fails:
            break
        feedback = ("Rejected output: " + (draft.model_dump_json() if draft else "unreadable")
                    + "\nFailed checks: " + "; ".join(fails))
    if draft is not None:
        link.generator, link.differs_on, link.quote_a, link.quote_b = (draft.verdict, list(draft.differs_on),
                                                                      draft.quote_a, draft.quote_b)
    if fails:
        link.verdict, link.note = "unknown", "generator failed checks: " + "; ".join(fails)
        return link
    if not use_verifier:
        link.verdict, link.note = draft.verdict, "verifier off (ablation)"
        return link
    try:
        with dspy.context(lm=verifier or lm, adapter=dspy.JSONAdapter()):
            out = dspy.Predict(VerifyLink)(dimensions=dims_j, set_a=sa, set_b=sb)
        ver = out.verdict if isinstance(out.verdict, VerifyVerdict) else VerifyVerdict.model_validate(out.verdict)
        link.verifier = ver.verdict
    except Exception as exc:   # noqa: BLE001
        if service_failed(exc):
            raise
        link.verdict, link.note = "unknown", f"verifier failed: {type(exc).__name__}"
        return link
    if ver.verdict == draft.verdict:
        link.verdict = draft.verdict
    else:
        link.verdict, link.note = "unknown", f"generator {draft.verdict}, verifier {ver.verdict}: kept apart"
    return link


def run(spec: Spec, rows: list[Row], cfg: RunConfig, lm: dspy.BaseLM | None = None,
        verifier: dspy.BaseLM | None = None) -> list[Link]:
    """Links for the pairs Answer must compare (module doc)."""
    todo = pairs(spec, rows)
    if not todo:
        return []
    links_cfg = cfg.links or LinkConfig()
    out: list[Link] = []
    calls = 0
    for a, b, dims in todo:
        done = by_code(a, b, dims)
        if done is not None:
            out.append(done)
            continue
        if calls >= links_cfg.max_pairs:
            out.append(Link(a=a.id, b=b.id, dimensions=[d.key for d in dims], by="cap",
                            note=f"not judged: more than {links_cfg.max_pairs} pairs"))
            continue
        if lm is None:
            from evqa.lm import make_lm
            lm = make_lm(cfg.llm_for("link"))
        calls += 1
        out.append(judge(a, b, dims, spec.question, lm, verifier, links_cfg.verifier))
    return out


# ---------------------------------------------------------------- groups (used by Answer, code only)
def components(links: list[Link]) -> dict[str, str]:
    """Setting-set id -> representative id: connected components of accepted "same" links between sets, never
    joining two components that hold a pair with an accepted "different" link (that merge is skipped)."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    apart = [(lk.a, lk.b) for lk in links if lk.verdict == "different" and QUESTION not in (lk.a, lk.b)]
    for lk in links:
        if QUESTION in (lk.a, lk.b):
            continue
        find(lk.a), find(lk.b)
    for lk in sorted((x for x in links if x.verdict == "same" and QUESTION not in (x.a, x.b)), key=lambda x: (x.a, x.b)):
        ra, rb = find(lk.a), find(lk.b)
        if ra == rb:
            continue
        members_a = {k for k in parent if find(k) == ra}
        members_b = {k for k in parent if find(k) == rb}
        if any((x in members_a and y in members_b) or (x in members_b and y in members_a) for x, y in apart):
            continue
        lo, hi = sorted((ra, rb))
        parent[hi] = lo
    return {k: find(k) for k in parent}
