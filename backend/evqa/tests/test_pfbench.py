"""pfbench: questions + gold from paperfactory fact rows, their gold file for the scorer (evqa/scoring.py) and
their L3-text scoring by thesis_scorer (no model calls)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from thesis_scorer import text
from thesis_scorer.gold import Gold
from thesis_scorer.schema import GoldFile, Record, TextClaim, TextClaims

from evqa import scoring
from evqa.seed import pfbench, pfview

ENTS = {
    "T1": {"kind": "treatment", "label": "potrogliflozin", "alt": [], "attrs": {}},
    "T2": {"kind": "treatment", "label": "lifostinib", "alt": [], "attrs": {}},
    "TR1": {"kind": "trial", "label": "the ZIMOR-3 trial", "alt": ["ZIMOR-3"], "attrs": {"year": 2015}},
    "TR2": {"kind": "trial", "label": "the BRUMON-6 trial", "alt": ["BRUMON-6"], "attrs": {"year": 2018}},
    "TR3": {"kind": "trial", "label": "the SUTHO-5 trial", "alt": ["SUTHO-5"], "attrs": {"year": 2021}},
}
VOCAB = {"field": "medicine", "words": {"subject_kind": "trial", "subject_plural": "trials"},
         "effect": {"name": "hazard ratio", "short": "HR", "unit": "HR", "better_side": "lower"},
         "relations": {"finds_benefit": {"words": "found a benefit of"}, "finds_no_effect": {"words": "found no effect of"}},
         "conflict_pairs": [["finds_benefit", "finds_no_effect"]],
         "kinds": {"trial": {"numbers": {"patients": {"label": "patients randomised", "unit": "n"},
                                         "sites": {"label": "sites", "unit": "sites"}}},
                   "treatment": {"numbers": {}}}}


def _rows() -> list[dict]:
    rows = []
    for i, (s, r, val) in enumerate([("TR1", "finds_benefit", "0.64"), ("TR2", "finds_no_effect", "1.02"),
                                     ("TR3", "finds_benefit", "0.80")], 1):
        pid = f"MED-0{i}"
        rows.append({"id": f"{pid}:{s}-{r}-T1", "paper": pid, "what": "relation", "subject": s, "relation": r,
                     "object": "T1", "role": "claim"})
        for stat, v in (("estimate", val), ("ci_low", "0.40"), ("ci_high", "1.30")):
            rows.append({"id": f"R-med-0{i}-{stat}", "paper": pid, "what": "effect", "subject": s, "relation": r,
                         "object": "T1", "stat": stat, "value": v, "unit": "HR"})
        rows.append({"id": f"R-med-0{i}-p", "paper": pid, "what": "attr", "subject": s, "attr": "patients",
                     "value": str(100 * i), "unit": "n"})
    rows.append({"id": "MED-03:TR3-finds_benefit-T2", "paper": "MED-03", "what": "relation", "subject": "TR3",
                 "relation": "finds_benefit", "object": "T2", "role": "decoy"})    # T2: a sibling for near misses
    # the same number in a second paper: still one gold row
    rows.append({"id": "R-med-09-p", "paper": "MED-09", "what": "attr", "subject": "TR1", "attr": "patients",
                 "value": "100", "unit": "n"})
    return rows


@pytest.fixture
def dom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    d = tmp_path / "seed" / "pf_test"
    d.mkdir(parents=True)
    (d / "facts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in _rows()))
    (d / "entities.json").write_text(json.dumps(ENTS))
    (d / "vocab.json").write_text(json.dumps(VOCAB))
    (d / "paperfactory.json").write_text("{}")
    monkeypatch.setattr(pfbench, "domain_dir", lambda name: tmp_path / "seed" / name)
    monkeypatch.setattr(pfbench, "DATASET", tmp_path / "dataset")
    import evqa.paths
    monkeypatch.setattr(evqa.paths, "domain_dir", lambda name: tmp_path / "seed" / name)
    monkeypatch.setattr(pfview, "domain_dir", lambda name: tmp_path / "seed" / name)
    monkeypatch.setattr(scoring, "domain_dir", lambda name: tmp_path / "seed" / name)
    monkeypatch.setattr(scoring, "DATASET", tmp_path / "dataset")
    return "pf_test"


def test_build_every_type_and_gold_from_rows(dom: str):
    got = pfbench.build(dom, mix={t: 1 for t in pfbench.MIX})
    by = {g["type"]: g for g in got["golds"]}
    assert set(by) == set(pfbench.MIX), got["short"]
    assert len(by["lookup"]["answer"]["table"]) == 1
    assert {r["value"] for r in by["effect"]["answer"]["table"]} <= {"0.64", "1.02", "0.80", "0.40", "1.30"}
    assert [r["cells"]["year"] for r in by["trend"]["answer"]["table"]] == ["2015", "2018", "2021"]
    assert {e["id"] for e in by["list"]["answer"]["entities"]} == {"TR1", "TR3"}
    assert by["conflict"]["answer"]["table"]            # every disagreeing trial has an effect estimate
    for t in pfbench.NOT_REPORTED:
        assert by[t]["answerable"] is False and by[t]["row_ids"] == []
    oos = by["out_of_scope"]["slots"]["subject"][0]
    assert oos not in {e["label"] for e in ENTS.values()}
    assert by["absent"]["slots"]["attr"] == "sites"


def test_value_in_two_papers_is_one_row(dom: str):
    d = pfbench.Domain(dom)
    lk = next(c for c in pfbench.lookups(d) if c["key"] == ("lookup", "TR1", "patients"))
    assert lk["table"][0]["papers"] == ["MED-01", "MED-09"]


def _gold(dom: str, golds: list[dict]) -> Gold:
    return Gold(GoldFile.model_validate({"domain": dom, "kind": "paperfactory", "units": {},
                                         "entities": ENTS, "questions": golds}))


def _score(dom: str, g: dict, answer: str, claims: list[TextClaim]) -> dict:
    tc = TextClaims(qid=g["qid"], text_sha256="x", model="m", claims=claims)
    return text.score_question(g, Record(qid=g["qid"], answer=answer), tc, _gold(dom, [g]), None)


def test_scoring_numbers_without_units_and_any_paper(dom: str):
    d = pfbench.Domain(dom)
    lk = next(c for c in pfbench.lookups(d) if c["key"] == ("lookup", "TR1", "patients"))
    g = pfbench._gold("Q1", d, "lookup", lk["q"], lk["slots"], lk["table"], lk["columns"])
    t = "The ZIMOR-3 trial randomised 100 patients (MED-09)."
    got = _score(dom, g, t, [TextClaim(value_text="100 patients", subject="the ZIMOR-3 trial", paper="MED-09",
                                       quote=t)])
    assert got["exact"] and got["score"] == 1.0


def test_scoring_entity_list(dom: str):
    d = pfbench.Domain(dom)
    c = pfbench.lists(d)[0]
    g = pfbench._gold("Q2", d, "list", c["q"], c["slots"], [], c["columns"], c["entities"])
    right = _score(dom, g, "ZIMOR-3 and the SUTHO-5 trial.", [])
    extra = _score(dom, g, "ZIMOR-3, SUTHO-5 and BRUMON-6.", [])
    assert right["exact"] and right["score"] == 1.0
    assert extra["recall"] == 1.0 and extra["precision"] == pytest.approx(2 / 3, abs=1e-3)


def test_gold_file_of_a_paperfactory_domain(dom: str):
    pfbench.write(dom, pfbench.build(dom, mix={t: 1 for t in pfbench.MIX}))
    gf = scoring.gold_file(dom, "test")
    assert gf["kind"] == "paperfactory" and gf["facts"] == {} and gf["names"] == {}
    assert gf["entities"]["TR1"] == {"kind": "trial", "label": "the ZIMOR-3 trial", "alt": ["ZIMOR-3"]}
    assert len(gf["questions"]) == len(pfbench.MIX) and all(q["question"] for q in gf["questions"])
    lk = next(q for q in gf["questions"] if q["type"] == "lookup")
    assert lk["answer"]["table"][0]["papers"]
