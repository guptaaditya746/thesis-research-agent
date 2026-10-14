"""The read endpoints of the API on the fixture world (webapp/tests/world.py)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.anchor import read_text
from agent.tests.runs import SPIDER_BIRD
from webapp.app import create_app

from .test_stream import events
from .world import KEY_DRAFT, OUTPUT, SCORE, World


def test_health_and_config(client: TestClient, world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/api/health").json()["ok"] is True
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    config = client.get("/api/config").json()
    assert config["llm_key_set"] is False
    assert (config["runs_root"], config["corpus"]) == (str(world.runs), str(world.corpus))
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-secret-value")
    response = client.get("/api/config")
    assert response.json()["llm_key_set"] is True and "sk-secret-value" not in response.text


def test_questions(client: TestClient) -> None:
    q01, q02 = client.get("/api/questions").json()
    assert q01["id"] == "q01" and q01["category"] == "corpus_wide"
    assert q01["concept"] == {"status": "picked", "title": "Benchmarks used by RAG papers", "picked_by": "user"}
    assert q01["runs"] == {"claim_on": 1, "claim_off": 1}  # both fixture runs use q01's picked concept
    assert q01["gold"] == {"status": "none", "rows": None, "facts": None, "stage": None}
    assert q02["concept"]["status"] == "none" and q02["runs"] == {"claim_on": 0, "claim_off": 0}
    assert q02["gold"] == {"status": "draft", "rows": 1, "facts": 1, "stage": None}


def test_question_detail(client: TestClient) -> None:
    q = client.get("/api/questions/q01").json()
    assert [b["id"] for b in q["briefs"]] == ["c1", "c2"]
    assert q["briefs"][0]["answer_shape"]["kind"] == "graph" and q["briefs"][1]["answer_shape"]["kind"] == "table"
    assert q["picked"]["choice"] == 1 and q["picked"]["picked_by"] == "user"
    assert q["concept_brief"]["title"] == "Benchmarks used by RAG papers"
    assert client.get("/api/questions/q02").json()["briefs"] == []
    assert client.get("/api/questions/q99").status_code == 404


def test_runs_list_and_filters(client: TestClient) -> None:
    runs = {r["run_id"]: r for r in client.get("/api/runs").json()}
    assert set(runs) == {"baseline-r1", "research-r1"}
    r = runs["research-r1"]
    assert (r["qid"], r["condition"], r["seed"], r["exit_status"], r["live"]) == ("q01", "claim_on", 1234, "submitted", False)
    assert (r["batch"], r["concept_current"], r["answer_from"], r["post_processing"]) == (None, True, "final", False)
    assert (r["steps"], r["model_calls"], r["claims_accepted"], r["claims_rejected"]) == (6, 6, 6, 1)
    assert (r["rows"], r["facts"], r["attach"]) == (5, 5, "not_applicable")
    assert r["score"] == {"support_share": 0.6, "fact_f1": 0.889, "row_f1": 0.667,  # soft fact F1
                          "key_version": "v1", "provisional": False}
    b = runs["baseline-r1"]
    assert (b["condition"], b["exit_status"], b["attach"], b["score"]) == ("claim_off", "submitted", "pending", None)
    assert b["tokens_without_attach"] is not None and b["claims_accepted"] == 3
    assert [x["run_id"] for x in client.get("/api/runs", params={"condition": "claim_off"}).json()] == ["baseline-r1"]
    assert len(client.get("/api/runs", params={"qid": "q01"}).json()) == 2
    assert client.get("/api/runs", params={"qid": "q02"}).json() == []
    checked = {x["run_id"]: x["verify"] for x in client.get("/api/runs", params={"verify": True}).json()}
    assert checked == {"baseline-r1": "ok", "research-r1": "ok"}


def test_run_detail(client: TestClient) -> None:
    d = client.get("/api/runs/research-r1").json()
    assert d["summary"]["verify"] == "ok" and d["verify"]["ok"] is True and d["verify"]["errors"] == []
    assert d["verify"]["stats"]["facts_with_claims"] == 4
    assert d["config"]["condition"] == "claim_on" and d["concept"]["title"] == "Benchmarks used by RAG papers"
    assert d["summary"]["sandbox"] == (d["config"].get("sandbox") or {}).get("mode")
    assert [row["id"] for row in d["answer"]["rows"]] == ["r1", "r2", "r3", "r4", "r5"]
    assert d["answer"]["rows"][0]["source"] == "p1" and d["answer"]["rows"][0]["facts"][0]["claims"] == ["claim-000001"]
    assert client.get("/api/runs/nope").status_code == 404


def test_steps(client: TestClient) -> None:
    steps = client.get("/api/runs/research-r1/steps").json()
    assert [(s["agent_id"], s["step"]) for s in steps] == [("main", 1), ("main", 2), ("main", 3), ("sub-01", 4),
                                                          ("main", 5), ("main", 6)]
    one = steps[0]
    assert one["command"].startswith('rg -n "Spider"') and one["origin"] == "research"
    assert one["output_head"] == "\n".join(OUTPUT.splitlines()[:12])
    assert [(c["claim_id"], c["status"]) for c in one["claims"]] == [("claim-000001", "accepted"), ("claim-000002", "accepted")]
    assert steps[2]["spawned"] == ["sub-01"] and steps[2]["command"] is None
    assert [c["claim_id"] for c in steps[3]["claims"]] == ["claim-000005", "claim-000006"]
    assert steps[4]["claims"] == [{"claim_id": None, "status": "rejected", "reason": "not_found", "s": "p3",
                                   "p": "evaluatesOn", "o": "HellaSwag"}]
    assert steps[5]["model_call"]["final_answer"] is True and steps[5]["model_call"]["task_id"].startswith("t")
    attach = client.get("/api/runs/baseline-r1/steps").json()[4:]
    assert [(s["step"], s["origin"], s["fact_id"]) for s in attach] == [
        (5, "attach", "f1"), (6, "attach", "f2"), (7, "attach", "f3"), (8, "attach", "f4")]
    assert attach[3]["claims"] == []


def test_step_output(client: TestClient) -> None:
    response = client.get("/api/runs/research-r1/steps/1/output")
    assert response.status_code == 200 and response.text == OUTPUT
    assert response.headers["content-type"].startswith("text/plain")
    assert client.get("/api/runs/research-r1/steps/1/output", params={"agent_id": "sub-01"}).status_code == 404
    assert client.get("/api/runs/research-r1/steps/2/output").status_code == 404  # no output file written
    assert client.get("/api/runs/research-r1/steps/6/output").status_code == 404  # no command at step 6


def test_claims(client: TestClient, world: World) -> None:
    claims = client.get("/api/runs/research-r1/claims").json()
    assert len(claims) == 7
    first = claims[0]
    assert (first["claim_id"], first["status"], first["file"], first["paper_id"], first["step"]) == \
        ("claim-000001", "accepted", "p1.md", "p1", 1)
    text = read_text(world.corpus / "p1.md")
    assert text[first["anchor"]["start"]:first["anchor"]["end"]] == first["quote"] == SPIDER_BIRD.text
    rejected = [c for c in claims if c["status"] == "rejected"]
    assert [(c["reason"], c["paper_id"], c["anchor"]) for c in rejected] == [("not_found", "p3", None)]
    assert rejected[0]["quote"] == "we evaluate on HellaSwag with exact match"
    sub = [c for c in claims if c["agent_id"] == "sub-01"]
    assert [c["claim_id"] for c in sub] == ["claim-000005", "claim-000006"]
    attach = client.get("/api/runs/baseline-r1/claims").json()
    assert {c["origin"] for c in attach} == {"attach"}


def test_graph(client: TestClient) -> None:
    graph = client.get("/api/runs/research-r1/graph").json()
    assert [e["id"] for e in graph["edges"]] == [f"edge-{n:06d}" for n in range(1, 7)]
    assert graph["edges"][0]["predicate"]["text"] == "evaluatesOn" and graph["edges"][0]["evidence"]["paper"] == "p1"
    assert {n["id"] for n in graph["nodes"]} >= {"paper:p1", "entity:spider"}
    assert graph["schema_version"] == 1  # graph.json as is, fields beyond the model kept
    assert len(client.get("/api/runs/baseline-r1/graph").json()["edges"]) == 3


def test_graph_of_a_run_without_graph_json(fresh: World) -> None:
    (fresh.research.run.root / "graph.json").unlink()
    with TestClient(create_app(fresh.settings)) as c:
        assert len(c.get("/api/runs/research-r1/graph").json()["edges"]) == 6  # built in memory
        assert not (fresh.research.run.root / "graph.json").exists()
    with TestClient(create_app(fresh.with_settings(corpus=None))) as c:
        assert c.get("/api/runs/research-r1/graph").status_code == 404


def test_walk(client: TestClient, world: World) -> None:
    walk = client.get("/api/runs/research-r1/facts/f1/walk").json()  # no judge by default: no model call
    assert (walk["fact"]["id"], walk["row_id"], walk["support"], walk["label"]) == ("f1", "r1", None, None)
    [item] = walk["claims"]
    assert item["claim_id"] == "claim-000001" and item["anchor_status"] == "ok"
    assert item["step"]["step"] == 1 and item["step"]["command"].startswith('rg -n "Spider"')
    passage = item["passage"]
    lo, hi = passage["highlight"]["start"], passage["highlight"]["end"]
    assert passage["text"][lo:hi] == SPIDER_BIRD.text and passage["paper_id"] == "p1"
    text = read_text(world.corpus / "p1.md")
    assert text[passage["offset"]:passage["offset"] + len(passage["text"])] == passage["text"]
    sub = client.get("/api/runs/research-r1/facts/f4/walk").json()
    assert sub["claims"][0]["step"]["agent_id"] == "sub-01"
    unsourced = client.get("/api/runs/research-r1/facts/f5/walk").json()
    assert (unsourced["claims"], unsourced["label"]) == ([], "unsourced")
    assert client.get("/api/runs/research-r1/facts/f9/walk").status_code == 404


def scored(label: str, claims: list[tuple[str, str | None]]) -> dict:
    """score.json's detail.support entry of fact f1 (scoring/support.py writes it)."""
    return {"row_id": "r1", "fact_id": "f1", "origin": "research", "label": label,
            "claims": [{"claim_id": c, "file": "p1.md", "label": lab, "rationale": "scored" if lab else None,
                        "model": "Qwen3-30B-A3B" if lab else None} for c, lab in claims]}


def test_walk_shows_the_verdicts_scoring_counted(fresh: World) -> None:
    asked = []

    def judge(fact, quote, *, context=None):
        asked.append((fact, quote, context))
        return {"label": "no", "rationale": "live", "model": "m", "prompt_sha256": "a" * 64, "cached": False}

    score = fresh.research.run.root / "score.json"
    with TestClient(create_app(fresh.settings, judge=judge)) as c:
        score.write_text(json.dumps(SCORE | {"detail": {"support": [scored("supports", [("claim-000001", "supports")])]}}),
                         encoding="utf-8")
        for params in ({}, {"judge": True}):  # a scored verdict is never asked again
            walk = c.get("/api/runs/research-r1/facts/f1/walk", params=params).json()
            assert (walk["label"], walk["support"]["label"], walk["support"]["source"]) == ("supports", "supports", "score")
            assert walk["claims"][0]["support"] == {"label": "supports", "rationale": "scored", "model": "Qwen3-30B-A3B",
                                                    "prompt_sha256": None, "cached": None, "source": "score"}
        assert asked == []
        # Scored while the judge was unreachable: pending, and only asked when the request says so.
        score.write_text(json.dumps(SCORE | {"detail": {"support": [scored("pending", [("claim-000001", None)])]}}),
                         encoding="utf-8")
        walk = c.get("/api/runs/research-r1/facts/f1/walk").json()
        assert (walk["label"], walk["support"], walk["claims"][0]["support"]) == ("pending", None, None)
        walk = c.get("/api/runs/research-r1/facts/f1/walk", params={"judge": True}).json()
        assert (walk["label"], walk["support"]["source"], walk["support"]["rationale"]) == ("no", "judge", "live")
    assert [a[:2] for a in asked] == [({"s": "p1", "p": "evaluatesOn", "o": "Spider"}, SPIDER_BIRD.text)]


def test_walk_asks_the_judge_with_scorings_context(fresh: World) -> None:
    """Unscored runs: the judge is asked live, per quote, with the calibrated context scoring's
    support_pair gives it (gold.judge.context_for), so the verdict and its cache line are scoring's."""
    from gold import judge as gold_judge
    from gold import review

    asked = []

    async def judge(fact, quote, *, context=None):
        asked.append(context)
        return {"label": "supports", "rationale": "names it", "model": "m", "prompt_sha256": "b" * 64, "cached": True}

    with TestClient(create_app(fresh.settings, judge=judge)) as c:
        walk = c.get("/api/runs/baseline-r1/facts/f1/walk", params={"judge": True}).json()
    assert (walk["label"], walk["support"]["source"], walk["claims"][0]["support"]["cached"]) == ("supports", "judge", True)
    claim = walk["claims"][0]["claim"]
    expected = gold_judge.context_for(review.Corpus(fresh.settings.corpus), claim["file"],
                                      claim["anchor"]["start"], claim["anchor"]["end"])
    assert asked == [expected] and expected.startswith(f"Paper {Path(claim['file']).stem} (")


def test_no_judge_context_without_corpus_anchor_or_the_frozen_file(fresh: World) -> None:
    """Without the quote's context the judge is not asked (scoring leaves such a quote pending)."""
    from webapp import judge as walk_judge
    from webapp.models import Anchor

    span = Anchor(start=0, end=10)
    assert isinstance(walk_judge.calibrated_context("p1.md", span, fresh.corpus), str)
    assert walk_judge.calibrated_context("p1.md", None, fresh.corpus) is walk_judge.NO_CONTEXT
    assert walk_judge.calibrated_context("p1.md", span, None) is walk_judge.NO_CONTEXT
    assert walk_judge.calibrated_context("p77.md", span, fresh.corpus) is walk_judge.NO_CONTEXT
    (fresh.corpus / "p2.md").write_text("another text", encoding="utf-8")  # no longer the frozen file
    assert walk_judge.calibrated_context("p2.md", span, fresh.corpus) is walk_judge.NO_CONTEXT


def test_the_default_judge_is_found_through_sys_modules(fresh: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """gold.judge as importlib finds it (a test's stand-in in sys.modules), never a `gold.judge`
    attribute another test's import left on the package; and a judge that fails leaves no verdict."""
    import gold

    def real(*args, **kwargs):
        raise AssertionError("the real judge was called")

    def broken(fact, quote, *, context=None):
        raise ConnectionError("no model")

    monkeypatch.setattr(gold, "judge", types.SimpleNamespace(support=real), raising=False)
    monkeypatch.setitem(sys.modules, "gold.judge", types.SimpleNamespace(support=broken))
    with TestClient(create_app(fresh.settings)) as c:
        walk = c.get("/api/runs/research-r1/facts/f1/walk", params={"judge": True}).json()
    assert (walk["support"], walk["label"]) == (None, "pending") and walk["claims"][0]["passage"] is not None


def test_score(client: TestClient) -> None:
    score = client.get("/api/runs/research-r1/score").json()
    assert score["support"]["support_share"] == 0.6 and score["verify_ok"] is True  # extra fields kept
    assert score["facts"]["soft"]["f1"] == SCORE["facts"]["soft"]["f1"]
    assert client.get("/api/runs/baseline-r1/score").status_code == 404


def test_highlight_in_utf16_units(tmp_path: Path) -> None:
    """Characters outside the BMP before a quote: JavaScript slices with highlight_utf16."""
    from agent.canonical import sha256_hex
    from webapp.corpus import Corpus

    text = "# Paper\n\nWe set \U0001d465 = 3 and \U0001d703 = 0.5. The model reaches 91.2 F1 on Spider.\n"
    (tmp_path / "x1.md").write_text(text, encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({"papers": [
        {"id": "x1", "markdown_sha256": sha256_hex(text.encode("utf-8")), "failure": None}]}), encoding="utf-8")
    quote = "91.2 F1 on Spider"
    start = text.index(quote)
    p = Corpus(tmp_path).passage("x1", start, start + len(quote), 60)  # the window holds both letters
    assert p.text[p.highlight.start:p.highlight.end] == quote
    units = p.text.encode("utf-16-le")
    lo, hi = p.highlight_utf16.start, p.highlight_utf16.end
    assert units[2 * lo:2 * hi].decode("utf-16-le") == quote and (lo, hi) == (p.highlight.start + 2, p.highlight.end + 2)


def test_corpus_passage(client: TestClient, world: World) -> None:
    text = read_text(world.corpus / "p1.md")
    start = text.index(SPIDER_BIRD.text)
    end = start + len(SPIDER_BIRD.text)
    p = client.get("/api/corpus/p1", params={"start": start, "end": end, "context": 100}).json()
    assert p["text"][p["highlight"]["start"]:p["highlight"]["end"]] == SPIDER_BIRD.text
    assert p["offset"] == start - 100 and len(p["text"]) == len(SPIDER_BIRD.text) + 200 and p["length"] == len(text)
    first_heading = next(line for line in text.splitlines() if line.startswith("#"))
    assert p["title"] == first_heading.lstrip("#").strip()
    head = client.get("/api/corpus/p1.md", params={"context": 50}).json()
    assert (head["offset"], head["highlight"], head["text"]) == (0, None, text[:100])
    assert client.get("/api/corpus/p1", params={"start": 10, "end": 5}).status_code == 400
    assert client.get("/api/corpus/p1", params={"start": 0, "end": len(text) + 1}).status_code == 400
    assert client.get("/api/corpus/p1", params={"start": -1, "end": 5}).status_code == 422
    assert client.get("/api/corpus/p99").status_code == 404  # failed conversion: no text
    assert client.get("/api/corpus/nope").status_code == 404


def test_gold(client: TestClient) -> None:
    gold = {g["qid"]: g for g in client.get("/api/gold").json()}
    assert gold["q01"]["status"] == "none" and gold["q01"]["key_version"] is None
    q02 = gold["q02"]
    assert (q02["status"], q02["key_version"], q02["rows"], q02["facts"]) == ("draft", "v1-draft", 1, 1)
    assert q02["coverage"] == {"papers": 10, "relevant": 4} and q02["counts"] == {"candidates": 7}
    key = client.get("/api/gold/q02/key").json()
    assert key["version"] == "v1-draft" and key["rows"] == KEY_DRAFT["rows"]
    assert client.get("/api/gold/q01/key").status_code == 404


def test_gold_lists_question_directories_only(fresh: World) -> None:
    gold = fresh.root / "gold-data"
    for name, file in (("_calibration", "notes.txt"), ("judge", "sample.jsonl"), ("q07", "progress.json")):
        (gold / name).mkdir()
        (gold / name / file).write_text('{"stage": "failed"}', encoding="utf-8")
    (gold / "judge-cache.jsonl").write_text("", encoding="utf-8")
    with TestClient(create_app(fresh.settings)) as c:
        response = c.get("/api/gold")
    assert response.status_code == 200
    entries = {g["qid"]: g for g in response.json()}
    assert list(entries) == ["q01", "q02", "q07"]  # C2's judge/ sample and other directories are not questions
    assert (entries["q07"]["status"], entries["q07"]["stage"]) == ("building", "failed")  # stopped, not running


def test_gold_of_an_unfinished_review_is_reviewing(fresh: World) -> None:
    """key.json from an export half way through the review (review.complete false) is not `reviewed`."""
    folder = fresh.root / "gold-data" / "q02"
    key = {**KEY_DRAFT, "version": "v1", "reviewed": True, "review": {"complete": False, "unreviewed": 3}}
    (folder / "key.json").write_text(json.dumps(key), encoding="utf-8")
    with TestClient(create_app(fresh.settings)) as c:
        assert {g["qid"]: g["status"] for g in c.get("/api/gold").json()}["q02"] == "reviewing"
        assert next(q for q in c.get("/api/questions").json() if q["id"] == "q02")["gold"]["status"] == "reviewing"
        (folder / "key.json").write_text(json.dumps(key | {"review": {"complete": True}}), encoding="utf-8")
        assert {g["qid"]: g["status"] for g in c.get("/api/gold").json()}["q02"] == "reviewed"


def test_runs_list_shows_the_scorers_verify(fresh: World) -> None:
    """The list computes no `agent verify`; a run scored after its last record shows the scorer's verify_ok
    (`verify_from: score`), one changed since shows unknown until it is verified again."""
    score_file = fresh.research.run.root / "score.json"
    score_file.write_text(json.dumps(json.loads(score_file.read_text(encoding="utf-8")) | {"verify_ok": False}),
                          encoding="utf-8")
    newest = max(p.stat().st_mtime for p in (fresh.research.run.events, fresh.research.run.answer))
    os.utime(score_file, (newest + 10, newest + 10))
    with TestClient(create_app(fresh.settings)) as c:
        runs = {r["run_id"]: r for r in c.get("/api/runs").json()}
        assert (runs["research-r1"]["verify"], runs["research-r1"]["verify_from"]) == ("failed", "score")
        assert (runs["baseline-r1"]["verify"], runs["baseline-r1"]["verify_from"]) == ("unknown", None)  # no score
        os.utime(fresh.research.run.events, (newest + 20, newest + 20))  # the run changed after scoring
        assert {r["run_id"]: r["verify"] for r in c.get("/api/runs").json()}["research-r1"] == "unknown"
        checked = {r["run_id"]: (r["verify"], r["verify_from"]) for r in c.get("/api/runs", params={"verify": True}).json()}
        assert checked["research-r1"] == ("ok", "verify")  # the app's own check wins


def test_results(client: TestClient, fresh: World) -> None:
    assert client.get("/api/results").json() == {"primary": {"p_value": 0.03}}
    (fresh.runs / "report" / "report.json").unlink()
    with TestClient(create_app(fresh.settings)) as c:
        assert c.get("/api/results").status_code == 404
        for n, (batch, p) in enumerate((("e2e-smoke", 0.5), ("m4-72", 0.01))):  # `score report` on each batch root
            report = fresh.runs / batch / "report" / "report.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({"p": p}), encoding="utf-8")
            os.utime(report, (1_800_000_000 + n, 1_800_000_000 + n))
        assert c.get("/api/results").json() == {"p": 0.01}  # the newest
        assert c.get("/api/results", params={"batch": "e2e-smoke"}).json() == {"p": 0.5}
        assert c.get("/api/results", params={"batch": "nope"}).status_code == 404
        assert c.get("/api/results", params={"batch": ".."}).status_code == 404


def test_runs_of_batch_roots(fresh: World) -> None:
    """$RUNS/<manifest name>/<key>-aN, as the batch runner writes them; two batches share run names."""
    for batch in ("e2e-smoke", "m4-72"):
        shutil.copytree(fresh.research.run.root, fresh.runs / batch / "q01-claim_on-r1-a1")
    (fresh.runs / "m4-72" / "manifest.json").write_text("{}", encoding="utf-8")
    query = "PREFIX ours: <urn:thesis-agent:vocab#>\nSELECT (COUNT(?c) AS ?n) WHERE { ?c a ours:Claim }"
    with TestClient(create_app(fresh.settings)) as c:
        runs = {r["run_id"]: r for r in c.get("/api/runs").json()}
        assert list(runs) == ["baseline-r1", "research-r1", "e2e-smoke~q01-claim_on-r1-a1", "m4-72~q01-claim_on-r1-a1"]
        m4 = runs["m4-72~q01-claim_on-r1-a1"]
        assert (m4["batch"], m4["qid"], m4["concept_current"], m4["exit_status"]) == ("m4-72", "q01", True, "submitted")
        assert c.get("/api/questions").json()[0]["runs"] == {"claim_on": 3, "claim_off": 1}
        assert len(c.get("/api/runs/m4-72~q01-claim_on-r1-a1/steps").json()) == 6
        assert c.get("/api/runs/m4-72~q01-claim_on-r1-a1/facts/f1/walk").json()["run_id"] == "m4-72~q01-claim_on-r1-a1"
        with c.stream("GET", "/api/runs/m4-72~q01-claim_on-r1-a1/stream") as response:
            done = [e for e in events(response) if e.get("event") == "done"]
        assert json.loads(done[0]["data"])["run_id"] == "m4-72~q01-claim_on-r1-a1"
        assert c.get("/api/queries/1", params={"run_id": "m4-72~q01-claim_on-r1-a1"}).json()["rows"]
        one = c.post("/api/sparql", json={"query": query, "run_id": "e2e-smoke~q01-claim_on-r1-a1"})
        assert int(one.json()["rows"][0]["n"]) == 6
        # One graph per directory name in the store: the first batch's run holds it.
        assert c.post("/api/sparql", json={"query": query, "run_id": "m4-72~q01-claim_on-r1-a1"}).status_code == 409
        for bad in ("m4-72~nope", "m4-72~q01-claim_on-r1-a1~x", "nope~q01-claim_on-r1-a1"):
            assert c.get(f"/api/runs/{bad}").status_code == 404, bad


def test_nothing_there_yet(tmp_path: Path) -> None:
    """A server started before any run, concept or gold exists answers with empty lists, not errors."""
    from webapp.settings import Settings

    settings = Settings(runs=tmp_path / "runs", gold=tmp_path / "gold", concepts=tmp_path / "concepts",
                        questions=tmp_path / "questions.json", corpus=None, WEBAPP_DIST=tmp_path / "dist")
    with TestClient(create_app(settings)) as c:
        for url in ("/api/questions", "/api/runs", "/api/gold", "/api/jobs"):
            assert c.get(url).json() == [], url
        assert c.get("/api/results").status_code == 404
        assert c.post("/api/sparql", json={"query": "SELECT * WHERE { ?s ?p ?o }"}).json()["rows"] == []


def test_openapi_file_is_current() -> None:
    """webapp/web/openapi.json (the frontend's types come from it) is what `webapp openapi` prints."""
    path = Path(__file__).resolve().parents[1] / "web" / "openapi.json"
    committed, current = json.loads(path.read_text(encoding="utf-8")), create_app().openapi()
    for schema in (committed, current):
        schema["info"].pop("version")  # the package version; a bump alone changes no type
    assert committed == current, "run `uv run webapp openapi -o webapp/web/openapi.json`"
