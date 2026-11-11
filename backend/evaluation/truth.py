"""Readers for what evaluation compares: a corpus's ground truth, a run directory, answers.

Only evaluation reads `ground_truth.json` (docs/evidence-system.md, Part A, hard rule): the engine and
both baselines see `manifest.json` and `papers/` alone. Every reader here is tolerant of optional
files (a run without `locate.json`, `reexec.json`, `calls/` or `events.jsonl` is scored without those
sections), never of a malformed required one.

The per-extractor cost (Part F4, `evaluate benchmark`; our addition) is read from the run directory:
`calls/<id>.json` carries the extractor id and the ids of its model calls, `events.jsonl` the start and
end time of every extractor call, and the record cache named in `run.json` `settings.cache` (a cache
directory holding `extractor_calls.jsonl`, or the file itself; when it still exists) the token usage of
the model calls; a run without a cache gives null tokens.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evidence.contract import Item
from evidence.evidence_types import EvidenceType   # str: any evidence type name (types are open, EV4)
from evidence.rundir import (ANSWER_FILE, COMPARISONS_FILE, FUNNEL_FILE, LOCATE_FILE, REEXEC_FILE, RUN_FILE, PaperIndex,
                            RunDir)
from evidence.synthesis import SYSTEM as ENGINE  # the engine's `system` name in answer.json; baselines differ

# Ground-truth fact lists per evidence type, and the role of the placement that locates each kind of
# fact's main rendering (span accuracy compares the item's span of that role with it). A ground truth that lists its
# own `types` (fact type -> {list, main_role}; synth writes them for a recipe with a network: limitation, dependency,
# study_label) is read by those (`GroundTruth.types`, `.fact_lists`, `.main_role`); one without them (every old
# corpus) by these constants.
FACT_LISTS: dict[EvidenceType, str] = {"condition": "conditions", "metric": "metrics",
                                       "measurement": "measurements", "author_claim": "author_claim"}
MAIN_ROLE: dict[EvidenceType, str] = {"condition": "condition_label", "metric": "metric_label",
                                      "measurement": "value", "author_claim": "claim", "dataset": "dataset_label"}
TYPES: tuple[EvidenceType, ...] = ("condition", "metric", "measurement", "author_claim")
# Dataset facts (question-first redesign): one per (paper, dataset name), id `<paper>.d:<name>`, data `{name}`,
# no placements (a dataset item is right when its name matches). They live in `GroundTruth.datasets`, apart from
# `facts`, so the scoring of protocols without a `dataset` type (which iterates `facts` and TYPES) is unchanged.
DATASET: EvidenceType = "dataset"
# The fact type of a planted limitation (a truth with its own `types`; plan 2 Task 13): A scores it for a protocol that
# declares a type of this name.
LIMITATION: EvidenceType = "limitation"


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
    seed: Any = None
    datasets: dict[str, Fact] = field(default_factory=dict)
    # corpus.json `recipe.domain` next to ground_truth.json (None for an older corpus: the default pack's)
    domain: str | None = None
    fact_lists: dict[EvidenceType, str] = field(default_factory=lambda: dict(FACT_LISTS))
    main_role: dict[EvidenceType, str] = field(default_factory=lambda: dict(MAIN_ROLE))
    # ground_truth.json `network` ({things, comparisons, chains}; synth/network.py) of a recipe with a network, else {}
    network: dict[str, Any] = field(default_factory=dict)

    @property
    def types(self) -> tuple[EvidenceType, ...]:
        """The fact types this truth lists (TYPES for a truth without `types`; never `dataset`)."""
        return tuple(self.fact_lists)

    @classmethod
    def load(cls, path: Path) -> GroundTruth:
        data = read_json(path)
        truth = cls(data["corpus_id"], data.get("question", ""), data["studies"], data.get("placements", []),
                    data.get("answer", {}))
        truth.seed = data.get("seed")
        truth.network = data.get("network") or {}
        meta = Path(path).parent / "corpus.json"
        truth.domain = ((read_json(meta).get("recipe") or {}).get("domain") if meta.is_file() else None)
        if data.get("types"):
            truth.fact_lists = {t: spec["list"] for t, spec in data["types"].items()}
            truth.main_role = {**MAIN_ROLE, **{t: spec["main_role"] for t, spec in data["types"].items()}}
        for study in truth.studies:
            for kind, key in truth.fact_lists.items():
                entries = study.get(key) or []
                for entry in [entries] if isinstance(entries, dict) else entries:
                    truth.facts[entry["id"]] = Fact(entry["id"], kind, study["paper"], study["level"], entry)
            for name in dict.fromkeys(m["dataset"] for m in study.get("measurements") or [] if m.get("dataset")):
                fid = f"{study['paper']}.d:{name}"
                truth.datasets[fid] = Fact(fid, DATASET, study["paper"], study["level"], {"name": name})
        if not truth.facts and not truth.datasets:   # nothing to score against: refuse rather than score nothing
            raise ValueError(f"{path}: no facts: the evaluation cannot score against this ground truth")
        return truth

    def of(self, paper: str, kind: EvidenceType) -> list[Fact]:
        """The paper's facts of `kind`; for `dataset`, its dataset facts in measurement order."""
        pool = self.datasets if kind == DATASET else self.facts
        return [f for f in pool.values() if f.paper == paper and f.type == kind]

    def level_of(self, paper: str) -> str:
        return next((s["level"] for s in self.studies if s["paper"] == paper), "unknown")

    def cluster_of(self, paper: str) -> str:
        """`<seed>/<parent study id>`: a duplicate belongs to its parent's cluster, and the same study at
        another level (same seed, same id) to the same cluster."""
        study = next((s for s in self.studies if s["paper"] == paper), {})
        seed = self.seed if self.seed is not None else self.corpus_id
        return f"{seed}/{study.get('duplicate_of') or study.get('study_id') or paper}"

    def placements_of(self, fact_id: str, role: str | None = None) -> list[dict[str, Any]]:
        return [p for p in self.placements if p["fact"] == fact_id and (role is None or p["role"] == role)]

    @property
    def levels(self) -> list[str]:
        return sorted({s["level"] for s in self.studies})


def paper_ids(manifest: dict[str, Any]) -> PaperIndex:
    """The corpus manifest's papers, to place an item (`evidence.rundir.PaperIndex`)."""
    return PaperIndex.of_manifest(manifest)


def document_of(item: Item, files: PaperIndex) -> str:
    """The paper an item comes from (`PaperIndex.of`: an item of a file the corpus does not list is refused)."""
    return files.of(item)


@dataclass
class Run:
    """A run directory (A3): only the files the evaluation needs; missing optional ones are None.

    `calls` are the ExtractionResults of calls/*.json (sorted by file name), `events` the extractor_call
    records of events.jsonl, `usage` model-call record id -> {input_tokens, output_tokens} from the cache
    named in run.json (None when there is no cache file); `funnel` is funnel.json and `screens` the
    `screen` events (the funnel, Part D; None without them); `comparisons` comparisons.json (None without it)."""
    root: Path
    items: list[Item]
    answer: dict[str, Any] | None
    run: dict[str, Any] | None
    locate: Any | None
    reexec: Any | None
    calls: list[dict[str, Any]] | None = None
    events: list[dict[str, Any]] | None = None
    usage: dict[str, dict[str, int]] | None = None
    funnel: dict[str, Any] | None = None
    screens: list[dict[str, Any]] | None = None
    comparisons: dict[str, Any] | None = None
    settings: Any = None   # run.json settings read back (evidence.engine.Settings; RunDir.settings), None without

    @classmethod
    def load(cls, root: Path, reexec: Path | None = None) -> Run:
        rd = RunDir(root)
        records = rd.events()
        return cls(rd.root, rd.items(), rd.json(ANSWER_FILE), rd.json(RUN_FILE), rd.json(LOCATE_FILE),
                   read_json(reexec) if reexec else rd.json(REEXEC_FILE), rd.calls(),
                   [e for e in records if e.get("subtype") == "extractor_call"] if records is not None else None,
                   rd.usage(), rd.json(FUNNEL_FILE),
                   [e for e in records if e.get("subtype") == "screen"] if records is not None else None,
                   rd.json(COMPARISONS_FILE), rd.settings)
