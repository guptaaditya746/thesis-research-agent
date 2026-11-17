"""The facts a question needs, found by code.

The planted names in the main question (arm labels, measure names, condition and level names, setting names) pick
the in-scope facts from a folder's `ground_truth.json`; each fact is one plain line with a stable id:
`pair:<t>:<m>`, `h2h:<a>:<b>:<m>`, `rank:<m>`, `study:<sid>`. Code alone decides "can't tell".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from jsonio import canonical_bytes, sha256_hex
from synth2.recipe import Strict
from synth3.questions import Question
from synth3.spec import DomainSpec

_WORDS = {"helps": "better", "hurts": "worse", "no_effect": "no real difference"}


@dataclass(frozen=True)
class Folder:
    path: Path
    seed: int
    corpus_id: str
    spec: DomainSpec
    truth: dict


def load_folder(path: Path) -> Folder:
    truth_path, corpus_path = path / "ground_truth.json", path / "corpus.json"
    for p in (truth_path, corpus_path):
        if not p.is_file():
            raise ValueError(f"{p}: missing; is this a built synth3 folder?")
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    return Folder(path=path, seed=corpus["settings"]["seed"], corpus_id=corpus["corpus_id"],
                  spec=DomainSpec(**truth["spec"]), truth=truth)


def check_spec(folder: Folder, spec: DomainSpec) -> None:
    if folder.spec.sha256 != spec.sha256:
        raise ValueError("the folder was built from another spec")


def truth_sha256(truth: dict) -> str:
    return sha256_hex(canonical_bytes({k: truth[k] for k in ("world", "studies", "facts")}))


class Named(Strict):
    arms: list[str]
    measures: list[str]
    conditions: list[str]
    settings: list[str]


def _has(text: str, name: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(name)}(?:e?s)?(?!\w)", text, re.I) is not None


def named(spec: DomainSpec, text: str) -> Named:
    return Named(
        arms=[a.id for a in spec.arms if _has(text, a.label)],
        measures=[m.id for m in spec.measures if _has(text, m.name)],
        conditions=[c.id for c in spec.conditions
                    if _has(text, c.name) or any(_has(text, lv.name) for lv in c.levels)],
        settings=[s.name for s in spec.settings if _has(text, s.name)])


def scope(spec: DomainSpec, q: Question) -> Named:
    """`about` names when set, else the main question only; sub-questions never set the scope (not scored)."""
    return named(spec, "\n".join(q.about) if q.about else q.question)


class FactLine(Strict):
    id: str
    text: str


def _label(spec: DomainSpec, arm: str) -> str:
    return next(a.label for a in spec.arms if a.id == arm)


def _measure(spec: DomainSpec, m: str) -> str:
    me = spec.measure(m)
    return f"{me.name} ({'higher' if me.higher_is_better else 'lower'} is better)"


def _verdict(spec: DomainSpec, answer: dict, a: str, b: str, m: str) -> str:
    v = answer["verdict"]
    if v == "helps":
        return f"{a} does better than {b}"
    if v == "hurts":
        return f"{a} does worse than {b}"
    if v == "no_effect":
        return f"{a} and {b} show no real difference"
    if v == "depends":
        cond = next(c for c in spec.conditions if c.id == answer["condition"])
        sides = ", ".join(f"{lv.name}: {_WORDS[answer['sides'][lv.id]]}" for lv in cond.levels)
        return f"it depends on {cond.name}: {sides}"
    return f"no study in this folder compares {a} with {b} on {spec.measure(m).name}"


def _level_name(spec: DomainSpec, ref: str) -> str:
    cid, lid = ref.split(".", 1)
    return next(lv.name for c in spec.conditions if c.id == cid for lv in c.levels if lv.id == lid)


def _pair_line(spec: DomainSpec, p: dict) -> FactLine:
    t, m = p["treatment"], p["measure"]
    a, b = _label(spec, t), spec.control.label
    text = f"{a} against {b} on {_measure(spec, m)}: {_verdict(spec, p['answer'], a, b, m)}."
    if p["studies"]:
        text += (f" Studies: {', '.join(p['studies'])}. The authors say better in {len(p['supporting'])}, "
                 f"worse in {len(p['contradicting'])}, no real difference in {len(p['neutral'])}.")
    if p["overclaimed_in"]:
        text += f" The authors claim more than their numbers show in {', '.join(p['overclaimed_in'])}."
    if p["answer"]["untested"]:
        text += f" Not tested for: {', '.join(_level_name(spec, u) for u in p['answer']['untested'])}."
    return FactLine(id=f"pair:{t}:{m}", text=text)


def _h2h_line(spec: DomainSpec, h: dict) -> FactLine:
    a, b, m = _label(spec, h["arm"]), _label(spec, h["against"]), h["measure"]
    text = f"{a} against {b} on {_measure(spec, m)}, compared directly: {_verdict(spec, h['answer'], a, b, m)}."
    if h["studies"]:
        text += f" Studies: {', '.join(h['studies'])}."
    return FactLine(id=f"h2h:{h['arm']}:{h['against']}:{m}", text=text)


def _rank_line(spec: DomainSpec, truth: dict, m: str, T: list[str]) -> FactLine:
    rows = [r["treatment"] for r in truth["facts"]["ranking"][m] if r["treatment"] in T]
    best = ", ".join(_label(spec, t) for t in rows)
    text = f"{_measure(spec, m)}, against {spec.control.label}, best first: {best}."
    none = [t for t in T if t not in rows]
    if none:
        text += f" No studies: {', '.join(_label(spec, t) for t in none)}."
    return FactLine(id=f"rank:{m}", text=text)


def _study_line(spec: DomainSpec, s: dict) -> FactLine:
    arms = ", ".join(_label(spec, a) for a in s["arms"])
    measures = ", ".join(spec.measure(m).name for m in s["measures"])
    return FactLine(id=f"study:{s['study']}",
                    text=f"{s['study']} {s['label']}, {s['setting']}: compares {arms} on {measures}.")


def _in_scope(spec: DomainSpec, truth: dict, q: Question):
    """(named, T, M, in-scope pair facts, in-scope head-to-head facts)."""
    n = scope(spec, q)
    named_t = [t.id for t in spec.treatments if t.id in n.arms]
    T = named_t or [t.id for t in spec.treatments]
    M = n.measures or [m.id for m in spec.measures]

    def h2h_ok(h: dict) -> bool:
        if h["measure"] not in M:
            return False
        if len(named_t) >= 2:
            return h["arm"] in T and h["against"] in T
        if len(named_t) == 1:
            return h["arm"] in T or h["against"] in T
        return True

    pairs = {(p["treatment"], p["measure"]): p for p in truth["facts"]["pairs"]}
    return (n, T, M, [pairs[(t, m)] for t in T for m in M],
            [h for h in truth["facts"]["head_to_head"] if h2h_ok(h)])


def relevant_facts(spec: DomainSpec, truth: dict, q: Question) -> list[FactLine]:
    n, T, M, pairs, h2h = _in_scope(spec, truth, q)
    lines = [_pair_line(spec, p) for p in pairs]
    lines += [_h2h_line(spec, h) for h in h2h]
    if len(T) >= 2:
        lines += [_rank_line(spec, truth, m, T) for m in M]
    if n.settings or (not n.arms and not n.measures):
        lines += [_study_line(spec, s) for s in truth["facts"]["inventory"]]
    return lines


def cant_tell(spec: DomainSpec, truth: dict, q: Question) -> list[str] | None:
    _, _, _, pairs, h2h = _in_scope(spec, truth, q)
    if all(p["answer"]["verdict"] == "insufficient" for p in pairs) and not any(h["studies"] for h in h2h):
        return [f"pair:{p['treatment']}:{p['measure']}" for p in pairs]
    return None
