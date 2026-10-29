"""Extractor ids of EV1/EV2 runs survive the question-first changes (final review, finding 1): the modules
hashed into every extractor's code hash (base.SHARED_SOURCES) are unchanged, so rebuilding an old run's
extractors from its protocol gives exactly the ids in its run.json, and replay and the call caches still hit."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.engine import build_extractors
from evidence.extractors import regex
from evidence.protocol import load

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "tests" / "EV2" / "runs"
PROTOCOLS = ROOT / "evidence" / "protocols"
# (stored run, the protocol file it ran): regex only, the regex+LLM cascade, the cascade with the agentic extractor
OLD_RUNS = (("regex-only/rag-tpl-s1-mixed", "rag-factuality.yaml"), ("cascade/rag-claude-k1-mixed", "rag-factuality.yaml"),
            ("agentic/rag-claude-small-distributed", "rag-factuality-agentic.yaml"))


def ids(protocol_path: Path, settings: dict) -> set[str]:
    cascades = build_extractors(load(protocol_path), settings["selection"], model=settings["model"])
    return {extractor.spec.extractor_id for cascade in cascades.values() for _, extractor in cascade}


def test_the_rag_factuality_protocol_rebuilds_the_ev2_extractor_ids() -> None:
    run = json.loads((RUNS / "regex-only" / "rag-tpl-s1-mixed" / "run.json").read_text(encoding="utf-8"))
    protocol = PROTOCOLS / "rag-factuality.yaml"
    assert load(protocol).sha256 == run["protocol"]["sha256"]
    assert ids(protocol, run["settings"]) == set(run["extractor_specs"])
    assert regex.CODE_SHA256[:12] == "f1647847fdf9"


@pytest.mark.parametrize(("name", "protocol"), OLD_RUNS)
def test_old_runs_rebuild_their_extractor_ids(name: str, protocol: str) -> None:
    run = json.loads((RUNS / name / "run.json").read_text(encoding="utf-8"))
    assert load(PROTOCOLS / protocol).sha256 == run["protocol"]["sha256"]
    rebuilt, old = ids(PROTOCOLS / protocol, run["settings"]), set(run["extractor_specs"])
    # The agentic extractor is a new one since the EV3 fixes (prompt v3, agent/loop.py in its code hash): its
    # ids must differ, so no cached EV2 agent run is reused; every other extractor keeps its id.
    agentic = {i for i in rebuilt | old if i.startswith("agentic@")}
    assert rebuilt - agentic == old - agentic
    assert not rebuilt & old & agentic and (name.startswith("agentic/") == bool(agentic))


def test_the_contract_still_takes_dataset_items() -> None:
    from evidence.contract import ExtractionResult, Item, Span
    span = Span(role="dataset_label", selector={"file": "p.md", "start": 0, "end": 4})
    item = Item.build("dataset", {"name": "TriviaCheck"}, [span])
    result = ExtractionResult(extractor_id="x", task_sha256="t", status="ok", items=(item.model_dump(),))
    assert item.item_id.startswith("d-") and result.items[0].evidence_type == "dataset"
    with pytest.raises(ValueError):
        Item(item_id="z-1", evidence_type="nonsense", fields={}, spans=(span,))
