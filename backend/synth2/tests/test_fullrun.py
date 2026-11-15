import json
from pathlib import Path

import pytest
import yaml

from synth2 import fullrun

DATA = Path(__file__).resolve().parents[3] / "data" / "synth2"
ALL = {"helps", "hurts", "no_effect"}


@pytest.fixture
def recipe():
    return yaml.safe_load((DATA / "rag.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def phrases():
    return yaml.safe_load((DATA / "rag.phrases.yaml").read_text(encoding="utf-8"))


def test_study_inputs_carry_the_counts_the_claim_sentence_and_names(tiny, recipe, phrases):
    truth = json.loads((tiny / "ground_truth.json").read_text(encoding="utf-8"))
    inputs = fullrun.study_inputs(tiny, recipe, phrases)
    assert sorted(inputs) == sorted(s["id"] for s in truth["studies"])
    for s in truth["studies"]:
        inp = inputs[s["id"]]
        paper = (tiny / "papers" / f"{s['id']}.md").read_text(encoding="utf-8")
        assert inp["label"] == s["label"] and inp["benchmark"] == s["dataset"]
        assert inp["claim_sentence"] and inp["claim_sentence"] in paper
        assert [(c["treatment_correct"], c["treatment_total"], c["control_correct"], c["control_total"])
                for c in inp["cells"]] == [(c["k_t"], c["n_t"], c["k_c"], c["n_c"]) for c in s["cells"]]
        assert all(lv["suggested"] and lv["suggested"] != lv["name"] for c in inp["cells"] for lv in c["levels"])
        assert inp["system_names"]["treatment"] in fullrun.TREAT and inp["system_names"]["control"] in fullrun.CTRL
    assert fullrun.study_inputs(tiny, recipe, phrases) == inputs


def test_assign_gives_each_study_its_own_source_and_spends_restricted_ones_first():
    got, shared = fullrun.assign({"S1": "helps", "S2": "hurts", "S3": "hurts"},
                                 {"a": ALL, "b": {"helps"}, "c": ALL}, "seed")
    assert got["S1"] == "b" and sorted([got["S2"], got["S3"]]) == ["a", "c"] and shared == []


def test_assign_never_gives_a_source_whose_own_result_points_another_way():
    got, shared = fullrun.assign({"S1": "hurts", "S2": "hurts"}, {"a": ALL, "b": {"helps"}}, "seed")
    assert got == {"S1": "a", "S2": "a"} and shared == ["S2"]


def test_assign_refuses_a_claim_no_source_allows():
    with pytest.raises(ValueError, match="no source allows"):
        fullrun.assign({"S1": "no_effect"}, {"b": {"helps"}}, "seed")


def test_assign_is_seeded():
    pool = {p: ALL for p in "abcdef"}
    claims = {f"S{i}": "helps" for i in range(4)}
    assert fullrun.assign(claims, pool, "x") == fullrun.assign(claims, pool, "x")
    assert any(fullrun.assign(claims, pool, s)[0] != fullrun.assign(claims, pool, "x")[0] for s in "abcdefgh")


SOURCE = ("# Reading With Passages\n\n## Abstract\n\nWe study a reader on the NaturalQuestions benchmark and report "
          "results.\n\n## Method\n\nOur reader encodes each passage and decodes an answer. Karpukhin et al. (2020) "
          "built an earlier reader.\n\n## Results\n\nThe reader answers many questions well.\n\n## Conclusion\n\n"
          "We presented a reader. It works on several datasets.\n")


def three_sources(tmp_path):
    full = tmp_path / "full"
    full.mkdir()
    for p in ("p1", "p2", "p3"):
        (full / f"{p}.md").write_text(SOURCE.replace("Reading", f"Reading {p[-1]}"), encoding="utf-8")
    return full, {"p1": ALL, "p2": ALL, "p3": ALL}


def test_a_failing_study_is_retried_with_other_system_names(tiny, tmp_path, recipe, phrases, monkeypatch):
    first = fullrun.study_inputs(tiny, recipe, phrases)["S001"]["system_names"]
    real = fullrun.realedit.apply_study

    def flaky(base, sid, **kw):
        r = real(base, sid, **kw)
        names = json.loads((base / "inputs" / f"{sid}.json").read_text(encoding="utf-8"))["system_names"]
        return {**r, "problems": ["clash"]} if sid == "S001" and names == first else r

    monkeypatch.setattr(fullrun.realedit, "apply_study", flaky)
    full, pool = three_sources(tmp_path)
    summary = fullrun.run_corpus(tiny, tmp_path / "work", tmp_path / "out", pool, full, recipe, phrases)
    s1 = summary["studies"]["S001"]
    assert s1["problems"] == [] and s1["redrawn"] and summary["assembled"]
    names = json.loads((tmp_path / "work" / "inputs" / "S001.json").read_text(encoding="utf-8"))["system_names"]
    assert names != first and not summary["studies"]["S002"]["redrawn"]


def test_run_corpus_writes_a_checked_corpus(tiny, tmp_path, recipe, phrases):
    full, pool = three_sources(tmp_path)
    summary = fullrun.run_corpus(tiny, tmp_path / "work", tmp_path / "out", pool, full, recipe, phrases)
    truth = json.loads((tmp_path / "out" / "ground_truth.json").read_text(encoding="utf-8"))
    assert sorted(summary["studies"]) == sorted(s["id"] for s in truth["studies"])
    assert all(r["problems"] == [] for r in summary["studies"].values()), summary
    assert all((tmp_path / "out" / "papers" / f"{s['id']}.md").is_file() for s in truth["studies"])
    assert summary["shared"] == sorted(summary["shared"]) and len(summary["shared"]) == len(truth["studies"]) - 3
    assert json.loads((tmp_path / "work" / "run.json").read_text(encoding="utf-8")) == summary


def test_a_built_corpus_places_every_planted_fact_so_the_oracle_scores_perfectly(tiny, tmp_path, recipe, phrases):
    from evaluation import oracle
    from evaluation.score import score
    from repo_paths import DATA as REPO_DATA
    full, pool = three_sources(tmp_path)
    fullrun.run_corpus(tiny, tmp_path / "work", tmp_path / "out", pool, full, recipe, phrases)
    truth = json.loads((tmp_path / "out" / "ground_truth.json").read_text(encoding="utf-8"))
    for s in truth["studies"]:
        text = (tmp_path / "out" / "papers" / f"{s['id']}.md").read_text(encoding="utf-8")
        mine = {p["fact"]: text[p["start"]:p["end"]] for p in truth["placements"] if p["paper"] == s["id"]}
        for j, c in enumerate(s["cells"]):
            assert [mine[f"{s['id']}.c{j}.{f}"] for f in ("k_t", "n_t", "k_c", "n_c")] == [
                str(c[f]) for f in ("k_t", "n_t", "k_c", "n_c")]
        assert any(".claim." in f for f in mine)
    out = oracle.run(REPO_DATA / "domains/rag/protocols/rag-factuality.yaml", tmp_path / "out", tmp_path / "oracle")
    a = next(r for r in score(out, tmp_path / "out")["extraction"]["rows"]
             if r["evidence_type"] == "all" and r["level"] == "all")
    assert a["f1"] == 1.0 and a["span_accuracy"] == 1.0


EXTRA = {"id": "X1", "quote": "Karpukhin et al. (2020) built an earlier reader.", "direction": "helps"}


def test_a_known_extra_is_recorded_as_it_reads_in_the_built_paper(tiny, tmp_path, recipe, phrases):
    full, pool = three_sources(tmp_path)
    summary = fullrun.run_corpus(tiny, tmp_path / "work", tmp_path / "out", pool, full, recipe, phrases,
                                 extras={"p1": [EXTRA]})
    truth = json.loads((tmp_path / "out" / "ground_truth.json").read_text(encoding="utf-8"))
    on_p1 = sorted(sid for sid, s in summary["studies"].items() if s["source"] == "p1")
    assert on_p1 and sorted(e["study"] for e in truth["known_extras"]) == on_p1
    for e in truth["known_extras"]:
        paper = (tmp_path / "out" / "papers" / f"{e['study']}.md").read_text(encoding="utf-8")
        assert e["text"] in paper and "Karpukhin" not in e["text"] and e["text"].endswith("built an earlier reader.")
        assert (e["id"], e["direction"]) == ("X1", "helps")


def test_a_corpus_without_extras_has_an_empty_list(tiny, tmp_path, recipe, phrases):
    full, pool = three_sources(tmp_path)
    fullrun.run_corpus(tiny, tmp_path / "work", tmp_path / "out", pool, full, recipe, phrases)
    assert json.loads((tmp_path / "out" / "ground_truth.json").read_text(encoding="utf-8"))["known_extras"] == []


def test_load_extras_refuses_a_paper_id_yaml_reads_as_a_number(tmp_path):
    (tmp_path / "x.yaml").write_text('"2305.14251":\n  - {id: F1, quote: q, direction: helps}\n', encoding="utf-8")
    assert list(fullrun.load_extras(tmp_path / "x.yaml")) == ["2305.14251"]
    (tmp_path / "x.yaml").write_text("2305.14251:\n  - {id: F1, quote: q, direction: helps}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="quote the paper id"):
        fullrun.load_extras(tmp_path / "x.yaml")


def test_an_extra_whose_quote_is_not_in_its_source_is_refused(tiny, tmp_path, recipe, phrases):
    full, pool = three_sources(tmp_path)
    with pytest.raises(ValueError, match="not in source p2"):
        fullrun.run_corpus(tiny, tmp_path / "work", tmp_path / "out", pool, full, recipe, phrases,
                           extras={"p2": [{**EXTRA, "quote": "A sentence the paper never had."}]})
