"""Readers for what evaluation compares: a corpus's ground truth, a run directory, answers.

Only evaluation reads `ground_truth.json` (docs/evidence-system.md, Part A, hard rule): the engine and
both baselines see `manifest.json` and `papers/` alone. Every reader here is tolerant of optional
files (a run without `locate.json` or `reexec.json` is scored without those sections), never of a
malformed required one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from evidence.contract import EvidenceType, Item

# Ground-truth fact lists per evidence type, and the role of the placement that locates each kind of
# fact's main rendering (span accuracy compares the item's span of that role with it).
FACT_LISTS: dict[EvidenceType, str] = {"condition": "conditions", "metric": "metrics",
                                       "measurement": "measurements", "author_claim": "author_claim"}
MAIN_ROLE: dict[EvidenceType, str] = {"condition": "condition_label", "metric": "metric_label",
                                      "measurement": "value", "author_claim": "claim"}
TYPES: tuple[EvidenceType, ...] = ("condition", "metric", "measurement", "author_claim")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass(frozen=True)
class Fact:
    """One ground-truth fact: a condition, metric, measurement or author claim of one study."""
    id: str
    type: EvidenceType
    paper: str
    level: str
    data: dict[str, Any]


@dataclass
class GroundTruth:
    """ground_truth.json (section 2), indexed by fact id and by (paper, evidence type)."""
    corpus_id: str
    question: str
    studies: list[dict[str, Any]]
    placements: list[dict[str, Any]]
    answer: dict[str, Any]
    facts: dict[str, Fact] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> GroundTruth:
        data = read_json(path)
        truth = cls(data["corpus_id"], data.get("question", ""), data["studies"], data.get("placements", []),
                    data.get("answer", {}))
        for study in truth.studies:
            for kind, key in FACT_LISTS.items():
                entries = study.get(key) or []
                for entry in [entries] if isinstance(entries, dict) else entries:
                    truth.facts[entry["id"]] = Fact(entry["id"], kind, study["paper"], study["level"], entry)
        return truth

    def of(self, paper: str, kind: EvidenceType) -> list[Fact]:
        return [f for f in self.facts.values() if f.paper == paper and f.type == kind]

    def level_of(self, paper: str) -> str:
        return next((s["level"] for s in self.studies if s["paper"] == paper), "unknown")

    def placements_of(self, fact_id: str, role: str | None = None) -> list[dict[str, Any]]:
        return [p for p in self.placements if p["fact"] == fact_id and (role is None or p["role"] == role)]

    @property
    def levels(self) -> list[str]:
        return sorted({s["level"] for s in self.studies})


def paper_ids(manifest: dict[str, Any]) -> dict[str, str]:
    """File name (as in the manifest, and its base name) -> paper id, to place an item's spans."""
    out: dict[str, str] = {}
    for paper in manifest.get("papers", []):
        file = paper.get("file") or f"{paper['id']}.md"
        out[file] = paper["id"]
        out[PurePosixPath(file).name] = paper["id"]
    return out


def document_of(item: Item, files: dict[str, str]) -> str:
    """The paper an item comes from: the file of its first span, mapped through the manifest."""
    file = min(item.spans, key=lambda s: s.selector["start"]).selector["file"]
    return files.get(file) or files.get(PurePosixPath(file).name) or PurePosixPath(file).stem


@dataclass
class Run:
    """A run directory (section 3): only the files the evaluation needs; missing optional ones are None."""
    root: Path
    items: list[Item]
    answer: dict[str, Any] | None
    run: dict[str, Any] | None
    locate: Any | None
    reexec: Any | None

    @classmethod
    def load(cls, root: Path, reexec: Path | None = None) -> Run:
        root = Path(root)
        evidence = root / "evidence.jsonl"
        items = [Item.model_validate(row) for row in read_jsonl(evidence)] if evidence.is_file() else []

        def optional(name: str) -> Any | None:
            path = root / name
            return read_json(path) if path.is_file() else None

        stability = read_json(reexec) if reexec else optional("reexec.json")
        return cls(root, items, optional("answer.json"), optional("run.json"), optional("locate.json"), stability)
