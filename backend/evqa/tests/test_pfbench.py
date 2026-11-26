"""pfbench: questions + gold from paperfactory fact rows, their gold file for the scorer (evqa/scoring.py) and
their L3-text scoring by thesis_scorer (no model calls)."""
from __future__ import annotations

import json
import re
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


def test_scaled_mix_keeps_shares():
    from evqa.seed.pfbench import MIX, scaled_mix
    assert scaled_mix(40) == MIX
    m = scaled_mix(50)
    assert sum(m.values()) == 50 and set(m) == set(MIX)
    assert all(abs(m[t] - MIX[t] * 50 / 40) < 1 for t in MIX)


def _add_rows(dom: str, rows: list[dict]) -> None:
    f = pfbench.domain_dir(dom) / "facts.jsonl"
    f.write_text(f.read_text() + "".join(json.dumps(r) + "\n" for r in rows))


def test_papers_that_disagree_give_one_row_per_value_and_a_conflict(dom: str):
    """25 Nov 2026: a v2 paper reports 0.66 where the main seed says 0.64; both are gold, each with its paper."""
    _add_rows(dom, [{"id": "v2-R-med-01-e", "paper": "v2-MED-01", "what": "effect", "subject": "TR1",
                     "relation": "finds_benefit", "object": "T1", "stat": "estimate", "value": "0.66", "unit": "HR"},
                    {"id": "v2-R-med-01-p", "paper": "v2-MED-01", "what": "attr", "subject": "TR2",
                     "attr": "patients", "value": "250", "unit": "n"}])
    d = pfbench.Domain(dom)
    lk = next(c for c in pfbench.lookups(d) if c["key"] == ("lookup", "TR2", "patients"))
    assert [(r["value"], r["papers"]) for r in lk["table"]] == [("200", ["MED-02"]), ("250", ["v2-MED-01"])]
    best = next(c for c in pfbench.bests(d))
    assert [r["value"] for r in best["table"] if r["cells"]["candidate"] == "the ZIMOR-3 trial"] == ["0.64", "0.66"]
    keys = {c["key"] for c in pfbench.conflicts(d)}
    assert ("conflict", "TR2", "patients") in keys and ("conflict", "TR1", "finds_benefit", "T1") in keys


def test_refresh_keeps_the_questions_and_recomputes_gold(dom: str):
    pfbench.write(dom, pfbench.build(dom, mix={t: 1 for t in pfbench.MIX}))
    before = (pfbench.DATASET / dom / "questions" / "test.jsonl").read_text().splitlines()
    absent = next(json.loads(x) for x in before if json.loads(x)["type"] == "absent")
    _, s, a = json.loads((pfbench.domain_dir(dom) / "gold" / f"{absent['qid']}.json").read_text())["spec"]["key"]
    _add_rows(dom, [{"id": "v2-R-x", "paper": "v2-MED-01", "what": "attr", "subject": "TR1", "attr": "patients",
                     "value": "105", "unit": "n"},
                    {"id": "v2-R-y", "paper": "v2-MED-01", "what": "attr", "subject": s, "attr": a,
                     "value": "7", "unit": "sites"}])      # the asked absent number is now reported
    got = pfbench.refresh(dom)
    pfbench.write(dom, got)
    after = [json.loads(x) for x in (pfbench.DATASET / dom / "questions" / "test.jsonl").read_text().splitlines()]
    assert [q["question"] for q in after[:len(before)]] == [json.loads(x)["question"] for x in before]
    assert got["lost"] == [] and got["turned"] == [absent["qid"]]
    turned = next(q for q in after if q["qid"] == absent["qid"])
    assert turned["type"] == "lookup" and turned["answerable"] is True
    assert len(got["added"]) == 1 and after[-1]["type"] == "conflict"


def test_add_hard_keeps_questions_and_adds_look_alikes_and_near_misses(dom: str, tmp_path: Path):
    pfbench.write(dom, pfbench.build(dom, mix={t: 1 for t in pfbench.MIX}))
    _add_rows(dom, [{"id": "MED-01:TR9-finds_benefit-T2", "paper": "MED-01", "what": "relation", "subject": "TR2",
                     "relation": "finds_benefit", "object": "T2", "role": "decoy"}])  # T2 named in TR1's paper
    pdir = tmp_path / "dataset" / dom / "MED-01"
    pdir.mkdir(parents=True)
    (pdir / "paper.md").write_text("The ZIMOR-3 trial, the BRUMON-6 trial and the SUTHO-5 trial; lifostinib.")
    before = (pfbench.DATASET / dom / "questions" / "test.jsonl").read_text().splitlines()
    got = pfbench.add_hard(dom, n={"absent": 1, "near_miss": 1, "out_of_scope": 1})
    pfbench.write(dom, got)
    after = [json.loads(x) for x in (pfbench.DATASET / dom / "questions" / "test.jsonl").read_text().splitlines()]
    assert [q["question"] for q in after[:len(before)]] == [json.loads(x)["question"] for x in before]
    assert all(q["intent_card"] == pfbench.CARD for q in after)          # one card for all: no answerability leak
    hard = {g["type"]: g for g in got["golds"] if g["spec"].get("level") == "hard"}
    oos = hard["out_of_scope"]["slots"]["subject"][0]
    assert re.sub(r"\d+", "", oos) in {re.sub(r"\d+", "", e["label"]) for e in ENTS.values()}   # a look-alike
    assert oos.lower() not in (pdir / "paper.md").read_text().lower()
    assert "with its 95% confidence interval" in hard["near_miss"]["wording"]["text"]   # worded like an effect
    again = pfbench.add_hard(dom, n={"absent": 1, "near_miss": 1, "out_of_scope": 1})
    assert again["added"] == []                                          # a type that has hard ones gets no more


# ---------------------------------------------------------------- law: one court naming for every one-number question
LAW_ENTS = {
    "C1": {"kind": "court", "label": "Tetre District Court", "alt": [], "attrs": {"level": 1}},
    "C2": {"kind": "court", "label": "Tetre Court of Appeal", "alt": [], "attrs": {"level": 2}},
    "D1": {"kind": "decision", "label": "Arno v. Bel Bank", "alt": [], "attrs": {"court": "C1", "year": 2015}},
    "D2": {"kind": "decision", "label": "Cato v. Dex Media", "alt": [], "attrs": {"court": "C2", "year": 2018}},
}
LAW_VOCAB = {"field": "law", "words": {"subject_kind": "decision", "subject_plural": "decisions"}, "effect": None,
             "relations": {}, "conflict_pairs": [],
             "kinds": {"court": {"numbers": {}}, "provision": {"numbers": {}},
                       "decision": {"numbers": {"judges": {"label": "judges", "unit": "judges"},
                                                "hearing_days": {"label": "hearing days", "unit": "days"}}}}}
COURT_Q = re.compile(r"^In (.+) before the (Tetre [A-Za-z ]+?), what number is reported for (.+)\?$")


@pytest.fixture
def law(dom: str) -> str:
    d = pfbench.domain_dir("pf_law")
    d.mkdir(parents=True)
    rows = [{"id": f"R-law-0{i}-j", "paper": f"LAW-0{i}", "what": "attr", "subject": s, "attr": "judges",
             "value": str(i + 2), "unit": "judges"} for i, s in ((1, "D1"), (2, "D2"))]
    (d / "facts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "entities.json").write_text(json.dumps(LAW_ENTS))
    (d / "vocab.json").write_text(json.dumps(LAW_VOCAB))
    return "pf_law"


def test_law_traps_and_normal_questions_name_courts_the_same_way(law: str):
    """26 Nov 2026 (closed-book test, near_miss above chance): only traps named a court, so the court gave them
    away. Now lookup, absent, near_miss and out_of_scope all read "In <decision> before the <court>, ..."."""
    got = pfbench.build(law, mix={"lookup": 1, "absent": 1, "near_miss": 1, "out_of_scope": 1})
    by = {g["type"]: g for g in got["golds"]}
    assert set(by) == set(pfbench.ONE_NUMBER), got["short"]
    for t, g in by.items():
        m = COURT_Q.match(g["wording"]["text"])
        assert m, (t, g["wording"]["text"])
        assert m.group(1) == g["slots"]["subject"][0]
    own = {LAW_ENTS[e]["label"]: LAW_ENTS[LAW_ENTS[e]["attrs"]["court"]]["label"] for e in ("D1", "D2")}
    lk, nm = (COURT_Q.match(by[t]["wording"]["text"]) for t in ("lookup", "near_miss"))
    assert lk.group(2) == own[lk.group(1)] and nm.group(2) != own[nm.group(1)]   # right court vs the trap's wrong one


def test_refresh_reword_moves_old_law_wording_and_keeps_the_gold(law: str):
    pfbench.write(law, pfbench.build(law, mix={"lookup": 1, "absent": 1, "near_miss": 1, "out_of_scope": 1}))
    gdir, qfile = pfbench.domain_dir(law) / "gold", pfbench.DATASET / law / "questions" / "test.jsonl"
    old = {}
    for p in gdir.glob("Q-*.json"):          # back to the "plain-1" wording: a court only in the near miss
        g = json.loads(p.read_text())
        if g["type"] != "near_miss":
            m = COURT_Q.match(g["wording"]["text"])
            text = f"For {m.group(1)}, what number is reported for {m.group(3)}?"
            g["wording"] = {"template": text, "source": "template", "text": text}
            p.write_text(json.dumps(g))
        old[g["qid"]] = g
    qfile.write_text("".join(json.dumps(json.loads(x) | {"question": old[json.loads(x)["qid"]]["wording"]["text"]})
                             + "\n" for x in qfile.read_text().splitlines()))
    assert pfbench.refresh(law)["reworded"] == []                       # without reword: wording kept
    got = pfbench.refresh(law, reword=True)
    assert sorted(got["reworded"]) == sorted(q for q, g in old.items() if g["type"] != "near_miss")
    for g in got["golds"]:
        assert {k: v for k, v in g.items() if k != "wording"} == {k: v for k, v in old[g["qid"]].items()
                                                                  if k != "wording"}
        assert COURT_Q.match(g["wording"]["text"])
        if g["qid"] in got["reworded"]:
            assert g["wording"]["before"] == old[g["qid"]]["wording"]
            assert g["wording"]["version"] == pfbench.WORDING_VERSION
    assert [q["question"] for q in got["questions"]] == [g["wording"]["text"] for g in got["golds"]]
