"""Oracle synthesis: the engine's synthesis on perfect evidence (Tim M2 §5C, extraction vs synthesis errors).

`items_from_truth` builds the items a perfect extractor would give: one per ground-truth fact, its fields
in the protocol's field schema, its spans at the fact's main-role placements (MAIN_ROLE), a measurement
linked to its condition and metric items, `found_by=("oracle",)`. `run` puts them through
evidence.synthesis.answer and writes a run directory (`write_run`) whose answer.json has `system:
oracle-synthesis`, so `evaluate score --oracle` can tell a system's upstream errors (the oracle is right)
from downstream ones (the oracle is wrong too).

The oracle reads ground_truth.json: it is a diagnostic, not a system under test. Its synthesis and the
generator's truth share evidence/rules.py, so for the engine it is a check of the code path, not an
independent validation of the rules.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.anchor import selector_at
from evidence import protocol as protocol_module
from evidence.contract import Item, Span
from evidence.rundir import ANSWER_FILE, EVIDENCE_FILE, LOCATE_FILE, REEXEC_FILE, RUN_FILE, Corpus
from evidence.synthesis import answer as synthesize

from .truth import MAIN_ROLE, TYPES, GroundTruth

SYSTEM = "oracle-synthesis"
FOUND_BY = ("oracle",)


def dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8", newline="\n")


def fields_of(fact_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """The item fields of a fact, as the protocol's field schema has them (links are not fields)."""
    if fact_type == "condition":
        return {"label": data["label"], "role": data["role"]}
    if fact_type == "metric":
        return {"name": data["name"], "canonical": data["canonical"], "higher_is_better": data["higher_is_better"]}
    if fact_type == "measurement":
        return {"value": data["value"], "dataset": data.get("dataset")}
    return {"direction": data["direction"]}


def items_from_truth(truth: GroundTruth, corpus_dir: Path) -> tuple[dict[str, list[Item]], dict[str, str]]:
    """(document -> its items in document order, fact id -> item id). Condition and metric items are built
    before measurements, which link to them; a fact without a main-role placement is a ValueError."""
    corpus = Corpus(corpus_dir)
    papers = {p.id: p for p in corpus.papers}
    texts: dict[str, str] = {}
    items: dict[str, list[Item]] = {}
    item_of: dict[str, str] = {}
    for kind in TYPES:
        for fact in (f for f in truth.facts.values() if f.type == kind):
            paper = papers[fact.paper]
            text = texts.setdefault(paper.id, corpus.text(paper))
            role = MAIN_ROLE[kind]
            spans = [Span.of(role, selector_at(text, p["start"], p["end"], file=paper.file))
                     for p in truth.placements_of(fact.id, role) if p.get("paper", fact.paper) == fact.paper]
            if not spans:
                raise ValueError(f"{fact.id}: no {role} placement")
            links = ({"condition": item_of[fact.data["condition"]], "metric": item_of[fact.data["metric"]]}
                     if kind == "measurement" else None)
            item = Item.build(kind, fields_of(kind, fact.data), spans, links=links)
            items.setdefault(fact.paper, []).append(item.model_copy(update={"found_by": FOUND_BY}))
            item_of[fact.id] = item.item_id
    for doc in items.values():
        doc.sort(key=lambda i: (i.first_start(), i.evidence_type, i.item_id))
    return items, item_of


def write_run(run: Path, items: list[Item], answer: dict[str, Any] | None, run_json: dict[str, Any], *,
              locate: Any = None, reexec: Any = None) -> Path:
    """A run directory as scoring reads it (evidence/rundir.py): evidence.jsonl (document order), answer.json,
    locate.json and reexec.json when given, run.json."""
    run = Path(run)
    run.mkdir(parents=True, exist_ok=True)
    ordered = sorted(items, key=lambda i: (i.first_start(), i.evidence_type, i.item_id))
    (run / EVIDENCE_FILE).write_text("".join(json.dumps(i.model_dump(mode="json")) + "\n" for i in ordered),
                                     encoding="utf-8", newline="\n")
    if answer is not None:
        dump(run / ANSWER_FILE, answer)
    if locate is not None:
        dump(run / LOCATE_FILE, locate)
    if reexec is not None:
        dump(run / REEXEC_FILE, reexec)
    dump(run / RUN_FILE, run_json)
    return run


def run(protocol_path: Path, corpus_dir: Path, out: Path) -> Path:
    """The oracle run directory `out`: the protocol's synthesis over the ground truth's facts."""
    protocol = protocol_module.load(protocol_path)
    truth = GroundTruth.load(Path(corpus_dir) / "ground_truth.json")
    corpus = Corpus(corpus_dir)
    items, _ = items_from_truth(truth, corpus_dir)
    answer, _ = synthesize(protocol, [p.id for p in corpus.papers], items)
    answer["system"] = SYSTEM
    run_json = {"run_id": Path(out).name, "mode": "oracle", "protocol": {"id": protocol.id, "sha256": protocol.sha256},
                "corpus_id": truth.corpus_id, "manifest_sha256": corpus.manifest_sha256,
                "extractors": list(FOUND_BY), "outputs": {}}
    return write_run(out, [i for doc in items.values() for i in doc], answer, run_json)
