"""The funnel order in the protocols (regex, then abbreviations, then GLiNER, then numbers, then the LLM), and the
engine's skip of an extractor that says it is unavailable."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from evaluation import cli
from evidence import engine, extractors, protocol, replay
from evidence.extractors import gliner

from .conftest import PROTOCOL, corpus_of
from .fake_gliner import FakeGliner

PROTOCOLS = PROTOCOL.parent
EXAMPLE = Path(__file__).resolve().parents[2] / "synth" / "examples" / "rag-demo-explicit"
# Per protocol and evidence type, the cascade as written (the GLiNER steps stay in the file; the engine leaves them
# out when the service is missing). Specialised first steps stay where they fit: regex_condition_kind and
# regex_measurement_units are those protocols' "regex" step. A step that would write fields the protocol's schema
# forbids is left out: abbrev_condition and gliner_condition write {label, role}, which best-* ({label, kind}) and
# inv-methods ({label}) do not take. rag-latency: regex_measurement_units is its "regex" step; number_measurement takes the
# same metrics/fraction_metrics config (time units and ms headers read as seconds); its metric steps take the latency wording.
ROLE = ["regex_condition", "abbrev_condition", "gliner_condition", "llm_condition"]
METRIC = ["regex_metric", "abbrev_metric", "gliner_metric", "llm_metric"]
MEASURE = ["regex_measurement", "number_measurement", "llm_measurement"]
CLAIM = ["regex_author_claim", "llm_author_claim"]
KIND = ["regex_condition_kind", "llm_condition"]
EXPECTED: dict[str, dict[str, list[str]]] = {
    "rag-factuality-funnel": {"condition": ROLE, "metric": METRIC, "measurement": MEASURE, "author_claim": CLAIM},
    "rag-hallucination": {"condition": ROLE, "metric": METRIC, "measurement": MEASURE, "author_claim": CLAIM},
    "rag-latency": {"condition": ROLE, "metric": METRIC, "measurement": ["regex_measurement_units", "number_measurement", "llm_measurement"]},
    "cons-accuracy": {"condition": ROLE, "metric": METRIC, "measurement": MEASURE, "author_claim": CLAIM},
    "cons-hallucination": {"condition": ROLE, "metric": METRIC, "measurement": MEASURE, "author_claim": CLAIM},
    "best-accuracy": {"condition": KIND, "metric": METRIC, "measurement": MEASURE},
    "best-hallucination": {"condition": KIND, "metric": METRIC, "measurement": MEASURE},
    "inv-metrics": {"metric": METRIC},
    "inv-methods": {"condition": KIND},
    "inv-datasets": {"dataset": ["regex_dataset", "gliner_dataset", "llm_dataset"]},
}
# the fixed protocol keeps its old order (its hash is pinned in test_ten_protocols)
FIXED = {"rag-factuality": {"condition": ["regex_condition", "llm_condition"], "metric": ["regex_metric", "llm_metric"],
                            "measurement": ["regex_measurement", "llm_measurement"], "author_claim": CLAIM}}
STAGE = {"regex": 0, "abbrev": 1, "gliner": 2, "number": 3, "llm": 4}


def cascade_of(qid: str) -> dict[str, list[str]]:
    p = protocol.load(PROTOCOLS / f"{qid}.yaml")
    return {t: [r.name for r in s.extractors] for t, s in p.evidence_types.items()}


@pytest.mark.parametrize("qid", [*EXPECTED, *FIXED])
def test_cascade_order(qid: str) -> None:
    got = cascade_of(qid)
    assert got == (EXPECTED.get(qid) or FIXED[qid])
    for etype, names in got.items():   # regex, abbrev, GLiNER, number, LLM: never backwards
        stages = [STAGE[n.split("_", 1)[0]] for n in names]
        assert stages == sorted(stages) and stages[0] == 0, (qid, etype, names)
        assert set(names) <= set(extractors.names())


def test_the_funnel_sibling_asks_the_same_question_with_its_own_id() -> None:
    old = protocol.load(PROTOCOLS / "rag-factuality.yaml")
    new = protocol.load(PROTOCOLS / "rag-factuality-funnel.yaml")
    assert (new.id, new.question, new.kind) == ("rag-factuality-funnel", old.question, old.kind)
    assert new.sha256 != old.sha256


TEXT = ("# Study\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R). We report "
        "factual accuracy (FA).\n\n## Results\n\n| System | Dataset | FA (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n| R | NQ | 70.0 |\n")


def metric_protocol(tmp_path: Path, steps: list[str]) -> Path:
    proto = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    proto["evidence_types"]["metric"]["extractors"] = [{"name": n} for n in steps]
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(proto, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def no_gliner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLINER_URL", raising=False)
    gliner.forget()


@pytest.mark.parametrize("strategy", ["all", "gaps"])
def test_unavailable_extractor_skipped_and_recorded(tmp_path: Path, strategy: str) -> None:
    path = metric_protocol(tmp_path, ["gliner_metric", "regex_metric"])
    settings = engine.Settings(corpus=str(corpus_of(tmp_path / "corpus", {"P1": TEXT})), cache=str(tmp_path / "cache"),
                               strategy=strategy, gliner_url=None)
    run = engine.execute_run(path.read_bytes(), settings, tmp_path / "runs", provider=None)
    events = [json.loads(x) for x in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    calls = [e for e in events if e["subtype"] == "extractor_call" and e["custom_metadata"]["evidence_type"] == "metric"]
    assert [(e["agent_id"].split("@")[0], e["status"]) for e in calls] == [("gliner_metric", "skipped"), ("regex_metric", "ok")]
    skipped = calls[0]
    assert skipped["custom_metadata"]["position"] == 0 and "task_sha256" not in skipped["custom_metadata"]
    assert not (run / "calls" / f"{skipped['task_id']}.json").exists()      # no checked result for it
    assert "gliner_metric" not in (tmp_path / "cache" / "extractor_calls.jsonl").read_text(encoding="utf-8")
    if (run / "calls.jsonl").exists():
        assert "gliner_metric" not in (run / "calls.jsonl").read_text(encoding="utf-8")
    items = [json.loads(x) for x in (run / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(i["evidence_type"] == "metric" for i in items)             # the next position found them


def test_a_run_with_skipped_steps_replays_and_scores(tmp_path: Path) -> None:
    run = engine.run(PROTOCOLS / "rag-factuality-funnel.yaml", EXAMPLE, tmp_path / "runs", selection="cascade",
                     provider=None, strategy="all")
    _, check = replay.replay(run)
    assert check["ok"], check["mismatched"]
    assert cli.main(["score", "--run", str(run), "--corpus", str(EXAMPLE), "--out", str(tmp_path / "out")]) == 0


def test_per_extractor_A_reports_new_extractors(tmp_path: Path) -> None:
    with FakeGliner() as server:
        settings = engine.Settings(corpus=str(EXAMPLE), cache=str(tmp_path / "cache"), strategy="all",
                                   gliner_url=server.url)
        run = engine.execute_run((PROTOCOLS / "rag-factuality-funnel.yaml").read_bytes(), settings, tmp_path / "runs",
                                 provider=None)
    assert cli.main(["score", "--run", str(run), "--corpus", str(EXAMPLE), "--out", str(tmp_path / "out")]) == 0
    report: dict[str, Any] = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    listed = {r["extractor"].split("@")[0] for r in report["extractors"]["rows"]}
    assert {"number_measurement", "abbrev_metric", "gliner_metric"} <= listed
