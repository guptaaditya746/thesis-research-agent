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


def test_a_reply_that_labels_none_of_its_batch_is_not_cached(built):
    wrong = Script()
    original = wrong.reply
    wrong.reply = lambda stage, prompt: ({"labels": [{"id": "q01-c999999", "label": "answers"}]}
                                         if stage == "triage" else original(stage, prompt))
    assert run_triage(built, wrong)["unsorted"] == 6
    good = Script()
    assert run_triage(built, good)["unsorted"] == 0 and good.calls["triage"] == 1  # asked again, not cached


def test_labels_hold_for_their_concept_and_prompt_only(built):
    run_triage(built)
    qdir = built["dir"]
    lines = read_jsonl(qdir.triage)
    assert {line["concept_sha256"] for line in lines} == {concept_sha256(table_concept())}
    assert len(load_labels(qdir)) == 6
    lines[0]["concept_sha256"] = "0" * 64  # judged under another concept
    lines[1]["prompt_sha256"] = "f" * 64   # under another triage prompt
    qdir.triage.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    assert set(load_labels(qdir)) == {line["id"] for line in lines[2:]}
    script = Script()
    assert run_triage(built, script)["unsorted"] == 0 and script.calls["triage"] == 1  # the two sorted again
    runs = json.loads(qdir.triage_runs.read_text(encoding="utf-8"))["runs"]
    assert len(runs) == 2 and runs[1]["to_sort"] == 2
    assert {"batch", "context_chars", "temperature", "seed", "max_tokens", "model_key", "passages",
            "corpus_manifest_sha256", "prompt", "concept_sha256"} <= set(runs[0])
    assert runs[0]["passages"] is True and runs[0]["corpus_manifest_sha256"] == built["corpus"].manifest_sha256


def test_triage_refuses_a_corpus_that_is_not_the_one_d_was_built_from(built):
    from agent.broker import Rejected

    (built["corpus"].root / "p5.md").write_text("changed", encoding="utf-8")
    with pytest.raises(Rejected):
        run_triage(built)


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
    assert strata["partial"] is False and strata["doc"]["papers"] == strata["doc"]["papers_in_corpus"] == 11
    assert strata["passages"] is True and strata["corpus_manifest_sha256"] == built["corpus"].manifest_sha256
    assert strata["concept_sha256"] == concept_sha256(table_concept()) and len(strata["doc"]["sha256"]) == 64


def trial(tmp_path, qid="q01", concept=None, script=None, papers=("p5", "p6")):
    c = corpus(tmp_path)
    out = tmp_path / "gold"
    script = script or Script()
    build(qid, concept or table_concept(), c, out, rotation=script.rotation(),
          settings=replace(SETTINGS, only_papers=papers), log=lambda _: None)
    triage(qid, out, c, script.rotation(), settings=SETTINGS, log=lambda _: None)
    return c, out


def test_pool_and_draft_refuse_a_partial_d_unless_allowed(tmp_path):
    c, out = trial(tmp_path)
    with pytest.raises(ValueError, match="trial over 2 of 11 papers"):
        build_pool("q01", out, c)
    with pytest.raises(ValueError, match="--allow-partial"):
        draft_key("q01", out)
    strata = build_pool("q01", out, c, allow_partial=True)
    assert strata["partial"] is True and strata["doc"]["only_papers"] == ["p5", "p6"]
    key = draft_key("q01", out, allow_partial=True)
    assert key["built"]["partial"] is True and key["built"]["doc"]["papers"] == 2 and "PARTIAL" in key["notes"]


def test_pool_and_draft_refuse_a_d_with_failed_calls(tmp_path):
    down = Script(fail=lambda stage, paper, part: stage == "extract" and paper == "p6")
    c, out = trial(tmp_path, script=down)
    with pytest.raises(ValueError, match="1 extractions"):
        draft_key("q01", out)
    assert "failed calls" in draft_key("q01", out, allow_partial=True)["built"]["partial_reason"]


def test_draft_refuses_untriaged_candidates_unless_allowed(built):
    failing = Script()
    failing.fail = lambda stage, *_: failing.calls["triage"] == 1
    assert run_triage(built, failing, batch=3)["unsorted"] == 3
    with pytest.raises(ValueError, match="3 candidates have no triage label"):
        draft_key("q01", built["out"])
    key = draft_key("q01", built["out"], allow_untriaged=True)
    assert key["built"]["untriaged"] == 3 and key["counts"]["skipped"]["untriaged"] == 3
    assert "3 candidates had no triage label" in key["notes"] and key["built"]["partial"] is False


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
    key = draft_key("q02", out, allow_partial=True)
    assert validate_key(key, concept) == []
    edges = {(r["source"], r["target"]): r for r in key["rows"]}
    assert set(edges) == {("p5", "GSM8K"), ("p6", "HotpotQA")}
    gsm8k = edges[("p5", "GSM8K")]
    assert gsm8k["attributes"] == {"metric": "exact match"}
    assert [(f["s"], f["p"], f["o"]) for f in gsm8k["facts"]] == [("p5", "evaluatesOn", "GSM8K"),
                                                                    ("GSM8K", "measured with", "exact match")]
    assert len(key["merged_facts"]) == 1  # the second (p5, evaluatesOn, GSM8K) fact
