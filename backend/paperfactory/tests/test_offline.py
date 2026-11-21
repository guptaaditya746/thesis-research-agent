"""Offline tests (no model calls): packs, world checks, seed + gold, materials, settings, template rendering."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from paperfactory import config, materials, packs, seed, world
from paperfactory.evaluate import Eval
from paperfactory.text import split_sents
from paperfactory.write import repeated_phrases

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW, ARG = packs.field("law"), packs.genre("argument")


@pytest.mark.parametrize("name", ["law", "medicine", "materials"])
def test_every_field_pack_is_complete(name: str) -> None:
    f = packs.field(name)
    for key in ("paper_kind", "venue", "subject_kind", "subject_plural", "source_kinds", "actor",
                "framework_section", "analysis_section"):
        assert f.words[key]
    assert set(f.subject_kinds) <= set(f.kinds)
    for r, d in f.relations.items():
        assert set(d["object_kinds"]) <= set(f.kinds), r
    for a, b in f.conflict_pairs:
        assert a in f.relations and b in f.relations
    for q in f.questions:
        assert q.get("relation", next(iter(f.relations))) in f.relations
        assert set(q.get("relation_in", [])) <= set(f.relations)


def test_pilot_world_passes_the_checks() -> None:
    assert world.check(PILOT, LAW, ARG, n_papers=3) == []


@pytest.mark.parametrize("change, message", [
    (lambda w: w["papers"]["L-01"]["claims"].__setitem__(0, ["K5", "relies_on", "CT1"]), "object of relies_on"),
    (lambda w: w["papers"]["L-01"]["claims"].__setitem__(0, ["K1", "distinguishes", "K5"]), "earlier one"),
    (lambda w: w["papers"]["L-02"]["decoys"].__setitem__(0, ["K5", "rejects", "S14"]), "relation relies_on in one paper"),
    (lambda w: w["entities"]["K2"]["alt"].append("Marrin"), "used by"),
    (lambda w: w["papers"]["L-01"]["decoys"].pop(), "need 3"),
])
def test_world_check_catches_broken_worlds(change, message: str) -> None:
    w = copy.deepcopy(PILOT)
    change(w)
    assert any(message in e for e in world.check(w, LAW, ARG)), world.check(w, LAW, ARG)


def test_seed_passes_shacl_and_every_question_has_gold() -> None:
    _, gold = seed.make(PILOT, LAW, per_question=3, seed=1)
    assert len(gold["facts"]) == 18
    assert gold["questions"]
    for q in gold["questions"]:
        assert q["gold"]
        assert q["papers"][0] == q["id"].split(":")[0]
        for i in q["gold"]:
            fa = gold["facts"][i]
            assert set(fa["papers"]) & set(q["papers"])
            assert q.get("subject", fa["s"]) == fa["s"] and q.get("object", fa["o"]) == fa["o"]


def test_conflict_question_has_both_sides() -> None:
    _, gold = seed.make(PILOT, LAW, per_question=3, seed=1)
    q = next(q for q in gold["questions"] if q["id"] == "L-03:conflict")
    assert {"K3-relies_on-S9", "K4-rejects-S9"} <= set(q["gold"])


def test_materials_give_holdings_as_data_not_sentences() -> None:
    _, log = materials.materials(PILOT, LAW, ARG, "L-03")
    assert "| Pell v. Vantor Systems | rejected | section 9 of the Veldra Personal Data Act 2016 |" in log
    assert "as a basis for its ruling." not in log.split("Action meanings:")[0]
    assert "## 4. Conflict" in log


def test_template_gets_field_words_and_length(tmp_path: Path) -> None:
    d = packs.render_template(LAW, ARG, 10, tmp_path)
    assert "## 2. Legal Framework" in (d / "template.md").read_text()
    guide = (d / "guidelines.md").read_text()
    assert "10 printed pages" in guide and "4500 to 5500 words" in guide and "{" not in guide
    assert json.loads((d / "genre.json").read_text())["numeric_facts"] is False


def test_settings_model_per_role(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"field": "law", "genre": "argument", "models": {"default": "m0", "judge": "m1"}}))
    s = config.load(p)
    assert s.model("judge") == "m1" and s.model("writer") == "m0" and s.papers == 20
    p.write_text(json.dumps({"field": "law", "genre": "argument", "models": {"jduge": "m1"}}))
    with pytest.raises(ValueError):
        config.load(p)


def test_judge_options_come_from_the_field() -> None:
    _, gold = seed.make(PILOT, LAW, per_question=3, seed=1)
    e = Eval(config.Settings("law", "argument"), PILOT, LAW, gold, call=None)
    assert list(e.letters.values()) == ["relies_on", "distinguishes", "rejects", "none"]
    med = packs.field("medicine")
    e2 = Eval(config.Settings("medicine", "argument"), PILOT, med, gold, call=None)
    assert len(e2.letters) == len(med.relations) + 1


def test_split_and_repeats() -> None:
    s = split_sents("In Marrin v. Tolst Media the court held so. Then s. 9 applied to it here.\n")
    assert [x[2] for x in s] == ["In Marrin v. Tolst Media the court held so.", "Then s. 9 applied to it here."]
    text = "In Rusk the court relied on it as a basis for its ruling. " * 3
    assert repeated_phrases(text, ["Rusk"])
