"""A hand-written two-paper corpus in the documented formats (docs/evidence-system.md A1-A4).

S001 (explicit): accuracy, closed-book 0.62 vs retrieval-augmented 0.70, plus a distractor system
(0.66) and a distractor metric (latency): supports, delta 0.08. The baseline value is stated twice
(abstract "62%" and table "0.62"), so it has two placements.
S002 (paraphrased): hallucination rate, 0.20 without retrieval vs 0.25 with it: contradicts.
The answer is `mixed`. Placements are found in the text, so offsets are right by construction.

`perfect_run` writes the run directory a perfect engine would: one item per fact with spans at the
fact's placements, measurements linked to their condition and metric items, the true answer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent.anchor import selector_at
from evidence.contract import Item, Span

QUESTION = "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"
REGEX, LLM = "regex_result@1#aaaaaaaaaaaa", "llm_result@1#bbbbbbbbbbbb"

S001 = """# Retrieval helps factual question answering

## Abstract

We compare a closed-book model (B) with its retrieval-augmented variant (R). R reaches 70% answer accuracy, against 62% for B.

## Results

| System | Answer accuracy | Latency (ms) |
|---|---|---|
| B | 0.62 | 120 |
| R | 0.70 | 180 |
| R-noRerank | 0.66 | 150 |

Retrieval clearly improves the accuracy of the answers.
"""

S002 = """# Do retrieved passages reduce hallucination?

## Setup

Our plain generator answers without any documents; the augmented pipeline first fetches five passages.

## Findings

Without documents the generator hallucinated in 20% of answers; with fetched passages this rose to 25%.
We find no reliable benefit from retrieval.
"""

PAPERS = {"S001": S001, "S002": S002}

# fact id -> (paper, role, exact text, occurrence) for each rendering of the fact
RENDERINGS: list[tuple[str, str, str, str]] = [
    ("S001.c1", "S001", "condition_label", "closed-book model (B)"),
    ("S001.c2", "S001", "condition_label", "retrieval-augmented variant (R)"),
    ("S001.c3", "S001", "condition_label", "R-noRerank"),
    ("S001.k1", "S001", "metric_label", "Answer accuracy"),
    ("S001.k2", "S001", "metric_label", "Latency (ms)"),
    ("S001.m1", "S001", "value", "62%"),
    ("S001.m1", "S001", "value", "0.62"),
    ("S001.m2", "S001", "value", "0.70"),
    ("S001.m3", "S001", "value", "0.66"),
    ("S001.a1", "S001", "claim", "Retrieval clearly improves the accuracy of the answers."),
    ("S002.c1", "S002", "condition_label", "plain generator"),
    ("S002.c2", "S002", "condition_label", "augmented pipeline"),
    ("S002.k1", "S002", "metric_label", "hallucinated"),
    ("S002.m1", "S002", "value", "20%"),
    ("S002.m2", "S002", "value", "25%"),
    ("S002.a1", "S002", "claim", "We find no reliable benefit from retrieval."),
]


def studies() -> list[dict[str, Any]]:
    return [
        {"study_id": "S001", "paper": "S001", "level": "explicit",
         "conditions": [{"id": "S001.c1", "role": "baseline", "label": "closed-book model", "aliases": ["B"]},
                        {"id": "S001.c2", "role": "rag", "label": "retrieval-augmented variant", "aliases": ["R"]},
                        {"id": "S001.c3", "role": "other", "label": "R-noRerank", "aliases": []}],
         "metrics": [{"id": "S001.k1", "canonical": "factual_accuracy", "name": "answer accuracy",
                      "higher_is_better": True},
                     {"id": "S001.k2", "canonical": "other", "name": "latency", "higher_is_better": False}],
         "measurements": [{"id": "S001.m1", "condition": "S001.c1", "metric": "S001.k1", "value": 0.62, "dataset": "NQ"},
                          {"id": "S001.m2", "condition": "S001.c2", "metric": "S001.k1", "value": 0.70, "dataset": "NQ"},
                          {"id": "S001.m3", "condition": "S001.c3", "metric": "S001.k1", "value": 0.66, "dataset": "NQ"}],
         "author_claim": {"id": "S001.a1", "direction": "improves"},
         "effect": {"direction": "supports", "delta": 0.08, "metric": "S001.k1", "treatment": "S001.m2",
                    "control": "S001.m1"}},
        {"study_id": "S002", "paper": "S002", "level": "paraphrased",
         "conditions": [{"id": "S002.c1", "role": "baseline", "label": "plain generator", "aliases": []},
                        {"id": "S002.c2", "role": "rag", "label": "augmented pipeline", "aliases": []}],
         "metrics": [{"id": "S002.k1", "canonical": "hallucination_rate", "name": "hallucination rate",
                      "higher_is_better": False}],
         "measurements": [{"id": "S002.m1", "condition": "S002.c1", "metric": "S002.k1", "value": 0.20, "dataset": "x"},
                          {"id": "S002.m2", "condition": "S002.c2", "metric": "S002.k1", "value": 0.25, "dataset": "x"}],
         "author_claim": {"id": "S002.a1", "direction": "no_effect"},
         "effect": {"direction": "contradicts", "delta": -0.05, "metric": "S002.k1", "treatment": "S002.m2",
                    "control": "S002.m1"}},
    ]


def placements() -> list[dict[str, Any]]:
    out = []
    for fact, paper, role, exact in RENDERINGS:
        text = PAPERS[paper]
        start = text.index(exact)
        assert text.count(exact) == 1, exact
        out.append({"fact": fact, "role": role, "paper": paper, "start": start, "end": start + len(exact),
                    "exact": exact})
    return out


def ground_truth(corpus_id: str = "test-mixed") -> dict[str, Any]:
    return {"corpus_id": corpus_id, "seed": 1, "question": QUESTION, "studies": studies(),
            "placements": placements(),
            "answer": {"label": "mixed", "supporting": ["S001"], "contradicting": ["S002"], "neutral": []}}


def write_corpus(root: Path, corpus_id: str = "test-mixed", poison: bool = True) -> Path:
    """manifest.json, papers/, ground_truth.json, and (poison) corpus.json, fidelity.json and decoys.json."""
    corpus = Path(root) / corpus_id
    (corpus / "papers").mkdir(parents=True)
    entries = []
    for pid, text in PAPERS.items():
        data = text.encode("utf-8")
        (corpus / "papers" / f"{pid}.md").write_bytes(data)
        entries.append({"id": pid, "file": f"papers/{pid}.md", "sha256": hashlib.sha256(data).hexdigest()})
    dump(corpus / "manifest.json", {"corpus_id": corpus_id, "papers": entries})
    dump(corpus / "ground_truth.json", ground_truth(corpus_id))
    if poison:
        dump(corpus / "corpus.json", {"corpus_id": corpus_id, "question": QUESTION, "level": "mixed"})
        dump(corpus / "fidelity.json", {"papers": []})
        dump(corpus / "decoys.json", [])
    return corpus


def dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8", newline="\n")


# --- a perfect run ----------------------------------------------------------------------------------

def span(paper: str, role: str, exact: str) -> Span:
    text = PAPERS[paper]
    start = text.index(exact)
    return Span.of(role, selector_at(text, start, start + len(exact), file=f"papers/{paper}.md"))


def fact_spans(fact: str) -> list[Span]:
    return [span(paper, role, exact) for f, paper, role, exact in RENDERINGS if f == fact]


def perfect_items() -> dict[str, Item]:
    """fact id -> the item a perfect extractor gives for it."""
    items: dict[str, Item] = {}
    for study in studies():
        for c in study["conditions"]:
            items[c["id"]] = Item.build("condition", {"label": c["label"], "role": c["role"]}, fact_spans(c["id"]))
        for k in study["metrics"]:
            items[k["id"]] = Item.build("metric", {"name": k["name"], "canonical": k["canonical"],
                                                   "higher_is_better": k["higher_is_better"]}, fact_spans(k["id"]))
        for m in study["measurements"]:  # as the engine's protocol has it: links in `links`, not in fields
            cond, met = items[m["condition"]].item_id, items[m["metric"]].item_id
            items[m["id"]] = Item.build("measurement", {"value": m["value"], "dataset": m["dataset"]},
                                        fact_spans(m["id"]), links={"condition": cond, "metric": met})
        a = study["author_claim"]
        items[a["id"]] = Item.build("author_claim", {"direction": a["direction"]}, fact_spans(a["id"]))
    for fact, item in items.items():  # S001 found by regex, S002 by the LLM, S001.m3 by both
        by = (REGEX, LLM) if fact == "S001.m3" else (REGEX,) if fact.startswith("S001") else (LLM,)
        items[fact] = item.model_copy(update={"found_by": by})
    return items


def engine_answer(items: dict[str, Item]) -> dict[str, Any]:
    def side(m: str, c: str, value: float) -> dict[str, Any]:
        return {"condition": items[c].item_id, "measurement": items[m].item_id, "value": value}

    return {"system": "evidence-engine", "question": QUESTION, "label": "mixed",
            "counts": {"supporting": 1, "contradicting": 1, "neutral": 0, "undetermined": 0},
            "studies": [{"document": "S001", "direction": "supports", "delta": 0.08, "metric": "factual_accuracy",
                         "treatment": side("S001.m2", "S001.c2", 0.70), "control": side("S001.m1", "S001.c1", 0.62),
                         "author_claim": {"item": items["S001.a1"].item_id, "direction": "improves",
                                          "agrees_with_data": True}, "reason": None},
                        {"document": "S002", "direction": "contradicts", "delta": -0.05, "metric": "hallucination_rate",
                         "treatment": side("S002.m2", "S002.c2", 0.25), "control": side("S002.m1", "S002.c1", 0.20),
                         "author_claim": {"item": items["S002.a1"].item_id, "direction": "no_effect",
                                          "agrees_with_data": False}, "reason": None}],
            "supporting": ["S001"], "contradicting": ["S002"], "neutral": [], "undetermined": []}


def write_run(root: Path, items: list[Item], answer: dict[str, Any] | None, *, locate: Any = "document",
              reexec: Any = None, run_id: str = "run-1", settings: dict[str, Any] | None = None) -> Path:
    run = Path(root) / run_id
    run.mkdir(parents=True)
    ordered = sorted(items, key=lambda i: (i.first_start(), i.evidence_type, i.item_id))
    (run / "evidence.jsonl").write_text("".join(json.dumps(i.model_dump(mode="json")) + "\n" for i in ordered),
                                        encoding="utf-8", newline="\n")
    if answer is not None:
        dump(run / "answer.json", answer)
    if locate == "document":
        locate = [{"document": p, "evidence_type": t, "strategy": "whole", "scope": {"kind": "document"}}
                  for p in PAPERS for t in ("condition", "metric", "measurement", "author_claim")]
    if locate is not None:
        dump(run / "locate.json", locate)
    if reexec is not None:
        dump(run / "reexec.json", reexec)
    dump(run / "run.json", {"run_id": run_id, "mode": "run", "protocol": {"id": "rag-factuality", "sha256": "0" * 64},
                            "manifest_sha256": "1" * 64, "extractors": [REGEX, LLM], "outputs": {},
                            "cost": {"calls": 16, "model_calls": 8, "input_tokens": 4000, "output_tokens": 600,
                                     "seconds": 12.5}, **({"settings": settings} if settings else {})})
    return run


def baseline_answer(system: str, directions: dict[str, str], label: str) -> dict[str, Any]:
    groups = {d: sorted(p for p, x in directions.items() if x == d) for d in ("supports", "contradicts", "neutral")}
    return {"system": system, "question": QUESTION, "label": label,
            "counts": {"supporting": len(groups["supports"]), "contradicting": len(groups["contradicts"]),
                       "neutral": len(groups["neutral"]), "undetermined": 0},
            "studies": [{"document": p, "direction": d} for p, d in sorted(directions.items())],
            "supporting": groups["supports"], "contradicting": groups["contradicts"], "neutral": groups["neutral"],
            "undetermined": [], "answer_text": "..."}


# --- Part F shapes (docs/evidence-system.md F1, F2): flags, duplicates, missing information, irrelevant papers

def f_studies() -> list[dict[str, Any]]:
    """The two studies above plus: S003 a duplicate of S001; S004 missing its control value (effect
    undetermined); S005 an irrelevant paper; S006 a supporting study with an unusually large effect. S002's
    claim (no effect) disagrees with its data (contradicts). No papers or placements exist for S003-S006:
    C and the flag scores need only the studies and the answer."""
    s1, s2 = studies()
    s2["flags"], s2["duplicate_of"], s2["missing"], s2["relevant"] = ["claim_disagrees"], None, None, True
    s1["flags"], s1["duplicate_of"], s1["missing"], s1["relevant"] = [], None, None, True
    s3 = {"study_id": "S003", "paper": "S003", "level": "explicit", "relevant": True, "flags": ["duplicate"],
          "duplicate_of": "S001", "missing": None,
          "conditions": [{"id": "S003.c1", "role": "baseline", "label": "closed-book model", "aliases": []},
                         {"id": "S003.c2", "role": "rag", "label": "retrieval-augmented variant", "aliases": []}],
          "metrics": [{"id": "S003.k1", "canonical": "factual_accuracy", "name": "answer accuracy",
                       "higher_is_better": True}],
          "measurements": [{"id": "S003.m1", "condition": "S003.c1", "metric": "S003.k1", "value": 0.62, "dataset": "NQ"},
                           {"id": "S003.m2", "condition": "S003.c2", "metric": "S003.k1", "value": 0.70, "dataset": "NQ"}],
          "author_claim": {"id": "S003.a1", "direction": "improves"},
          "effect": {"direction": "supports", "delta": 0.08, "metric": "S003.k1", "treatment": "S003.m2",
                     "control": "S003.m1"}}
    s4 = {"study_id": "S004", "paper": "S004", "level": "complex", "relevant": True, "flags": [], "duplicate_of": None,
          "missing": "control",
          "conditions": [{"id": "S004.c1", "role": "baseline", "label": "vanilla model", "aliases": []},
                         {"id": "S004.c2", "role": "rag", "label": "retrieval model", "aliases": []}],
          "metrics": [{"id": "S004.k1", "canonical": "factual_accuracy", "name": "accuracy", "higher_is_better": True}],
          "measurements": [{"id": "S004.m2", "condition": "S004.c2", "metric": "S004.k1", "value": 0.55, "dataset": "NQ"}],
          "author_claim": {"id": "S004.a1", "direction": "improves"},
          "effect": {"direction": "undetermined", "delta": None, "metric": "S004.k1", "treatment": "S004.m2",
                     "control": None, "reason": "missing_control"}}
    s5 = {"study_id": "S005", "paper": "S005", "level": "explicit", "relevant": False, "flags": [], "duplicate_of": None,
          "missing": None, "conditions": [], "metrics": [], "measurements": [], "author_claim": None, "effect": None}
    s6 = {"study_id": "S006", "paper": "S006", "level": "distributed", "relevant": True, "flags": ["large_effect"],
          "duplicate_of": None, "missing": None,
          "conditions": [{"id": "S006.c1", "role": "baseline", "label": "no retrieval", "aliases": []},
                         {"id": "S006.c2", "role": "rag", "label": "with retrieval", "aliases": []}],
          "metrics": [{"id": "S006.k1", "canonical": "factual_accuracy", "name": "accuracy", "higher_is_better": True}],
          "measurements": [{"id": "S006.m1", "condition": "S006.c1", "metric": "S006.k1", "value": 0.40, "dataset": "NQ"},
                           {"id": "S006.m2", "condition": "S006.c2", "metric": "S006.k1", "value": 0.80, "dataset": "NQ"}],
          "author_claim": {"id": "S006.a1", "direction": "improves"},
          "effect": {"direction": "supports", "delta": 0.40, "metric": "S006.k1", "treatment": "S006.m2",
                     "control": "S006.m1"}}
    return [s1, s2, s3, s4, s5, s6]


F_FLAGS = {"claim_disagrees": ["S002"], "duplicate": ["S003"], "large_effect": ["S006"]}
F_DIRECTIONS = {"S001": "supports", "S002": "contradicts", "S003": "supports", "S004": "undetermined",
                "S005": "undetermined", "S006": "supports"}


def f_ground_truth(corpus_id: str = "test-f") -> dict[str, Any]:
    return {"corpus_id": corpus_id, "seed": 1, "question": QUESTION, "protocol": {"id": "rag-factuality", "sha256": "0" * 64},
            "studies": f_studies(), "placements": placements(),
            "answer": {"label": "mixed", "supporting": ["S001", "S006"], "contradicting": ["S002"], "neutral": [],
                       "undetermined": ["S004", "S005"], "duplicates": ["S003"], "flags": F_FLAGS}}


def write_f_corpus(root: Path, corpus_id: str = "test-f") -> Path:
    """The two-paper corpus with the Part F ground truth (four more studies without papers)."""
    corpus = write_corpus(root, corpus_id)
    dump(corpus / "ground_truth.json", f_ground_truth(corpus_id))
    return corpus


def f_answer(system: str = "evidence-engine", directions: dict[str, str] | None = None,
             flags: dict[str, list[str]] | None = None, duplicate_of: dict[str, str] | None = None,
             label: str = "mixed") -> dict[str, Any]:
    """An answer.json with the F1 keys: per-study `flags` and `duplicate_of`, `counts.duplicates`, top-level
    `duplicates` and `flags`. Defaults: the perfect answer on `f_ground_truth`."""
    directions = dict(F_DIRECTIONS if directions is None else directions)
    flags = {k: list(v) for k, v in (F_FLAGS if flags is None else flags).items()}
    duplicate_of = dict({"S003": "S001"} if duplicate_of is None else duplicate_of)
    dups = sorted(flags.get("duplicate", []))
    groups = {g: sorted(p for p, x in directions.items() if x == d and p not in dups)
              for g, d in (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral"),
                           ("undetermined", "undetermined"))}
    studies = []
    for doc, direction in sorted(directions.items()):
        entry = {"document": doc, "direction": direction, "flags": sorted(f for f, docs in flags.items() if doc in docs),
                 "duplicate_of": duplicate_of.get(doc), "reason": None}
        if direction == "undetermined":
            entry["reason"] = {"code": "no_pair", "text": "no rag and baseline measurement on a question metric"}
        studies.append(entry)
    return {"system": system, "question": QUESTION, "label": label,
            "counts": {**{g: len(v) for g, v in groups.items()}, "duplicates": len(dups)}, "studies": studies,
            **groups, "duplicates": dups, "flags": {f: sorted(flags.get(f, [])) for f in F_FLAGS}}
