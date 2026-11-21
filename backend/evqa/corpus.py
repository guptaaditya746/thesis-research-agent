"""What the QA system may read: the questions (text, qid and the intent card answers) and the paper.md files of
data/dataset. Never data/seed: the pipeline steps get their inputs only through this module (seed wall test).

The dataset's question records also carry labels for the evaluation (type, answerable, intent_text, ...); questions()
strips them (leak guard), so no step can read the question type, whether it is answerable, or anything about gold.
"""
from __future__ import annotations

import json
from typing import Any

from evqa.paths import DATASET

QUESTION_KEYS = ("qid", "question", "intent_card")     # the only keys of a pipeline-facing question record
CARD_KEYS = ("point", "answer")                        # the only keys of an intent card entry (the user's answers)


def papers(domain: str) -> dict[str, str]:
    """{paper id: paper.md text} of every written paper of the domain (practice and test papers alike)."""
    root = DATASET / domain
    return {p.parent.name: p.read_text(encoding="utf-8") for p in sorted(root.glob("*/paper.md"))}


def pipeline_record(rec: dict[str, Any]) -> dict[str, Any]:
    """The part of a dataset question record the pipeline may see: qid, question text, and per intent card point
    only the user's answer. Everything else (type, answerable, split, gold, why, closest facts, template) is dropped."""
    card = [{k: str(c[k]) for k in CARD_KEYS if k in c} for c in rec.get("intent_card") or []]
    return {"qid": str(rec["qid"]), "question": str(rec["question"]), "intent_card": card}


def questions(domain: str, split: str = "test") -> list[dict[str, Any]]:
    """Pipeline-facing question records (pipeline_record): qid, question, intent_card [{point, answer}]."""
    path = DATASET / domain / "questions" / f"{split}.jsonl"
    return [pipeline_record(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
