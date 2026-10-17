"""The evidence-level viewer (/api/ev, webapp/evapi.py) on a world made by the real tools (evidence_world.py):
corpora, protocols and proposals, engine and baseline runs with their funnel, spans, calls and traces, scores."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.anchor import read_text
from webapp.app import create_app
from webapp.evfiles import RecordCache, segments
from webapp.settings import Settings

from .evidence_world import NAME, POSIX, EvidenceWorld, build

MIXED, EXPLICIT = f"{NAME}-mixed", f"{NAME}-explicit"


def settings_for(world: EvidenceWorld, **more: object) -> Settings:
    return Settings(EV=world.root, runs=world.root / "earlier-runs", **more)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def ev_world(tmp_path_factory: pytest.TempPathFactory) -> EvidenceWorld:
    return build(tmp_path_factory.mktemp("ev") / "world")


@pytest.fixture(scope="module")
def ev(ev_world: EvidenceWorld) -> Iterator[TestClient]:
    with TestClient(create_app(settings_for(ev_world))) as c:
        yield c


def variant_name(ev_world: EvidenceWorld) -> str:
    return next(p.name for p in ev_world.corpora.iterdir() if "-cf-" in p.name)


# --- configuration and corpora -----------------------------------------------------------------------

def test_config_defaults_under_ev(ev: TestClient, ev_world: EvidenceWorld) -> None:
    config = ev.get("/api/ev/config").json()
    assert config["ev"] == str(ev_world.root)
    assert config["corpora"] == {"path": str(ev_world.corpora), "exists": True}
    assert config["cache"]["path"] == str(ev_world.cache) and config["cache"]["exists"]
    assert config["agent_work"]["path"] == str(ev_world.agent_work)
    assert config["protocols"]["path"].endswith("protocols")


def test_unconfigured_roots_are_404_with_the_variable(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(runs=tmp_path / "r"))) as c:
        assert c.get("/api/ev/corpora").json() == [] and c.get("/api/ev/runs").json() == []
        response = c.get("/api/ev/corpora/x")
        assert response.status_code == 404 and "$CORPORA" in response.json()["detail"]
        assert c.get("/api/ev/scores").json() == {"reports": [], "compares": [], "shifts": [], "benchmarks": []}


def test_corpora_list_levels_knobs_variant(ev: TestClient, ev_world: EvidenceWorld) -> None:
    corpora = {c["name"]: c for c in ev.get("/api/ev/corpora").json()}
    variant = variant_name(ev_world)
    assert {EXPLICIT, MIXED, f"{NAME}-paraphrased", variant} <= set(corpora)
    mixed = corpora[MIXED]
    assert mixed["level"] == "mixed" and mixed["renderer"] == "template" and mixed["seed"] == 7
    assert mixed["settings"]["duplicates"] == 1 and mixed["settings"]["irrelevant"] == 1
    assert mixed["answer"]["label"] and mixed["fidelity_ok"] == mixed["papers"] and mixed["variant"] is None
    cf = corpora[variant]
    assert cf["variant"]["base_corpus_id"] == mixed["corpus_id"] and cf["base"] == MIXED
    assert cf["variant"]["expected"]["after"]["label"]


def test_corpus_detail_and_paper_with_placements(ev: TestClient, ev_world: EvidenceWorld) -> None:
    detail = ev.get(f"/api/ev/corpora/{MIXED}").json()
    truth = json.loads((ev_world.corpora / MIXED / "ground_truth.json").read_text(encoding="utf-8"))
    papers = {p["id"]: p for p in detail["papers_list"]}
    assert set(papers) == {s["paper"] for s in truth["studies"]}
    irrelevant = [p for p in papers.values() if not p["relevant"]]
    assert len(irrelevant) == 1 and irrelevant[0]["direction"] is None
    assert any(p["duplicate_of"] for p in papers.values()) and any(p["missing"] for p in papers.values())
    paper = ev.get(f"/api/ev/corpora/{MIXED}/papers/S001").json()
    text = read_text(ev_world.corpora / MIXED / "papers" / "S001.md")
    assert paper["text"] == text and "".join(s["text"] for s in paper["segments"]) == text
    for p in paper["placements"]:
        assert text[p["start"]:p["end"]] == p["exact"]
        assert any(p["fact"] in s["marks"] for s in paper["segments"] if s["start"] >= p["start"] and s["end"] <= p["end"])
    assert paper["study"]["study_id"] == "S001" and paper["fidelity"]["ok"] is True
    assert ev.get(f"/api/ev/corpora/{MIXED}/papers/S999").status_code == 404


# --- protocols and proposals ----------------------------------------------------------------------------

def test_protocols_from_the_repo(ev: TestClient) -> None:
    entries = {p["name"]: p for p in ev.get("/api/ev/protocols").json()}
    assert entries["rag-factuality"]["version"] == 2 and entries["rag-factuality"]["revision"] is None
    view = ev.get("/api/ev/protocols/rag-factuality").json()
    protocol = view["protocol"]
    assert view["phases"] == ["condition", "metric", "measurement", "author_claim"] and view["yaml"].startswith("#")
    assert protocol["synthesis"]["compare"] == {"treatment": "rag", "control": "baseline"}
    assert [m["canonical"] for m in protocol["synthesis"]["metrics"]] == ["factual_accuracy", "hallucination_rate"]
    assert protocol["synthesis"]["label"][-1] == {"when": {}, "then": "insufficient"}
    assert protocol["screen"]["on_fail"] == "skip"
    assert [e["name"] for e in protocol["evidence_types"]["condition"]["extractors"]] == ["regex_condition", "llm_condition"]
    assert ev.get("/api/ev/protocols/nope").status_code == 404


def test_proposal_cards_decisions_amendments(ev: TestClient) -> None:
    (summary,) = ev.get("/api/ev/proposals").json()
    assert summary["name"] == "rag-factuality" and summary["frozen"] and summary["revision"] == 2
    assert summary["steps"] == ["frame", "draft", "critic", "cards", "freeze"] and summary["amendments"] == 1
    assert summary["decided_by"]["aditya"] == ["min_effect"]
    detail = ev.get("/api/ev/proposals/rag-factuality").json()
    cards = {c["id"]: c for c in detail["cards"]}
    assert len(cards) == 8 and cards["min_effect"]["decision"]["by"] == "aditya"
    assert cards["min_effect"]["decision"]["default"] == "draft" and cards["min_effect"]["decision"]["choice"] != "draft"
    assert cards["screen"]["decision"]["by"] == "model" and cards["screen"]["decision"]["reason"].startswith("default: ")
    assert detail["frame"]["treatment"]["source"] == "ontology" and detail["sources"]["fields"]
    assert any(c["kind"] == "deterministic" for c in detail["checks"])
    assert detail["revisions"] == [1, 2] and detail["protocol"]["protocol"]["revision"] == 2
    assert detail["proposal"]["decided_by"] and not {"frame", "sources", "critic"} & set(detail["proposal"])
    (amendment,) = detail["amendment_log"]
    assert amendment["impact"] == ["synthesis.flags.large_effect.factor"] and amendment["before_main_run"] is True
    assert detail["protocol"]["sha256"] == amendment["sha256"] == summary["protocol_sha256"]


# --- runs ----------------------------------------------------------------------------------------------

def test_runs_list_engine_and_baselines(ev: TestClient, ev_world: EvidenceWorld) -> None:
    runs = {r["id"]: r for r in ev.get("/api/ev/runs").json()}
    groups = {"regex-only", "cascade", "cascade-gaps", "rag-baseline"} | ({"agentic-gaps", "agent-baseline"} if ev_world.agent else set())
    assert {r["group"] for r in runs.values()} == groups
    gaps = runs[f"cascade-gaps~{MIXED}"]
    assert (gaps["kind"], gaps["strategy"], gaps["selection"], gaps["corpus"]) == ("engine", "gaps", "cascade", MIXED)
    assert gaps["label"] and gaps["counts"] is not None and gaps["cost"]["calls"] > 0
    rag = runs[f"rag-baseline~{MIXED}"]
    assert (rag["kind"], rag["system"], rag["strategy"], rag["corpus"]) == ("baseline", "rag-baseline", "global", MIXED)


def test_run_detail_answer_funnel_links(ev: TestClient) -> None:
    run = ev.get(f"/api/ev/runs/cascade-gaps~{MIXED}").json()
    assert run["answer"]["system"] == "evidence-engine" and len(run["answer"]["studies"]) == len(run["documents"])
    assert set(run["funnel"]) == set(run["documents"])
    first = run["funnel"][run["documents"][0]]
    assert first["screen"]["relevant"] in (True, False) and first["steps"][0]["position"] == 0
    assert f"rag-baseline~{MIXED}" in run["baselines"] and run["reports"] == [f"cascade-gaps~{MIXED}"]
    assert {e["kind"] for e in run["extractors"]} == {"regex", "llm"}
    assert ev.get("/api/ev/runs/cascade-gaps").status_code == 404
    assert ev.get("/api/ev/runs/..~x").status_code == 404


def test_run_paper_spans_and_calls(ev: TestClient, ev_world: EvidenceWorld) -> None:
    paper = ev.get(f"/api/ev/runs/cascade~{EXPLICIT}/papers/S001").json()
    text = read_text(ev_world.corpora / EXPLICIT / "papers" / "S001.md")
    assert paper["text"] == text and "".join(s["text"] for s in paper["segments"]) == text
    assert paper["items"], "the regex finds something in an explicit paper"
    for item in paper["items"]:
        assert item["found_by"]
        for span in item["spans"]:
            sel = span["selector"]
            assert text[sel["start"]:sel["end"]] == sel["exact"]
            covered = [s for s in paper["segments"] if sel["start"] <= s["start"] and s["end"] <= sel["end"]]
            assert covered and all(item["item_id"] in s["marks"] for s in covered)
    calls = paper["calls"]
    assert {c["evidence_type"] for c in calls} >= {"screen", "condition", "metric", "measurement", "author_claim"}
    assert all(c["document"] == "S001" for c in calls) and {c["kind"] for c in calls} == {"regex", "llm"}
    assert paper["study"]["document"] == "S001" and paper["funnel"]["steps"]


def test_run_graph_and_protocol(ev: TestClient) -> None:
    graph = ev.get(f"/api/ev/runs/cascade~{EXPLICIT}/graph").json()
    kinds = {n["type"] for n in graph["nodes"]}
    assert "document" in kinds and "condition" in kinds
    assert {e["rel"] for e in graph["edges"]} >= {"in_document"}
    protocol = ev.get(f"/api/ev/runs/cascade~{EXPLICIT}/protocol").json()
    assert protocol["source"] == "run" and protocol["protocol"]["id"] == "rag-factuality"
    assert ev.get(f"/api/ev/runs/rag-baseline~{MIXED}/protocol").status_code == 404


def test_llm_call_with_its_model_records(ev: TestClient) -> None:
    paper = ev.get(f"/api/ev/runs/cascade~{EXPLICIT}/papers/S001").json()
    llm = next(c for c in paper["calls"] if c["kind"] == "llm" and c["evidence_type"] == "condition")
    detail = ev.get(f"/api/ev/runs/cascade~{EXPLICIT}/calls/{llm['call_id']}").json()
    assert detail["cached"] and detail["task"]["evidence_type"] == "condition"
    assert detail["result"]["extractor_id"] == llm["extractor_id"] and detail["spec"]["kind"] == "llm"
    (record,) = detail["model_calls"]
    assert record["request"]["user_prompt"] and record["response"]["output"] == {"items": []}
    assert record["agent_run"] is None and detail["agent_runs"] == [] and "messages" not in record
    regex = next(c for c in paper["calls"] if c["kind"] == "regex")
    assert ev.get(f"/api/ev/runs/cascade~{EXPLICIT}/calls/{regex['call_id']}").json()["model_calls"] == []
    assert ev.get(f"/api/ev/runs/cascade~{EXPLICIT}/calls/t999999").status_code == 404
    assert ev.get(f"/api/ev/runs/rag-baseline~{MIXED}/calls/t000001").status_code == 404


def test_baseline_run_detail_and_paper_citations(ev: TestClient) -> None:
    run = ev.get(f"/api/ev/runs/rag-baseline~{MIXED}").json()
    answer = run["answer"]
    assert answer["system"] == "rag-baseline" and answer["citations"] and answer["retrieved"]
    cited = answer["citations"][0]
    paper = ev.get(f"/api/ev/runs/rag-baseline~{MIXED}/papers/{cited['document']}").json()
    assert any(f"cited:{cited['start']}-{cited['end']}" in s["marks"] for s in paper["segments"])
    assert paper["items"] == [] and paper["calls"] == []


@pytest.mark.skipif(not POSIX, reason="the agentic run and the agent baseline need bash (evidence_world.py)")
def test_agentic_call_drills_down_to_the_agent_trace(ev: TestClient, ev_world: EvidenceWorld) -> None:
    run = ev.get(f"/api/ev/runs/agentic-gaps~{MIXED}").json()
    assert "agent" in {e["kind"] for e in run["extractors"]}
    calls = [c for d in run["documents"] for c in ev.get(f"/api/ev/runs/agentic-gaps~{MIXED}/papers/{d}").json()["calls"]
             if c["kind"] == "agent"]
    assert calls and all(c["focus"] for c in calls)   # gaps: the agent gets targeted tasks only
    detail = ev.get(f"/api/ev/runs/agentic-gaps~{MIXED}/calls/{calls[0]['call_id']}").json()
    (agent_run,) = detail["agent_runs"]
    assert any(m["agent_run"] == agent_run for m in detail["model_calls"])
    trace = ev.get(f"/api/ev/runs/agentic-gaps~{MIXED}/calls/{calls[0]['call_id']}/trace/{agent_run}").json()
    assert trace["source"] == "run_dir" and trace["run_id"] == agent_run
    assert any(s["command"] for s in trace["steps"]) and trace["claims"][0]["status"] == "rejected"
    assert trace["claims"][0]["reason"] == "not_found"
    # without the agent work directory the cache's record of the run is the trace
    with TestClient(create_app(settings_for(ev_world, EV_AGENT_WORK=ev_world.root / "elsewhere"))) as c:
        kept = c.get(f"/api/ev/runs/agentic-gaps~{MIXED}/calls/{calls[0]['call_id']}/trace/{agent_run}").json()
    assert kept["source"] == "cache" and [s["command"] for s in kept["steps"] if s["command"]] == \
        [s["command"] for s in trace["steps"] if s["command"]]
    assert ev.get(f"/api/ev/runs/agentic-gaps~{MIXED}/calls/{calls[0]['call_id']}/trace/agentic-0").status_code == 404


@pytest.mark.skipif(not POSIX, reason="the agent baseline needs bash (evidence_world.py)")
def test_agent_baseline_trace(ev: TestClient) -> None:
    run = ev.get(f"/api/ev/runs/agent-baseline~{MIXED}").json()
    assert run["has_trace"] and run["answer"]["agent"]["exit_status"] == "submitted"
    trace = ev.get(f"/api/ev/runs/agent-baseline~{MIXED}/trace").json()
    assert trace["source"] == "run_dir" and trace["answer"]["rows"]
    assert [c["status"] for c in trace["claims"]] == ["accepted"] and trace["claims"][0]["paper_id"] == "S001"
    assert ev.get(f"/api/ev/runs/rag-baseline~{MIXED}/trace").status_code == 404


# --- scores --------------------------------------------------------------------------------------------

def test_scores_index(ev: TestClient, ev_world: EvidenceWorld) -> None:
    index = ev.get("/api/ev/scores").json()
    reports = {r["id"]: r for r in index["reports"]}
    gaps = reports[f"cascade-gaps~{MIXED}"]
    assert gaps["strategy"] == "gaps" and gaps["run_id"] == MIXED and "rag-baseline" in gaps["systems"]
    assert {c["id"] for c in index["compares"]} >= {"compare-cascade", f"compare-funnel~{MIXED}"}
    assert {s["group"] for s in index["shifts"]} == {"shift-regex-only", "shift-cascade", "shift-cascade-gaps"}
    (bench,) = index["benchmarks"]
    assert bench["id"] == "benchmark-tpl" and any(s.startswith("regex_condition@") for s in bench["systems"])


def test_report_compare_shift_benchmark(ev: TestClient, ev_world: EvidenceWorld) -> None:
    view = ev.get(f"/api/ev/scores/reports/cascade-gaps~{MIXED}").json()
    report = view["report"]
    assert report["corpus_id"] and {s["system"] for s in report["synthesis"]} >= {"evidence-engine", "rag-baseline"}
    assert report["extraction"]["rows"] and report["intervals"]["synthesis"] and report["funnel"]["strategy"] == "gaps"
    assert view["markdown"].startswith("# Evaluation of run")
    compare = ev.get(f"/api/ev/scores/compares/compare-funnel~{MIXED}").json()
    assert {r.get("strategy") for r in compare["rows"]} >= {"all", "gaps"} and compare["intervals"]
    shift = ev.get(f"/api/ev/scores/shifts/shift-cascade~{variant_name(ev_world)}").json()
    assert shift["shift"]["from"] == "supports" and shift["shift"]["to"] == "contradicts" and shift["shift"]["systems"]
    bench = ev.get("/api/ev/scores/benchmarks/benchmark-tpl").json()
    assert {r["name"] for r in bench["records"]} >= {"regex_condition", "llm_condition"}
    assert bench["markdown"]
    for bad in ("/api/ev/scores/reports/nope~x", "/api/ev/scores/reports/a~b~c", "/api/ev/scores/compares/cascade",
                "/api/ev/scores/reports/..~cascade", "/api/ev/scores/reports/%2e%2e", "/api/ev/scores/benchmarks/cascade"):
        assert ev.get(bad).status_code == 404, bad


# --- pieces --------------------------------------------------------------------------------------------

def test_segments_cut_at_every_boundary() -> None:
    cut = segments("abcdef", [(1, 3, "x", "value"), (2, 5, "y", "claim"), (9, 12, "z", "value"), (4, 4, "e", "r")])
    assert [(s.text, s.marks) for s in cut] == [("a", []), ("b", ["x"]), ("c", ["x", "y"]), ("de", ["y"]), ("f", [])]
    assert segments("", []) == [] or [s.text for s in segments("", [])] == []


def test_record_cache_reads_the_last_line_of_a_key(tmp_path: Path) -> None:
    path = tmp_path / "c.jsonl"
    rows = [{"key": "a", "value": 1}, {"key": "b", "value": {"x": [1, 2]}}, {"key": "a", "value": 3}]
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows) + '{"key": "c", "val', encoding="utf-8")
    cache = RecordCache()
    assert (cache.get(path, "a"), cache.get(path, "b"), cache.get(path, "c"), cache.get(path, "d")) == (3, {"x": [1, 2]}, None, None)
    with path.open("a", encoding="utf-8") as fh:   # a changed file is scanned again
        fh.write('\n{"key": "d", "value": 4}\n')
    assert cache.get(path, "d") == 4
