"""Score a system's fixed-form answers for one corpus family, by code, and average the scores over families.

Three headline scores: `recovers_law` (the answer equals the key), `follows_evidence` (the answer moves, and
moves correctly, when the twin's evidence changes), `resists_overclaiming` (the answer stays when only the
authors' claims change). Two side scores: `stays_steady` (the answer stays for the other harmless relatives)
and `fell_for_lumping` (the answer is the one you get by ignoring the conditions).
"""
from __future__ import annotations

import json
import statistics
from math import sqrt
from pathlib import Path
from typing import Any, Sequence

from synth2.conclude import Answer, lumped, pooled, vote
from synth2.corpus import load_studies, load_truth
from synth2.family import KINDS, RELATION
from synth2.recipe import load_recipe

RULES = {"pooled": pooled, "vote": vote, "lumped": lumped}
SCORES = ("recovers_law", "follows_evidence", "resists_overclaiming", "stays_steady", "fell_for_lumping")
MEMBERS = ("base", *KINDS)


def reference_answers(family_root: Path, rule: str) -> dict[str, dict]:
    """Corpus id -> the answer the named rule gives, for the base and its four relatives."""
    if rule not in RULES:
        raise ValueError(f"unknown rule '{rule}'; known: {', '.join(RULES)}")
    answers = {}
    for member in MEMBERS:
        folder = family_root / member
        domain = json.loads((folder / "corpus.json").read_text(encoding="utf-8"))["settings"]["domain"]
        truth = load_truth(folder)
        answers[truth["corpus_id"]] = RULES[rule](load_studies(folder), load_recipe(domain)).json()
    return answers


def score_family(family_root: Path, answers: dict[str, Any]) -> dict:
    truths = {member: load_truth(family_root / member) for member in MEMBERS}
    given: dict[str, Answer | None] = {}
    invalid = []
    for member, truth in truths.items():
        try:
            given[member] = Answer.parse(answers[truth["corpus_id"]])
        except (KeyError, ValueError):
            given[member] = None
            invalid.append(truth["corpus_id"])
    keys = {member: Answer.parse(truth["key"]) for member, truth in truths.items()}
    by_kind = {}
    for kind in KINDS:
        if given[kind] is None or given["base"] is None:
            by_kind[kind] = False
        elif RELATION[kind] == "must_change":
            by_kind[kind] = given[kind] != given["base"] and given[kind] == keys[kind]
        else:
            by_kind[kind] = given[kind] == given["base"]

    def count(kinds: Sequence[str]) -> dict:
        return {"hits": sum(by_kind[k] for k in kinds), "of": len(kinds)}

    # a spun copy in which no author overclaims is the base again: there is nothing to resist, so it is not counted
    spun = ["spun"] if any(s.overclaims for s in load_studies(family_root / "spun")) else []
    dependent = [m for m in MEMBERS if keys[m].verdict == "depends"]
    return {
        "recovers_law": {"hits": sum(given[m] == keys[m] for m in MEMBERS), "of": len(MEMBERS)},
        "follows_evidence": count([k for k in KINDS if RELATION[k] == "must_change"]),
        "resists_overclaiming": count(spun),
        "stays_steady": count([k for k in KINDS if RELATION[k] == "must_stay" and k != "spun"]),
        "fell_for_lumping": {"hits": sum(given[m] == Answer.parse(truths[m]["lumped"]) for m in dependent),
                             "of": len(dependent)},
        "by_kind": by_kind,
        "invalid": invalid,
    }


def summarise(reports: Sequence[dict]) -> dict:
    """Mean and standard error of each score over the per-family fractions; families with nothing to count
    for a score are left out of that score."""
    out = {}
    for score in SCORES:
        fractions = [r[score]["hits"] / r[score]["of"] for r in reports if r[score]["of"]]
        n = len(fractions)
        out[score] = {"mean": statistics.fmean(fractions) if n else 0.0,
                      "stderr": statistics.stdev(fractions) / sqrt(n) if n >= 2 else 0.0, "n": n}
    return out
