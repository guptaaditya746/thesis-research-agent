"""gold/triage.py, pool.py and draft.py on a built D: labels, the blind seeded pool, the draft key."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agent.concept import answer_schema_for, concept_sha256
from agent.schema import errors
from gold.build import QuestionDir, build, read_jsonl
from gold.draft import GOLD_ONLY, VERSION, answer_view, draft_key, strip_gold, validate_key
from gold.pool import build_pool, sample_ids
from gold.triage import LABELS, load_labels, triage

from .scripted import GRAPH_RULES, GSM8K_FIXED, SETTINGS, Script, corpus, graph_concept, table_concept


@pytest.fixture
def built(tmp_path):
    c = corpus(tmp_path)
    out = tmp_path / "gold"
    build("q01", table_concept(), c, out, rotation=Script().rotation(), settings=SETTINGS,
          question="Which benchmarks do the RAG papers evaluate on?", log=lambda _: None)
    return {"corpus": c, "out": out, "dir": QuestionDir(out / "q01")}


def run_triage(built, script=None, **kw):
    return triage("q01", built["out"], built["corpus"], (script or Script()).rotation(), settings=SETTINGS,
                  log=lambda _: None, **kw)


# --- triage ------------------------------------------------------------------------------------------

def test_triage_labels_every_candidate_once(built):
    script = Script()
    counts = run_triage(built, script, batch=4)
    # 6 candidates: MMLU x2, GSM8K x2 -> answers; HotpotQA -> context; HellaSwag -> irrelevant
    assert counts == {"answers": 4, "context": 1, "irrelevant": 1, "unsorted": 0}
    assert script.calls["triage"] == 2
    lines = read_jsonl(built["dir"].triage)
    assert {line["label"] for line in lines} <= set(LABELS)
    assert all({"id", "label", "model", "served_model", "prompt_sha256"} <= set(line) for line in lines)
    again = Script(fail=lambda *_: True)
    assert run_triage(built, again)["unsorted"] == 0 and sum(again.calls.values()) == 0


def test_a_failed_triage_batch_is_retried_on_rerun(built):
    failing = Script()
    failing.fail = lambda stage, *_: failing.calls["triage"] == 1
    counts = run_triage(built, failing, batch=3)
    assert counts["unsorted"] == 3
    script = Script()
    assert run_triage(built, script, batch=3)["unsorted"] == 0
    assert script.calls["triage"] == 1


def test_triage_shows_the_passage_around_the_quote(built):
    seen = []
    script = Script()
    original = script.reply

    def spy(stage, prompt):
        seen.append(json.loads(prompt))
        return original(stage, prompt)

    script.reply = spy
    run_triage(built, script, batch=10)
    facts = {f["quote"]: f for f in seen[0]["facts"]}
    assert GSM8K_FIXED in facts[GSM8K_FIXED]["passage"] and len(facts[GSM8K_FIXED]["passage"]) > 300
    assert seen[0]["concept"]["title"] == table_concept()["title"]
    assert seen[0]["question"].startswith("Which benchmarks")


# --- pool --------------------------------------------------------------------------------------------

def test_pool_is_seeded_blind_and_stratified(built):
    run_triage(built)
    strata = build_pool("q01", built["out"], built["corpus"], sample=1, seed=0)
    pool = read_jsonl(built["dir"].pool)
    labels = load_labels(built["dir"])
    assert strata["reviewed_tiers"] == 5 and strata["rest"] == 1 and strata["sampled"] == 1 and len(pool) == 6
    assert {r["id"] for r in pool} == set(strata["strata"]["triaged"]) | set(strata["strata"]["sample"])
    assert all(labels[i] in ("answers", "context") for i in strata["strata"]["triaged"])
    assert all("label" not in r and "stratum" not in r and "triage" not in r for r in pool)
    assert json.loads(built["dir"].strata.read_text(encoding="utf-8")) == strata
    first = built["dir"].pool.read_text(encoding="utf-8")
    build_pool("q01", built["out"], built["corpus"], sample=1, seed=0)
    assert built["dir"].pool.read_text(encoding="utf-8") == first
    build_pool("q01", built["out"], built["corpus"], sample=1, seed=1)
    assert [r["id"] for r in read_jsonl(built["dir"].pool)] != [r["id"] for r in pool]


def test_pool_passages_highlight_the_quote(built):
    run_triage(built)
    build_pool("q01", built["out"], built["corpus"])
    for r in read_jsonl(built["dir"].pool):
        passage = r["passage"]
        if r["anchor_status"] == "ok":
            hl = passage["highlight"]
            assert passage["text"][hl["start"]:hl["end"]] == r["anchor"]["exact"]
        else:
            assert passage["highlight"] is None and len(passage["text"]) > 1000  # the whole chunk


def test_sample_is_deterministic_and_seeded():
    ids = [f"q01-c{n:06d}" for n in range(1, 301)]
    assert sample_ids(ids, 50, "0:q01") == sample_ids(list(reversed(ids)), 50, "0:q01")
    assert sample_ids(ids, 50, "0:q01") != sample_ids(ids, 50, "1:q01")
    assert len(sample_ids(ids, 50, "0:q01")) == 50 and sample_ids(ids[:3], 50, "x") == set(ids[:3])


def test_untriaged_candidates_are_reviewed_in_full(built):
    strata = build_pool("q01", built["out"], built["corpus"], sample=0)
    assert strata["unsorted"] == strata["records"] == 6 and strata["sampled"] == 0


# --- draft -------------------------------------------------------------------------------------------

def test_draft_key_validates_as_an_answer(built):
    run_triage(built)
    key = draft_key("q01", built["out"])
    concept = table_concept()
    assert key["version"] == VERSION == "v1-draft" and key["reviewed"] is False
    assert key["concept_sha256"] == concept_sha256(concept) and key["kind"] == "table"
    assert validate_key(key, concept) == []
    assert errors(answer_schema_for(concept), answer_view(key)) == []
    with_gold = {"concept_sha256": key["concept_sha256"], "kind": "table", "rows": key["rows"]}
    assert errors(answer_schema_for(concept), with_gold)  # the gold-only fields are what must be stripped
    rows = {r["cells"]["dataset"]: r for r in key["rows"]}
    assert set(rows) == {"MMLU", "GSM8K", "HotpotQA"}  # HellaSwag: irrelevant and unanchored
    assert rows["MMLU"]["cells"] == {"dataset": "MMLU", "papers": ["p3", "p5"], "paper_count": 2}
    fact = rows["GSM8K"]["facts"][0]
    assert set(fact) == {"id", "s", "p", "o", "claims", "origin", *GOLD_ONLY}
    assert fact["vital"] is False and fact["paper_id"] == "p5" and fact["quote"] == "math reasoning using GSM8K"
    # 5 kept candidates, but p5 states (p5, evaluates on, GSM8K) twice: one fact, the other listed as merged
    assert [f["id"] for r in key["rows"] for f in r["facts"]] == [f"f{n}" for n in range(1, 5)]
    assert key["merged_facts"] == {fact["id"]: [c["id"] for c in read_jsonl(built["dir"].candidates)
                                                if c["quote"] == GSM8K_FIXED]}
    assert key["counts"]["skipped"]["other_tiers"] == 1 and key["counts"]["kept"] == 5
    assert json.loads(built["dir"].draft.read_text(encoding="utf-8")) == key


def test_draft_needs_triage(built):
    with pytest.raises(ValueError, match="gold triage"):
        draft_key("q01", built["out"])


def test_validate_key_reports_bad_rows(built):
    run_triage(built)
    key = draft_key("q01", built["out"])
    key["rows"][0]["cells"]["paper_count"] = "two"
    del key["rows"][1]["facts"][0]["vital"]
    problems = validate_key(key, table_concept())
    assert any("paper_count" in p for p in problems)
    key["rows"][0]["cells"]["paper_count"] = 2
    assert validate_key(key, table_concept()) == [f"r2/{key['rows'][1]['facts'][0]['id']}: missing ['vital']"]
    assert "vital" not in strip_gold(key["rows"][0])["facts"][0]


def test_graph_draft_merges_identical_edges_and_validates(tmp_path):
    c = corpus(tmp_path)
    out = tmp_path / "gold"
    concept = graph_concept()
    script = Script(rules=list(GRAPH_RULES), labels={"HotpotQA": "answers", "GSM8K": "answers",
                                                     "exact match": "context"})
    build("q02", concept, c, out, rotation=script.rotation(), settings=replace(SETTINGS, only_papers=("p5", "p6")),
          log=lambda _: None)
    triage("q02", out, c, script.rotation(), settings=SETTINGS, log=lambda _: None)
    key = draft_key("q02", out)
    assert validate_key(key, concept) == []
    edges = {(r["source"], r["target"]): r for r in key["rows"]}
    assert set(edges) == {("p5", "GSM8K"), ("p6", "HotpotQA")}
    gsm8k = edges[("p5", "GSM8K")]
    assert gsm8k["attributes"] == {"metric": "exact match"}
    assert [(f["s"], f["p"], f["o"]) for f in gsm8k["facts"]] == [("p5", "evaluatesOn", "GSM8K"),
                                                                    ("GSM8K", "measured with", "exact match")]
    assert len(key["merged_facts"]) == 1  # the second (p5, evaluatesOn, GSM8K) fact
