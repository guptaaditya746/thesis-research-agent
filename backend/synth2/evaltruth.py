"""A synth2 truth in the evaluation's study format, so A (extraction), B (integration) and C (synthesis) can score it.

A synth2 study has one or more cells; each cell is one pair of counts per arm. The translation gives a study two
conditions (the treatment and the control), one metric and one measurement per cell and arm. A study with one cell
also gets an `effect` and, when its author claim says another direction, the flag `claim_disagrees` (as old synth
truth flags it); a study with two cells has no single result, so B and C cannot score it yet and its id goes into
`unscored`. While any study is unscored the corpus-level answer has no `label` and no groups (the engine's answer
covers every study, the truth could only cover the one-cell ones), so C leaves the label and the counts unscored;
`duplicates` is always there. Template text gets a placement for every mention of the treatment label, the control
label and the metric name, so an item quoting any of them (the results table, say) has a right span.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from synth2.recipe import Recipe, load_recipe
from synth2.world import direction

CLAIM = {"helps": "improves", "hurts": "worsens", "no_effect": "no_effect"}
EFFECT = {"helps": "supports", "hurts": "contradicts", "no_effect": "neutral"}
GROUPS = (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral"))


def is_synth2(data: dict) -> bool:
    return "law" in data and "key" in data


def _label(directions: list[str]) -> str:
    """The verdict from the studies' directions (the rag-factuality table, in its order)."""
    if "supports" in directions and "contradicts" in directions:
        return "mixed"
    for want, label in (("supports", "supported"), ("contradicts", "refuted"), ("neutral", "no_effect")):
        if want in directions:
            return label
    return "insufficient"


def _every(text: str, needle: str, paper: str) -> list[tuple[int, int]]:
    """Every mention of `needle` in the text, in order."""
    found = [(m.start(), m.end()) for m in re.finditer(re.escape(needle), text)]
    if not found:
        raise ValueError(f"{paper}: '{needle}' is not in the paper text, so it cannot be placed")
    return found


def _study(s: dict, recipe: Recipe, level: str) -> dict:
    sid, c1, c2, k1 = s["id"], f"{s['id']}.c1", f"{s['id']}.c2", f"{s['id']}.k1"
    measurements = []
    for j, cell in enumerate(s["cells"]):
        for arm, cond in (("t", c1), ("c", c2)):
            measurements.append({"id": f"{sid}.m{j}{arm}", "condition": cond, "metric": k1,
                                 "value": cell[f"k_{arm}"] / cell[f"n_{arm}"], "dataset": s["dataset"]})
    study = {
        "study_id": sid, "paper": sid, "level": level, "duplicate_of": s.get("duplicate_of"),
        "conditions": [{"id": c1, "role": "rag", "label": recipe.treatment.label, "aliases": []},
                       {"id": c2, "role": "baseline", "label": recipe.control.label, "aliases": []}],
        "metrics": [{"id": k1, "canonical": "factual_accuracy", "name": recipe.metric, "higher_is_better": True}],
        "measurements": measurements,
        "author_claim": {"id": f"{sid}.a1", "direction": CLAIM[s["claim"]]},
    }
    if len(s["cells"]) == 1:
        cell = s["cells"][0]
        delta = cell["k_t"] / cell["n_t"] - cell["k_c"] / cell["n_c"]
        study["effect"] = {"direction": EFFECT[direction(delta, recipe.min_effect)], "delta": delta, "metric": k1,
                           "treatment": f"{sid}.m0t", "control": f"{sid}.m0c"}
        study["flags"] = ["claim_disagrees"] if EFFECT[s["claim"]] != study["effect"]["direction"] else []
    else:
        study["flags"] = []
    return study


def eval_truth(data: dict, corpus_dir: Path) -> dict:
    corpus_dir = Path(corpus_dir)
    meta = corpus_dir / "corpus.json"
    if not meta.is_file():
        raise ValueError(f"{corpus_dir}: a synth2 ground_truth.json needs the corpus.json next to it (its settings)")
    settings = json.loads(meta.read_text(encoding="utf-8"))["settings"]
    recipe = load_recipe(settings["domain"])
    level = data.get("eval_level") or settings["text_level"]
    studies = [_study(s, recipe, level) for s in data["studies"]]
    unscored = [s["id"] for s in data["studies"] if len(s["cells"]) != 1]
    texts: dict[str, str] = {}

    def text(paper: str) -> str:
        if paper not in texts:
            texts[paper] = (corpus_dir / "papers" / f"{paper}.md").read_text(encoding="utf-8")
        return texts[paper]

    placements = []

    def place(paper: str, fact: str, role: str, start: int, end: int) -> None:
        placements.append({"fact": fact, "role": role, "paper": paper, "start": start, "end": end,
                           "exact": text(paper)[start:end]})

    for p in data["placements"]:
        paper, parts = p["paper"], p["fact"].split(".")   # S001.c0.k_t | S001.claim.abstract
        if parts[1] == "claim":
            place(paper, f"{paper}.a1", "claim", p["start"], p["end"])
        else:
            field = parts[2]
            role = "value" if field.startswith("k_") else "value_total"
            place(paper, f"{paper}.m{int(parts[1][1:])}{field[-1]}", role, p["start"], p["end"])
    if data["placements"]:   # template text: the labels and the metric name are in the text too
        for s in studies:
            paper = s["paper"]
            for fact, role, needle in ((s["conditions"][0]["id"], "condition_label", recipe.treatment.label),
                                       (s["conditions"][1]["id"], "condition_label", recipe.control.label),
                                       (s["metrics"][0]["id"], "metric_label", recipe.metric)):
                for start, end in _every(text(paper), needle, paper):
                    place(paper, fact, role, start, end)
    answer: dict = {"duplicates": [s["paper"] for s in studies if s["duplicate_of"]]}
    if not unscored:   # every study has one result: the corpus-level verdict is known
        one = [s for s in studies if not s["duplicate_of"]]   # a copy is set aside, not counted
        answer = {"label": _label([s["effect"]["direction"] for s in one]),
                  **{name: [s["paper"] for s in one if s["effect"]["direction"] == d] for name, d in GROUPS},
                  **answer}
    return {"corpus_id": data["corpus_id"], "question": data.get("question", ""), "seed": settings["seed"],
            "studies": studies, "placements": placements, "answer": answer, "unscored": unscored}
