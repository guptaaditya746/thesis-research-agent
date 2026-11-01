"""Extractors take their topic words from the protocol's domain pack (D35): the engine fills each config from
`domains/<name>/words.yaml`, a protocol's own config wins, and no extractor falls back to words in code. For
`rag` the filled configs are compared with the EV3b snapshot (evidence/tests/fixtures/ev3b_configs.json, D36)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from agent.anchor import Index, text_sha256
from evidence import extractors
from evidence.contract import DocumentRef, ExtractionTask, Item, ProtocolRef
from evidence.engine import build_extractors
from evidence.extractors import abbrev, dataset, gliner, numbers, regex, units
from evidence.pack import DOMAINS, load_pack
from evidence.protocol import ExtractorRef, Protocol, load

from .conftest import PROTOCOL

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "ev3b_configs.json"
PROTOCOLS = sorted((DOMAINS / "rag" / "protocols").glob("*.yaml"))
# D35/D36: the snapshot's sha256 entries were updated when the measurement type gained form and value_total (Task 6)
OLD_SHA = {key.split("/")[0]: sha for key, sha in json.loads(SNAPSHOT.read_text(encoding="utf-8")).items()
           if key.endswith("/sha256")}
# the keys that hold topic words; an LLM or agent extractor gets none of them
WORD_KEYS = ("conditions", "metrics", "labels", "pattern", "fraction_metrics", "not_a_system", "subject", "claims",
             "system_nouns",
             "supplement")
TEXT = "The retrieval-augmented model reaches 71% accuracy."
TASK = ExtractionTask(protocol=ProtocolRef(id="p", sha256="x"), evidence_type="metric", field_schema_sha256="x",
                      document=DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(TEXT)))


class Ctx:
    @staticmethod
    def text() -> str:
        return TEXT

    @staticmethod
    def index() -> Index:
        return Index(TEXT)

    @staticmethod
    def context_items() -> list[Item]:
        return []


def effective(ex: Any) -> dict[str, Any]:
    """The words one extractor uses, in the snapshot's shape."""
    if isinstance(ex, (regex.RegexExtractor, abbrev.Abbrev)):
        return dict(ex.patterns)
    if isinstance(ex, (units.MeasurementUnitsRegex, numbers.NumberMeasurement)):
        return {**ex.patterns, "fraction_metrics": ex.fractions}
    if isinstance(ex, dataset.DatasetRegex):
        return {"names": ex.names, "pattern": ex.pattern.pattern}
    if isinstance(ex, gliner.GlinerExtractor):
        return {"labels": ex.labels, **ex.words}
    if ex.spec.kind in ("llm", "agent"):
        return {k: v for k, v in ex.spec.config.items() if k in WORD_KEYS}
    return {k: v for k, v in ex.spec.config.items() if k not in regex.INJECTED and k != "description"}


def all_protocols() -> list[Protocol]:
    return [load(path) for path in PROTOCOLS]


def effective_configs(protocols: list[Protocol]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in protocols:
        out[f"{p.id}/sha256"] = p.sha256
        for etype, cascade in build_extractors(p).items():
            for ref, ex in cascade:
                out[f"{p.id}/{etype}/{ref.name}"] = json.loads(json.dumps(effective(ex)))
    return out


def with_config(proto: Protocol, etype: str, name: str, config: dict[str, Any]) -> Protocol:
    spec = proto.evidence_types[etype]
    refs = tuple(ExtractorRef(name=r.name, config={**r.config, **config}) if r.name == name else r
                 for r in spec.extractors)
    return proto.model_copy(update={"evidence_types": {**proto.evidence_types,
                                                       etype: spec.model_copy(update={"extractors": refs})}})


def build(proto: Protocol, etype: str, name: str) -> Any:
    return next(ex for ref, ex in build_extractors(proto)[etype] if ref.name == name)


def test_rag_filled_configs_match_ev3b_snapshot():
    # migration check (D36): reports differences; update the fixture only with a reason in the commit message
    assert effective_configs(all_protocols()) == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_protocol_wins_over_pack():
    proto = with_config(load(PROTOCOL), "metric", "regex_metric", {"metrics": [["acc", "accuracy", True]]})
    ex = build(proto, "metric", "regex_metric")
    assert ex.patterns["metrics"] == [["acc", "accuracy", True]]


def test_protocol_without_domain_uses_rag_and_keeps_hash():
    for path in PROTOCOLS:
        p = load(path)
        assert p.domain == "rag" and p.sha256 == OLD_SHA[path.stem]


def test_extractors_have_no_code_word_fallback():
    with pytest.raises(KeyError):
        extractors.get("regex_metric", {"evidence_type": "metric"}).extract(TASK, Ctx)


def test_extractor_id_changes_when_pack_words_change(tmp_path):
    shutil.copytree(DOMAINS / "rag", tmp_path / "rag")
    words = tmp_path / "rag" / "words.yaml"
    words.write_text(words.read_text(encoding="utf-8").replace(r"(?i)\blatency\b", r"(?i)\blatency\s+ms\b"),
                     encoding="utf-8")

    def ident(pack: Any) -> str:
        return extractors.get("regex_metric", {**pack.extractor_config("metric", "regex_metric"),
                                               "evidence_type": "metric"}).spec.extractor_id

    rag, changed = load_pack("rag"), load_pack("rag", root=tmp_path)
    assert ident(rag) == ident(load_pack("rag")) and ident(rag) != ident(changed)
