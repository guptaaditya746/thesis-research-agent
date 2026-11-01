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


def duplicates(studies: Iterable[tuple[str, str, float, float]]) -> dict[str, str]:
    """`(id, canonical metric, treatment value, control value)` of the determined studies in document
    order -> {later id: the first id with the same key}. The dataset is not part of the key (an extractor
    may miss it); the generator keeps the pairs of distinct studies apart, so equal pairs mean one study."""
    first: dict[tuple[str, float, float], str] = {}
    out: dict[str, str] = {}
    for sid, canonical, treatment, control in studies:
        key = duplicate_key(canonical, treatment, control)
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
