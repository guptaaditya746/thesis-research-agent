"""`evaluate shift`: did each system's answer shift as a counterfactual variant predicts (F3, F4).

The supervisor's controlled variant (STATE.md §1, §6): change one study's result, regenerate that paper,
and the answer should shift predictably. `synth variant` writes the prediction as `variant.json` (F3):
the study, its paper, the direction `from` -> `to`, and `expected: {before: {label, counts}, after:
{label, counts}, label_changes}`. This module (our addition) takes the base corpus's report.json, the
variant corpus's report.json and that file, and per system that both reports score:

- `direction`: the changed paper's given direction before (vs `from`) and after (vs `to`); a paper the
  system did not answer is `undetermined`, as score C counts it;
- `label`: the system's label before and after against `expected.before.label` / `expected.after.label`,
  whether it changed, and whether the prediction says it should (`label_changes`);
- `shifted_as_expected`: all four comparisons hold (direction before and after, label before and after).

The base report's corpus must be `base_corpus_id` and the variant report's `corpus_id`; anything else
is an error, never a silent comparison of the wrong corpora.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .report import table, write_pair

DIRECTION_COLUMNS = ["system", "from", "before", "before_correct", "to", "after", "after_correct"]
LABEL_COLUMNS = ["system", "expected_before", "before", "before_correct", "expected_after", "after", "after_correct",
                 "changed", "shifted_as_expected"]


def _given(system: dict[str, Any], paper: str) -> str:
    return next((s["given"] for s in system.get("studies", []) if s.get("paper") == paper), "undetermined")


def shift(base: dict[str, Any], variant: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """shift.json for two reports and a variant.json (module docstring)."""
    for report, key in ((base, "base_corpus_id"), (variant, "corpus_id")):
        if spec.get(key) and report.get("corpus_id") != spec[key]:
            raise ValueError(f"evaluate shift: the {key.replace('_', ' ')} is {spec[key]}, "
                             f"but the report given for it scores {report.get('corpus_id')}")
    paper = spec.get("paper") or spec["study"]
    expected = spec.get("expected") or {}
    before_label = (expected.get("before") or {}).get("label")
    after_label = (expected.get("after") or {}).get("label")
    label_changes = expected.get("label_changes")
    if label_changes is None and before_label is not None and after_label is not None:
        label_changes = before_label != after_label
    after_systems = {s["system"]: s for s in variant.get("synthesis") or []}
    systems, unmatched = [], []
    for b in base.get("synthesis") or []:
        a = after_systems.get(b["system"])
        if a is None:
            unmatched.append(b["system"])
            continue
        before, after = _given(b, paper), _given(a, paper)
        direction = {"from": spec.get("from"), "to": spec.get("to"), "before": before, "after": after,
                     "before_correct": before == spec.get("from"), "after_correct": after == spec.get("to")}
        label = {"expected_before": before_label, "expected_after": after_label, "before": b.get("label"),
                 "after": a.get("label"), "before_correct": b.get("label") == before_label,
                 "after_correct": a.get("label") == after_label, "changed": b.get("label") != a.get("label"),
                 "expected_change": label_changes}
        systems.append({"system": b["system"], "paper": paper, "direction": direction, "label": label,
                        "shifted_as_expected": all((direction["before_correct"], direction["after_correct"],
                                                    label["before_correct"], label["after_correct"]))})
    unmatched += [name for name in after_systems if name not in {s["system"] for s in systems}]
    return {"base_corpus_id": base.get("corpus_id"), "corpus_id": variant.get("corpus_id"), "study": spec.get("study"),
            "paper": paper, "from": spec.get("from"), "to": spec.get("to"), "changed": spec.get("changed") or [],
            "expected": expected, "label_changes": label_changes, "systems": systems,
            "unmatched_systems": sorted(set(unmatched))}


def render(result: dict[str, Any]) -> str:
    """shift.md: the prediction, then the direction and label tables per system."""
    changed = ", ".join(f"{c.get('measurement')}: {c.get('from')} -> {c.get('to')}" for c in result["changed"]) or "-"
    out = [f"# Shift from {result['base_corpus_id']} to {result['corpus_id']}", "",
           f"Study {result['study']} (paper {result['paper']}): {result['from']} -> {result['to']}; "
           f"changed measurements: {changed}.",
           f"Expected label: {(result['expected'].get('before') or {}).get('label')} -> "
           f"{(result['expected'].get('after') or {}).get('label')} "
           f"({'changes' if result['label_changes'] else 'does not change'}).", "",
           "## The changed study's direction", "",
           table([{"system": s["system"], **s["direction"]} for s in result["systems"]], DIRECTION_COLUMNS), "",
           "## The label", "",
           table([{"system": s["system"], **s["label"], "shifted_as_expected": s["shifted_as_expected"]}
                  for s in result["systems"]], LABEL_COLUMNS), "",
           "shifted_as_expected: the direction before and after and the label before and after are all as "
           "predicted.", ""]
    if result["unmatched_systems"]:
        out += ["Scored in only one of the reports: " + ", ".join(result["unmatched_systems"]), ""]
    return "\n".join(line.rstrip() for line in out)


def write_shift(result: dict[str, Any], out: Path) -> tuple[Path, Path]:
    """shift.json and shift.md in `out`."""
    return write_pair(result, render(result), out, "shift")
