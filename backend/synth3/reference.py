"""The facts a judge checks answers against, worked out from the studies, and the gate that keeps them out of the
noise: a folder is used only when the studies' own numbers lead back to every covered law."""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from synth2.world import direction
from synth3.spec import DomainSpec
from synth3.world import MAX_TRIES, Cell, Study, World, draw_studies, pair_delta


def _evidence(studies: Sequence[Study], arm: str, against: str, measure: str) -> list[Study]:
    """The studies that report both arms on the measure."""
    return [s for s in studies if arm in s.arms and against in s.arms and measure in s.measures]


def _cells(studies: Sequence[Study], measure: str) -> list[Cell]:
    return [c for s in studies for c in s.cells if c.measure == measure]


def _untested(spec: DomainSpec, cells: Sequence[Cell]) -> list[str]:
    """Like synth2: every '<condition id>.<level id>' of every condition that no cell covers."""
    seen = {(cond, level) for c in cells for cond, level in c.levels.items()}
    return sorted(f"{c.id}.{lv.id}" for c in spec.conditions for lv in c.levels if (c.id, lv.id) not in seen)


def pair_answer(spec: DomainSpec, studies: Sequence[Study], arm: str, against: str, measure: str) -> dict:
    """What the numbers say about `arm` against `against` on `measure`, in the shape of synth2's Answer.json()."""
    cells = _cells(_evidence(studies, arm, against, measure), measure)
    if not cells:
        return {"verdict": "insufficient", "condition": None, "sides": {}, "untested": _untested(spec, cells)}
    m = spec.measure(measure)
    best: tuple[float, str, dict[str, str]] | None = None
    for cond in spec.conditions:
        groups = [[c for c in cells if c.levels[cond.id] == lv.id] for lv in cond.levels]
        if not all(groups):
            continue
        deltas = [pair_delta(spec, g, arm, against) for g in groups]
        words = [direction(d, m.min_effect) for d in deltas]
        gap = abs(deltas[0] - deltas[1])
        if words[0] != words[1] and gap >= m.min_gap and (best is None or gap > best[0]):
            best = (gap, cond.id, {lv.id: w for lv, w in zip(cond.levels, words)})
    if best is None:
        verdict = direction(pair_delta(spec, cells, arm, against), m.min_effect)
        return {"verdict": verdict, "condition": None, "sides": {}, "untested": _untested(spec, cells)}
    return {"verdict": "depends", "condition": best[1], "sides": best[2], "untested": _untested(spec, cells)}


def _matches(spec: DomainSpec, world: World, answer: dict, t: str, m: str) -> bool:
    verdict, condition, sides = world.law(t, m).answer(spec.measure(m).min_effect)
    return (answer["verdict"], answer["condition"], answer["sides"]) == (verdict, condition, sides)


def _pair_fact(spec: DomainSpec, world: World, studies: Sequence[Study], t: str, m: str) -> dict:
    control = spec.control.id
    answer = pair_answer(spec, studies, t, control, m)
    used = _evidence(studies, t, control, m)
    key = f"{t}|{control}|{m}"
    claim = {s.id: s.claims[key] for s in used}
    reason = next((c.name for c in spec.conditions if c.id == answer["condition"]), None)
    return {
        "treatment": t, "measure": m, "law": world.law(t, m).json(), "answer": answer,
        "matches_law": _matches(spec, world, answer, t, m), "uncovered": (t, m) in world.uncovered,
        "reason": reason,
        "studies": [s.id for s in used],
        "supporting": [sid for sid, w in claim.items() if w == "helps"],
        "contradicting": [sid for sid, w in claim.items() if w == "hurts"],
        "neutral": [sid for sid, w in claim.items() if w == "no_effect"],
        "overclaimed_in": [s.id for s in used if key in s.overclaims],
    }


def _head_to_head(spec: DomainSpec, studies: Sequence[Study]) -> list[dict]:
    """One entry per (treatment pair, measure) that a study without a control compares directly; the direction
    follows the arm order of the first such study."""
    order: dict[tuple[frozenset[str], str], tuple[str, str]] = {}
    for s in studies:
        if spec.control.id in s.arms:
            continue
        for m in s.measures:
            order.setdefault((frozenset(s.arms[:2]), m), (s.arms[0], s.arms[1]))
    return [{"arm": arm, "against": against, "measure": m,
             "answer": pair_answer(spec, studies, arm, against, m),
             "studies": [s.id for s in _evidence(studies, arm, against, m)]}
            for (_, m), (arm, against) in order.items()]


def _ranking(spec: DomainSpec, studies: Sequence[Study]) -> dict[str, list[dict]]:
    control = spec.control.id
    ranking = {}
    for m in spec.measures:
        rows = []
        for t in spec.treatments:
            cells = _cells(_evidence(studies, t.id, control, m.id), m.id)
            if cells:
                rows.append({"treatment": t.id, "delta": pair_delta(spec, cells, t.id, control)})
        ranking[m.id] = sorted(rows, key=lambda r: -r["delta"])   # stable: a tie keeps the spec order
    return ranking


def reference_facts(spec: DomainSpec, world: World, studies: Sequence[Study]) -> dict:
    """Plain JSON: the per-pair answers with their evidence, the head-to-head answers, the ranking per measure and
    what each study reports."""
    return {
        "pairs": [_pair_fact(spec, world, studies, t, m) for t, m in spec.pairs],
        "head_to_head": _head_to_head(spec, studies),
        "ranking": _ranking(spec, studies),
        "inventory": [{"study": s.id, "label": s.label, "setting": s.setting, "arms": list(s.arms),
                       "measures": list(s.measures)} for s in studies],
    }


def draw_supported_studies(spec: DomainSpec, world: World, seed: int, count: int) -> tuple[tuple[Study, ...], int]:
    """The first noise attempt whose numbers lead back to every covered law, and that attempt."""
    control = spec.control.id
    covered = [p for p in spec.pairs if p not in world.uncovered]
    failed: Counter[tuple[str, str]] = Counter()
    for attempt in range(MAX_TRIES):
        studies = draw_studies(spec, world, seed, count, attempt)
        wrong = [(t, m) for t, m in covered
                 if not _matches(spec, world, pair_answer(spec, studies, t, control, m), t, m)]
        if not wrong:
            return studies, attempt
        failed.update(wrong)
    never = [f"{t}|{m}" for t, m in covered if failed[(t, m)] == MAX_TRIES]
    if never:
        raise ValueError(f"seed {seed}: in {MAX_TRIES} noise draws these pairs never matched their law: "
                         f"{', '.join(never)}; use larger studies or larger effects")
    worst = [f"{t}|{m} ({failed[(t, m)]} misses)" for t, m in covered if failed[(t, m)]]
    raise ValueError(f"seed {seed}: in {MAX_TRIES} noise draws the pairs never matched their laws all at once; "
                     f"misses: {', '.join(worst)}; use larger studies or larger effects")
