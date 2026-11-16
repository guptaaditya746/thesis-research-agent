"""A synth2 truth in the evaluation's study format, so A (extraction), B (integration) and C (synthesis) can score it.

A synth2 study has one or more cells; each cell is one pair of counts per arm, measured on one subset (a level of
each of the recipe's three conditions). The translation gives a study two conditions (the treatment and the
control), one metric and one measurement per cell and arm; a measurement carries its cell's `subset` (condition id
-> level id) and `total` (the n of its count). Every study gets `cells`, one effect per cell ({id, subset,
direction, delta, treatment, control}: B's unit, a per-subset result), and an `effect`: the study's own result, its
cells' counts added up (`world.study_delta`, what its honest claim says), with the first cell's measurements as its
pair. Flags: `claim_disagrees` when the author claim says another direction than that result (as old synth truth
flags it) and `large_effect` by the engine's own rule (`rules.large_effects`, the protocol's default thresholds)
over the studies that are no copy. The corpus-level `answer` is the synth2 `key` (what C scores the system's answer
against), the studies grouped by their own direction (copies set aside) and `duplicates`. Template text gets a placement for every mention of the treatment label, the control
label and the metric name, so an item quoting any of them (the results table, say) has a right span; a built paper
(fullrun) names its systems its own way and brings `<id>.label.<treatment|control|metric>` placements instead. Each of the
truth's `known_extras` (a real result left in a paper built from a real one) becomes an `excused` span at every place
its text is in its paper, so A does not count an item on it as wrong; a text missing from its paper is refused.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from evidence import rules
from evidence.protocol import LargeEffect
from synth2.recipe import Recipe, load_recipe
from synth2.world import direction

CLAIM = {"helps": "improves", "hurts": "worsens", "no_effect": "no_effect"}
EFFECT = {"helps": "supports", "hurts": "contradicts", "no_effect": "neutral"}
GROUPS = (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral"))


def is_synth2(data: dict) -> bool:
    return "law" in data and "key" in data


def _every(text: str, needle: str, paper: str) -> list[tuple[int, int]]:
    """Every mention of `needle` in the text, in order."""
    found = [(m.start(), m.end()) for m in re.finditer(re.escape(needle), text)]
    if not found:
        raise ValueError(f"{paper}: '{needle}' is not in the paper text, so it cannot be placed")
    return found


def _study(s: dict, recipe: Recipe, level: str) -> dict:
    sid, c1, c2, k1 = s["id"], f"{s['id']}.c1", f"{s['id']}.c2", f"{s['id']}.k1"
    measurements, cells = [], []
    for j, cell in enumerate(s["cells"]):
        for arm, cond in (("t", c1), ("c", c2)):
            measurements.append({"id": f"{sid}.m{j}{arm}", "condition": cond, "metric": k1,
                                 "value": cell[f"k_{arm}"] / cell[f"n_{arm}"], "dataset": s["dataset"],
                                 "total": cell[f"n_{arm}"], "subset": dict(cell["levels"])})
        delta = cell["k_t"] / cell["n_t"] - cell["k_c"] / cell["n_c"]
        cells.append({"id": f"{sid}.e{j}", "subset": dict(cell["levels"]),
                      "direction": EFFECT[direction(delta, recipe.min_effect)], "delta": delta,
                      "treatment": f"{sid}.m{j}t", "control": f"{sid}.m{j}c"})
    # the study's own result: its cells' counts added up (world.study_delta)
    delta = (sum(c["k_t"] for c in s["cells"]) / sum(c["n_t"] for c in s["cells"])
             - sum(c["k_c"] for c in s["cells"]) / sum(c["n_c"] for c in s["cells"]))
    said = EFFECT[direction(delta, recipe.min_effect)]
    return {
        "study_id": sid, "paper": sid, "level": level, "duplicate_of": s.get("duplicate_of"),
        "conditions": [{"id": c1, "role": "rag", "label": recipe.treatment.label, "aliases": []},
                       {"id": c2, "role": "baseline", "label": recipe.control.label, "aliases": []}],
        "metrics": [{"id": k1, "canonical": "factual_accuracy", "name": recipe.metric, "higher_is_better": True}],
        "measurements": measurements,
        "author_claim": {"id": f"{sid}.a1", "direction": CLAIM[s["claim"]]},
        "cells": cells,
        "effect": {"direction": said, "delta": delta, "metric": k1, "treatment": f"{sid}.m0t",
                   "control": f"{sid}.m0c"},
        "flags": ["claim_disagrees"] if EFFECT[s["claim"]] != said else [],
    }


def eval_truth(data: dict, corpus_dir: Path) -> dict:
    corpus_dir = Path(corpus_dir)
    meta = corpus_dir / "corpus.json"
    if not meta.is_file():
        raise ValueError(f"{corpus_dir}: a synth2 ground_truth.json needs the corpus.json next to it (its settings)")
    settings = json.loads(meta.read_text(encoding="utf-8"))["settings"]
    recipe = load_recipe(settings["domain"])
    level = data.get("eval_level") or settings["text_level"]
    studies = [_study(s, recipe, level) for s in data["studies"]]
    one = [s for s in studies if not s["duplicate_of"]]   # a copy is set aside, not counted
    default = LargeEffect()
    # as the engine reads it: deltas rounded to 6 places, a neutral study left out of the median
    large = rules.large_effects({s["paper"]: None if s["effect"]["direction"] == "neutral"
                                 else round(s["effect"]["delta"], 6) for s in one},
                                default.factor, default.min_studies, recipe.min_effect)
    for s in studies:
        if s["paper"] in large:
            s["flags"] = sorted([*s["flags"], "large_effect"])
    texts: dict[str, str] = {}

    def text(paper: str) -> str:
        if paper not in texts:
            texts[paper] = (corpus_dir / "papers" / f"{paper}.md").read_text(encoding="utf-8")
        return texts[paper]

    placements = []

    def place(paper: str, fact: str, role: str, start: int, end: int) -> None:
        placements.append({"fact": fact, "role": role, "paper": paper, "start": start, "end": end,
                           "exact": text(paper)[start:end]})

    label_fact = {"treatment": ("c1", "condition_label"), "control": ("c2", "condition_label"),
                  "metric": ("k1", "metric_label")}
    for p in data["placements"]:
        paper, parts = p["paper"], p["fact"].split(".")   # S001.c0.k_t | S001.claim.abstract | S001.label.control
        if parts[1] == "claim":
            place(paper, f"{paper}.a1", "claim", p["start"], p["end"])
        elif parts[1] == "label":   # a built paper names the systems its own way (fullrun.placements)
            fact, role = label_fact[parts[2]]
            place(paper, f"{paper}.{fact}", role, p["start"], p["end"])
        else:
            field = parts[2]
            role = "value" if field.startswith("k_") else "value_total"
            place(paper, f"{paper}.m{int(parts[1][1:])}{field[-1]}", role, p["start"], p["end"])
    if data["placements"] and not any(".label." in p["fact"] for p in data["placements"]):
        # template text: the labels and the metric name are in the text too
        for s in studies:
            paper = s["paper"]
            for fact, role, needle in ((s["conditions"][0]["id"], "condition_label", recipe.treatment.label),
                                       (s["conditions"][1]["id"], "condition_label", recipe.control.label),
                                       (s["metrics"][0]["id"], "metric_label", recipe.metric)):
                for start, end in _every(text(paper), needle, paper):
                    place(paper, fact, role, start, end)
    excused = [{"paper": e["study"], "id": e["id"], "start": start, "end": end}
               for e in data.get("known_extras") or [] for start, end in _every(text(e["study"]), e["text"], e["study"])]
    answer = {"key": data["key"],
              **{name: [s["paper"] for s in one if s["effect"]["direction"] == d] for name, d in GROUPS},
              "duplicates": [s["paper"] for s in studies if s["duplicate_of"]]}
    return {"corpus_id": data["corpus_id"], "question": data.get("question", ""), "seed": settings["seed"],
            "studies": studies, "placements": placements, "answer": answer, "excused": excused}
