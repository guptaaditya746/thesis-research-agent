"""The deterministic synthesis rules, shared by the engine (from extracted evidence) and the benchmark
generator (from ground truth), so both sides of the comparison use the very same definitions.

Nothing here knows the question: every parameter (which condition roles are compared, which metrics
count and in which direction, the neutral band, the claim vocabulary, the label table, the flag
thresholds) comes from the protocol's `synthesis` block (docs/evidence-system.md Part C). The functions
are the fixed machinery those parameters drive.

Flags (supervisor's synthesis step, 14 Oct: "an author claim that disagrees with its own experiment's
computed label; duplicated studies; unusually large effects") are rules here too, so the engine's flags
in answer.json and the generator's flags in ground_truth.json come from one definition:

- `claim_disagrees`: the study's author claim does not match its computed direction (`claim_agrees`).
- `duplicate`: a later study reports the same treatment and control values on the same canonical metric
  as an earlier one (`duplicates`); it is reported with its direction but not counted in the answer.
- `large_effect`: |delta| is more than `factor` times the median |delta| of the studies with a
  non-neutral effect, when at least `min_studies` studies have one (`large_effects`); the study still
  counts, the flag is only reported.

Subsets (protocol `synthesis.moderators`, 16 Nov): a study reports one cell per group it measured (a treatment and a
control value with the number of cases behind each). `pooled_delta` adds the counts of several cells into one
difference, `pooled_direction` names it, and `moderated` concludes over all cells: "depends" on the candidate
condition whose two levels have different directions and the widest gap between their pooled differences, else the
one direction of everything pooled.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from statistics import median
from typing import Any, Literal

Direction = Literal["supports", "contradicts", "neutral"]
Label = Literal["supported", "refuted", "mixed", "no_effect", "insufficient"]
Flag = Literal["claim_disagrees", "duplicate", "large_effect"]

DIRECTIONS: tuple[Direction, ...] = ("supports", "contradicts", "neutral")
LABELS: tuple[Label, ...] = ("supported", "refuted", "mixed", "no_effect", "insufficient")
FLAGS: tuple[Flag, ...] = ("claim_disagrees", "duplicate", "large_effect")
COUNTS = ("supporting", "contradicting", "neutral")      # what a label table's conditions may name
GROUP_OF: dict[Direction, str] = {"supports": "supporting", "contradicts": "contradicting", "neutral": "neutral"}
CONDITION = re.compile(r"^\s*(>=|<=|==|>|<)\s*(\d+)\s*$")
# answer.json's keys of a study's treatment and control: the compared thing's item id and the measured value's item
# id. Names of the answer format (graph.py, the web app and the evaluation read them), not evidence type names: they
# stay the same whatever a domain pack calls its types.
SIDE_THING, SIDE_VALUE = "condition", "measurement"
VALUE_DECIMALS = 3               # values are compared for duplication after rounding to this many decimals


def effect(treatment: float, control: float, higher_is_better: bool, min_effect: float) -> tuple[Direction, float]:
    """Direction of one study's effect and its signed improvement (positive = treatment better)."""
    delta = round((treatment - control) if higher_is_better else (control - treatment), 6)
    if abs(delta) < min_effect:
        return "neutral", delta
    return ("supports" if delta > 0 else "contradicts"), delta


def claim_agrees(claim: str, direction: Direction, claim_map: Mapping[str, str]) -> bool:
    """The author claim (in the protocol's claim vocabulary) names the computed direction."""
    return claim_map[claim] == direction


def condition_holds(condition: str, value: int) -> bool:
    m = CONDITION.match(condition)
    if not m:
        raise ValueError(f"a label condition is '<op><int>' with op in > >= < <= ==, not {condition!r}")
    op, n = m.group(1), int(m.group(2))
    return {">": value > n, ">=": value >= n, "<": value < n, "<=": value <= n, "==": value == n}[op]


def label(counts: Mapping[str, int], table: Sequence[Any]) -> Label:
    """The answer from the per-study counts by the protocol's decision table: the first row whose every
    condition holds (a row without conditions always matches). Rows are objects or mappings with `when`
    (count name -> condition) and `then` (a label). Duplicates and undetermined studies are left out of
    the counts before this is called."""
    for row in table:
        when = row.get("when", {}) if isinstance(row, Mapping) else row.when
        then = row["then"] if isinstance(row, Mapping) else row.then
        if all(condition_holds(c, int(counts.get(name, 0))) for name, c in when.items()):
            return then
    raise ValueError("the label table has no row that matches; the last row must have no `when`")


def duplicate_key(canonical: str, treatment: float, control: float) -> tuple[str, float, float]:
    return canonical, round(float(treatment), VALUE_DECIMALS), round(float(control), VALUE_DECIMALS)


def duplicates(studies: Iterable[tuple[str, str, float, float] | tuple[str, str, float, float, str | None]]
               ) -> dict[str, str]:
    """`(id, canonical metric, treatment value, control value[, experiment id])` of the determined studies in
    document order -> {later id: the first id with the same key}. With an experiment id (the paper's experiment
    map, evidence/experiments.py) the key is (experiment id, metric, treatment, control): the same numbers in
    two experiments are two findings. Without one (None, or a 4-tuple: a run with no experiment map) the key is
    today's: the dataset is not part of it (an extractor may miss it); the generator keeps the pairs of distinct
    studies apart, so equal pairs mean one study."""
    first: dict[tuple, str] = {}
    out: dict[str, str] = {}
    for sid, canonical, treatment, control, *rest in studies:
        key: tuple = duplicate_key(canonical, treatment, control)
        if rest and rest[0] is not None:
            key = (rest[0], *key)
        if key in first:
            out[sid] = first[key]
        else:
            first[key] = sid
    return out


def large_effects(deltas: Mapping[str, float | None], factor: float, min_studies: int, min_effect: float) -> list[str]:
    """Ids whose |delta| exceeds `factor` x the median |delta| over the studies with a non-neutral effect
    (|delta| >= min_effect), when at least `min_studies` such studies exist; sorted. Give it the determined
    studies that are not duplicates (None deltas are skipped)."""
    sizes = {k: abs(v) for k, v in deltas.items() if v is not None and abs(v) >= min_effect}
    if len(sizes) < min_studies:
        return []
    cut = factor * median(sizes.values())
    return sorted(k for k, s in sizes.items() if s > cut)


# Subsets. A cell is (treatment value, treatment total, control value, control total), the values oriented so that
# higher is better for the treatment (the caller swaps the sides of a lower-is-better metric); a total is the number
# of cases behind its value, or None when the paper gives none.
PooledCell = tuple[float, int | None, float, int | None]
CONCLUSIONS = ("depends", "supported", "refuted", "no_effect", "insufficient")
CONCLUSION_OF: dict[str, str] = {"supports": "supported", "contradicts": "refuted", "neutral": "no_effect"}


def pooled_delta(cells: Sequence[PooledCell]) -> float:
    """Treatment rate minus control rate over several cells, not rounded. When every cell has both totals the counts
    are added (a value times its total, rounded, is its count), so a large cell weighs more; when any total is
    missing every cell weighs the same (the mean of the values per side)."""
    if all(tn and cn for _, tn, _, cn in cells):
        return (sum(round(t * tn) for t, tn, _, _ in cells) / sum(tn for _, tn, _, _ in cells)       # type: ignore[misc]
                - sum(round(c * cn) for _, _, c, cn in cells) / sum(cn for _, _, _, cn in cells))    # type: ignore[misc]
    return sum(t for t, _, _, _ in cells) / len(cells) - sum(c for _, _, c, _ in cells) / len(cells)


def pooled_direction(delta: float, min_effect: float) -> Direction:
    """The direction of a pooled difference: `effect`'s neutral band, on the difference as it is (not rounded first,
    so sums of counts decide exactly as they are)."""
    if delta >= min_effect:
        return "supports"
    return "contradicts" if delta <= -min_effect else "neutral"


def moderated(cells: Sequence[tuple[Mapping[str, Any], PooledCell]], conditions: Sequence[tuple[str, Sequence[str]]],
              min_effect: float, min_gap: float) -> dict[str, Any]:
    """The answer over every counted cell, each with the level it has on each candidate condition (None: unknown).
    `conditions` are (condition id, its two level ids). A condition is a candidate when both its levels have cells,
    their pooled directions differ and their pooled differences lie at least `min_gap` apart; the candidate with
    the widest gap wins (the first one on a tie) and the verdict is `depends`, with `sides` level -> direction.
    Without a candidate the verdict is the direction of all cells pooled (CONCLUSION_OF), `insufficient` without
    cells. `untested`: `<condition>.<level>` of every level no cell was measured on; `conditions`: the pooled
    table the verdict was read from."""
    table = []
    best: tuple[float, str, dict[str, Any]] | None = None
    for cid, level_ids in conditions:
        per_level = {lv: [cell for at, cell in cells if at.get(cid) == lv] for lv in level_ids}
        deltas = {lv: pooled_delta(group) if group else None for lv, group in per_level.items()}
        words = {lv: pooled_direction(d, min_effect) if d is not None else None for lv, d in deltas.items()}
        gap = None
        if len(level_ids) == 2 and all(d is not None for d in deltas.values()):
            first, second = (deltas[lv] for lv in level_ids)
            gap = abs(first - second)                                                             # type: ignore[operator]
            if len(set(words.values())) > 1 and gap >= min_gap and (best is None or gap > best[0]):
                best = (gap, cid, dict(words))
        table.append({"condition": cid, "gap": None if gap is None else round(gap, 6),
                      "levels": {lv: {"cells": len(per_level[lv]), "direction": words[lv],
                                      "delta": None if deltas[lv] is None else round(deltas[lv], 6)}   # type: ignore[arg-type]
                                 for lv in level_ids}})
    untested = sorted(f"{row['condition']}.{lv}" for row in table for lv, side in row["levels"].items()
                      if not side["cells"])
    overall = pooled_delta([cell for _, cell in cells]) if cells else None
    out: dict[str, Any] = {"verdict": "insufficient", "condition": None, "sides": {}, "untested": untested,
                           "delta": None if overall is None else round(overall, 6), "conditions": table}
    if best is not None:
        out.update(verdict="depends", condition=best[1], sides=best[2])
    elif overall is not None:
        out["verdict"] = CONCLUSION_OF[pooled_direction(overall, min_effect)]
    return out


# Chaining (spec section 6.10, plan 2 Task 9): from A over B and B over C, conclude A over C. The truth network
# (synth/network.py) and the chaining kind judge a path with this one rule, as `effect` is shared for a study.
ChainVerdict = Literal["better", "worse", "no_difference", "refused"]
CHAIN_REASONS = ("direct_comparison", "no_path", "metric_differs", "context_differs", "mixed_directions",
                 "paths_disagree")


def chain_verdict(steps: Sequence[tuple[Direction, str | None]]) -> tuple[ChainVerdict, str | None]:
    """The verdict of one path source -> ... -> target and its refusal reason (None when it concludes). Each step
    is (the direction of the step's earlier thing over its later one by `effect`, the step's context or None).
    Two steps that both name a context must name the same one (`context_differs`); then better at every step
    concludes better, worse at every step worse, and anything else, a neutral step included, `mixed_directions`.
    The steps' metric is the caller's to check (`metric_differs`), as are paths and direct results."""
    if len({context for _, context in steps if context is not None}) > 1:
        return "refused", "context_differs"
    directions = {direction for direction, _ in steps}
    if directions == {"supports"}:
        return "better", None
    if directions == {"contradicts"}:
        return "worse", None
    return "refused", "mixed_directions"


def chain_paths(paths: Sequence[tuple[ChainVerdict, str | None]]) -> tuple[ChainVerdict, str | None, list[int]]:
    """Several paths of 2 or more steps (each its `chain_verdict`) combined into one answer: the paths that conclude
    (reason None) decide, one verdict among them is the answer (reason None: inferred) and different verdicts give
    `refused`, `paths_disagree`; a refused path does not stand against a concluding one. When none concludes, the
    answer is refused with `mixed_directions` when a path has it, else `context_differs`. Also the indices of the
    paths the answer rests on (the concluding ones; else every path). The chaining kind and the truth's expected
    answer (evaluation/expected.py) both combine paths with this; an empty list is the caller's (`no_path`)."""
    if not paths:
        raise ValueError("no path to combine: the caller decides no_path or metric_differs")
    concluding = [n for n, (_, reason) in enumerate(paths) if reason is None]
    if concluding:
        verdicts = {paths[n][0] for n in concluding}
        return (verdicts.pop(), None, concluding) if len(verdicts) == 1 else ("refused", "paths_disagree", concluding)
    reason = "mixed_directions" if any(r == "mixed_directions" for _, r in paths) else "context_differs"
    return "refused", reason, list(range(len(paths)))
