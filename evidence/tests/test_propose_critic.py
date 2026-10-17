"""The critic (docs/evidence-system.md Part E): its deterministic checks flag a broken draft; its LLM checklist
is recorded as the model answered it."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from evidence.propose import critic, frame
from evidence.propose.common import dump_yaml

from .propose_support import RAG_FRAME, Scripted, flow


def by_id(checks: list[dict]) -> dict[str, dict]:
    return {c["id"]: c for c in checks}


def test_critic_passes_the_rag_draft_and_records_the_checklist(tmp_path: Path) -> None:
    reply = {c: {"ok": True, "message": "fine"} for c in critic.LLM_CHECKS}
    reply["scope"] = {"ok": False, "message": "the term retrieval admits retrieval-only papers"}
    d = flow(tmp_path / "p", Scripted(critic_reply=reply), until="critic")
    data = json.loads((d / "critic.json").read_text(encoding="utf-8"))
    checks = by_id(data["checks"])
    assert data["ok"] is True
    assert [c["id"] for c in data["checks"] if c["kind"] == "deterministic"] == [
        "parses", "outcomes_complete", "terms_cover_synonyms", "regex_matches_enums", "screen_present", "label_complete",
        "extractors_registered", "vocabulary_direction"]
    assert checks["scope"] == {"id": "scope", "kind": "llm", "ok": False,
                               "message": "the term retrieval admits retrieval-only papers"}
    assert data["call"]["step"] == "critic" and data["call"]["cached"] is False


def test_critic_flags_a_broken_draft(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="draft")
    draft = yaml.safe_load((d / "draft.yaml").read_text(encoding="utf-8"))
    del draft["screen"]
    draft["evidence_types"]["metric"]["extractors"].append({"name": "no_such_extractor"})
    draft["synthesis"]["metrics"][1]["higher_is_better"] = True
    (d / "draft.yaml").write_text(dump_yaml(draft), encoding="utf-8")
    critic.run(d, model=Scripted().model)
    data = json.loads((d / "critic.json").read_text(encoding="utf-8"))
    checks = by_id(data["checks"])
    assert data["ok"] is False
    assert checks["parses"]["ok"]                                   # these still validate as a protocol
    assert not checks["screen_present"]["ok"]
    assert not checks["extractors_registered"]["ok"] and "no_such_extractor" in checks["extractors_registered"]["message"]
    assert not checks["outcomes_complete"]["ok"] and "hallucination_rate" in checks["outcomes_complete"]["message"]


def test_checks_on_a_protocol_that_does_not_parse() -> None:
    f = frame.annotate("Q?", frame.FrameReply.model_validate(RAG_FRAME), None)
    text = (Path(critic.__file__).parents[1] / "protocols" / "rag-factuality.yaml").read_text(encoding="utf-8")
    broken = text.replace("    - {then: insufficient}", "    - {when: {neutral: \"==0\"}, then: insufficient}")
    checks = by_id(critic.checks(broken, f))
    assert not checks["parses"]["ok"] and not checks["label_complete"]["ok"]
    assert checks["terms_cover_synonyms"]["message"].startswith("not checked")
    assert checks["screen_present"]["ok"] and checks["extractors_registered"]["ok"]


def test_coverage_names_what_the_regex_patterns_miss() -> None:
    reply = json.loads(json.dumps(RAG_FRAME))
    reply["control"]["synonyms"].append("parametric-only model")
    reply["outcomes"][0]["synonyms"].append("F1")
    f = frame.annotate("Q?", frame.FrameReply.model_validate(reply), None)
    text = (Path(critic.__file__).parents[1] / "protocols" / "rag-factuality.yaml").read_text(encoding="utf-8")
    check = by_id(critic.checks(text, f))["terms_cover_synonyms"]
    assert not check["ok"]
    assert "'parametric-only model' (regex_condition)" in check["message"] and "'F1' (regex_metric)" in check["message"]


def test_vocabulary_direction_is_checked() -> None:
    from evidence.propose import vocab
    reply = json.loads(json.dumps(RAG_FRAME))
    reply["outcomes"][1]["higher_is_better"] = True
    f = frame.annotate("Q?", frame.FrameReply.model_validate(reply), vocab.load("rag-factuality"))
    text = (Path(critic.__file__).parents[1] / "protocols" / "rag-factuality.yaml").read_text(encoding="utf-8")
    checks = by_id(critic.checks(text, f))
    assert not checks["vocabulary_direction"]["ok"] and "hallucination_rate" in checks["vocabulary_direction"]["message"]
    assert not checks["outcomes_complete"]["ok"]
