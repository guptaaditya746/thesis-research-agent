"""Records after review: every attempt of a call stays replayable (5), failed model calls are recorded and
make the result partial (10), re-execution keeps calls of one extractor apart by cascade position (13)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence import engine
from evidence.replay import reexec, replay

from .conftest import empty, make_corpus, provider_of, scripted


def test_retry_errors_keeps_earlier_runs_replayable(protocol_file: Path, tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path / "c", ("S001",))
    state = {"fail": True}

    def script(t: str, doc: str, prompt: str) -> dict[str, Any]:
        if state["fail"]:
            raise RuntimeError("gateway down")
        return empty(t, doc, prompt)

    provider = provider_of(scripted(script, []))
    a = engine.run(protocol_file, corpus, tmp_path / "out", cache=tmp_path / "cache", provider=provider, run_id="A")
    state["fail"] = False
    b = engine.run(protocol_file, corpus, tmp_path / "out", cache=tmp_path / "cache", provider=provider, run_id="B",
                   retry_errors=True)
    assert replay(a)[1]["ok"] and replay(b)[1]["ok"]
    statuses = {json.loads(p.read_text())["status"] for p in (b / "calls").glob("*.json")}
    assert statuses == {"ok"}
    c = engine.run(protocol_file, corpus, tmp_path / "out", cache=tmp_path / "cache", provider=provider, run_id="C")
    assert json.loads((c / "run.json").read_text())["outputs"] == json.loads((b / "run.json").read_text())["outputs"]


def test_failed_model_calls_are_recorded_and_a_failed_retry_is_partial(protocol_file: Path, tmp_path: Path) -> None:
    corpus = make_corpus(tmp_path / "c", ("S001",))

    def script(t: str, doc: str, prompt: str) -> dict[str, Any]:
        if t == "retry":
            raise RuntimeError("retry failed")
        if t == "author_claim":
            return {"items": [{"fields": {"direction": "improves"}, "quotes": {"claim": "a sentence not in the paper"}}]}
        return empty(t, doc, prompt)

    root = engine.run(protocol_file, corpus, tmp_path / "out", selection="llm-only", provider=provider_of(scripted(script, [])))
    claim = next(json.loads(p.read_text()) for p in (root / "calls").glob("*.json")
                 if json.loads(p.read_text())["extractor_id"].startswith("llm_author_claim"))
    assert claim["status"] == "partial" and len(claim["model_calls"]) == 2
    assert [r["reason"] for r in claim["rejected"]] == ["not_found"]

    def broken(alias: str) -> Any:
        raise RuntimeError("down")

    root = engine.run(protocol_file, corpus, tmp_path / "out2", selection="llm-only", provider=broken)
    for path in (root / "calls").glob("*.json"):
        result = json.loads(path.read_text())
        assert result["status"] == "error" and len(result["model_calls"]) == 1


def test_reexec_keeps_two_steps_of_one_extractor_apart(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    text = protocol_file.read_text(encoding="utf-8")
    protocol_file.write_text(text.replace("      - name: regex_measurement\n",
                                          "      - name: regex_measurement\n      - name: regex_measurement\n"
                                          "        config: {variant: 2}\n"), encoding="utf-8")
    root = engine.run(protocol_file, corpus, tmp_path / "runs", selection="regex-only", provider=None)
    report = json.loads((reexec(root) / "reexec.json").read_text())
    rows = [c for c in report["calls"] if c["extractor"] == "regex_measurement"]
    assert len(rows) == 10 and {c["position"] for c in rows} == {0, 1}
    assert all(c["outcome"] == "identical" for c in rows)
