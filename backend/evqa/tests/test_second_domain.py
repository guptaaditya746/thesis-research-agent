"""Plan v2 step 7: a tiny materials-science fixture (3 made-up papers, 2 questions, fake LM) runs Spec -> Find ->
Extract -> Link -> Answer, to show the pipeline needs no medical words, fields or files. No seed, no network."""
from __future__ import annotations

import json
import re

import pytest

import evqa.corpus
import evqa.lm
from evqa import run as runner
from evqa.contracts import Answer, Link, Row, RunConfig, read_jsonl
from evqa.spec import build

PAPERS = {
    "M-1": "# Annealed QX-7 sheets\n\nAbstract. We study alloy QX-7.\n\n## 1. Methods\n\nSpecimens of alloy QX-7 were "
           "annealed at 600 C for two hours.\n\n## 2. Results\n\nThe yield strength of QX-7 was 412 MPa.\n",
    "M-2": "# QX-7 plates\n\nAbstract. Plates of alloy QX-7 were tested.\n\n## 1. Methods\n\nQX-7 plates were annealed "
           "at 600 °C before testing.\n\n## 2. Results\n\nThe yield strength of QX-7 reached 405 MPa.\n",
    "M-3": "# Cast QX-7\n\nAbstract. Cast alloy QX-7 is studied.\n\n## 1. Methods\n\nAs-cast QX-7 samples were used "
           "without heat treatment.\n\n## 2. Results\n\nThe yield strength of QX-7 was 350 MPa.\n",
}
QUESTIONS = [
    {"qid": "M-q1", "question": "What is the yield strength of QX-7 annealed at 600 C?", "intent_card": []},
    {"qid": "M-q2", "question": "What is the yield strength of QX-7?", "intent_card": []},
]
PROCESSING = re.compile(r"annealed at 600 (?:C|°C)|As-cast")
SENTENCE = re.compile(r"[^.\n]*(?:annealed at 600|As-cast)[^.\n]*\.")
VALUE = re.compile(r"The yield strength of QX-7 (?:was|reached) (\d+) MPa\.")


def fields(prompt: str) -> dict[str, str]:
    user = prompt.split("[user]", 1)[-1]
    return {m.group(1): m.group(2).strip() for m in
            re.finditer(r"\[\[ ## (\w+) ## \]\]\n(.*?)(?=\n\n\[\[ ## |\n\nRespond with|\Z)", user, re.S)}


def same(a: str, b: str) -> bool:
    return ("annealed" in a.lower()) == ("annealed" in b.lower())


def fake(prompt: str) -> str:
    """Answers each task (named by its first output field) the way a careful reader would, from the inputs."""
    f = fields(prompt)
    task = re.search(r"order of fields: `(\w+)`", prompt).group(1)
    q = f.get("question", "")
    if task == "type":
        return json.dumps({"type": "lookup", "reason": "one value"})
    if task == "dimensions":
        fixed = PROCESSING.search(q)
        return json.dumps({"dimensions": [{"key": "processing", "question": "Which processing?",
                                           "why": "Strength depends on heat treatment.",
                                           "fixed_value": fixed.group(0) if fixed else "",
                                           "quote": fixed.group(0) if fixed else ""}]})
    if task == "subjects":
        return json.dumps({"subjects": ["QX-7"], "comparator": "", "measure": "yield strength", "dose": "",
                           "time_point": "", "patient_group": ""})
    if task == "known":
        return json.dumps({"known": False, "definition": ""})
    if task in ("synonyms", "names"):
        return json.dumps({task: []})
    if task == "same":
        return json.dumps({"same": []})
    if task == "higher_is_better":
        return json.dumps({"higher_is_better": True, "reason": "stronger"})
    if task == "decision":
        return json.dumps({"decision": "yes" if "QX-7" in prompt else "no", "reason": "names QX-7"})
    if task == "marks":
        marks = [{"id": int(m.group(1)), "role": "value" if "MPa" in m.group(2) else "context",
                  "quote": m.group(2)[:20], "subjects": ["QX-7"] if "MPa" in m.group(2) else [],
                  "columns": [] if "MPa" in m.group(2) else ["processing"]}
                 for m in re.finditer(r"^\[(\d+)\] \([^)]*\) (.*?)(?=\n\n\[\d+\] |\Z)", f["passages"], re.M | re.S)
                 if "MPa" in m.group(2) or PROCESSING.search(m.group(2))]
        return json.dumps({"marks": marks})
    if task == "kind":
        return json.dumps({"kind": "stop", "term": "", "reason": "nothing missing"})
    if task == "terms":
        return json.dumps({"terms": []})
    if task == "rows":
        m = VALUE.search(f["passage"])
        rows = [{"subject": "QX-7", "measure": "yield strength", "raw": m.group(1), "unit": "MPa",
                 "statistic": "mean", "quote": m.group(0)}] if m else []
        return json.dumps({"rows": rows})
    if task == "setting_sets":
        key = json.loads(f["dimensions"])[0]["key"]
        text = f["context"] + "\n" + f["passages"]
        s = SENTENCE.search(text)
        v = PROCESSING.search(s.group(0)) if s else None
        setting = {"dimension": key, "value": v.group(0), "quote": s.group(0).strip(), "source": "paper"} if v else \
            {"dimension": key, "value": "not stated", "quote": "", "source": "paper"}
        return json.dumps({"setting_sets": [{"settings": [setting], "extra_settings": []}]})
    if task == "verdicts":
        return json.dumps({"verdicts": [{"id": c["id"], "supported": True} for c in json.loads(f["candidates"])]})
    if task == "setting_id":
        return json.dumps({"setting_id": ""})
    if task in ("link", "verdict"):
        a, b = json.loads(f["set_a"])[0], json.loads(f["set_b"])[0]
        verdict = "same" if same(a["value"], b["value"]) else "different"
        out = {"verdict": verdict, "differs_on": [] if verdict == "same" else [a["dimension"]]}
        if task == "link":
            return json.dumps({"link": {**out, "quote_a": a["value"], "quote_b": b["value"]}})
        return json.dumps({"verdict": out})
    raise AssertionError(f"unexpected task {task}")


@pytest.fixture
def materials(monkeypatch, tmp_path):
    monkeypatch.setattr(evqa.corpus, "papers", lambda domain: dict(PAPERS))
    monkeypatch.setattr(evqa.corpus, "questions", lambda domain, split: list(QUESTIONS))
    monkeypatch.setattr(evqa.lm, "CACHE_FILE", tmp_path / "lm.jsonl")
    monkeypatch.setattr(evqa.lm, "_caches", {})
    real = evqa.lm.make_lm
    monkeypatch.setattr(evqa.lm, "make_lm", lambda cfg, ask=None: real(cfg, ask=fake))
    monkeypatch.setattr(build, "make_lm", lambda cfg, ask=None: real(cfg, ask=fake))
    return tmp_path


def test_materials_questions_run_end_to_end_without_medical_parts(materials):
    folder = runner.run(RunConfig(name="materials-fixture", domain="materials-fixture", split="practice"),
                        root=materials)
    q1 = Answer.model_validate_json((folder / "M-q1" / "answer.json").read_text())
    rows1 = read_jsonl(folder / "M-q1" / "rows.jsonl", Row)
    links1 = read_jsonl(folder / "M-q1" / "links.jsonl", Link)
    # fixed "annealed at 600 C": M-1 by code (same words), M-2 by generator + verifier (°C), M-3 different
    assert sorted(rows1[i].paper for a in q1.table for i in a.rows) == ["M-1", "M-2"]
    assert {lk.b.split("/")[0]: (lk.verdict, lk.by) for lk in links1} == {
        "M-1": ("same", "code"), "M-2": ("same", "llm"), "M-3": ("different", "llm")}
    assert not q1.not_reported and not q1.cant_tell

    q2 = Answer.model_validate_json((folder / "M-q2" / "answer.json").read_text())
    rows2 = read_jsonl(folder / "M-q2" / "rows.jsonl", Row)
    assert q2.columns == ["processing"] and len(q2.table) == 3
    label = {rows2[a.rows[0]].paper: a.cells["processing"] for a in q2.table}
    assert label["M-1"] == label["M-2"] == "annealed at 600 C"     # one label for sets linked "same"
    assert label["M-3"] == "As-cast"
