"""D4: decoy warnings, real names, shape report. D5: confusions per relation, aliases across the world."""
from __future__ import annotations

import copy
import json
import subprocess

import pytest

from paperfactory import packs, world
from paperfactory.tests.test_offline import ARG, LAW, PILOT


def test_pilot_still_passes_and_its_loose_decoys_are_warnings() -> None:
    assert world.check(PILOT, LAW, ARG, n_papers=3) == []
    warn = world.decoy_warnings(PILOT, LAW)
    assert any("L-01 decoy ['K6', 'relies_on', 'K1']" in x for x in warn)
    assert not any("['K1', 'relies_on', 'S14']" in x for x in warn)        # same relation, one entity different


def test_real_names_from_the_pack_are_errors() -> None:
    f = packs.Field(copy.deepcopy(LAW.raw) | {"real_names": ["Vantor"]})
    errs = world.check(PILOT, f, ARG)
    assert any("K4" in e and "real name 'Vantor'" in e for e in errs)
    f.raw["real_names"] = ["Vant"]                                          # whole words only
    assert world.check(PILOT, f, ARG) == []


def test_a_short_name_equal_to_another_entitys_derived_name_is_an_error() -> None:
    w = copy.deepcopy(PILOT)
    w["entities"]["K2"]["alt"].append("Pell")       # "Pell" is derived from K4's title "Pell v. Vantor Systems"
    errs = world.check(w, LAW, ARG)
    assert any("'Pell' (K2) is also a derived name of K4" in e or "used by" in e for e in errs)
    w = copy.deepcopy(PILOT)
    w["entities"]["K4"]["alt"] = []
    w["entities"]["K2"]["alt"].append("pell")
    assert "name 'pell' (K2) is also a derived name of K4" in world.check(w, LAW, ARG)


def test_shape_report() -> None:
    sh = world.shape(PILOT, LAW, ARG, pages=6)
    assert sh["papers"] == 3 and sh["per_paper"]["L-03"]["conflict"] and sh["per_paper"]["L-01"]["facts"] == 6
    assert sh["per_paper"]["L-01"]["words"] == [2700, 3300]


@pytest.mark.parametrize("name", ["law", "medicine", "materials", "llm"])
def test_confusions_are_relations_and_go_both_ways(name: str) -> None:
    f = packs.field(name)
    for r, d in f.relations.items():
        for c in d["confusable_with"]:
            assert c in f.relations and c != r
            assert r in f.relations[c]["confusable_with"], (r, c)
    assert f.raw["real_names"] == [] and f.raw["real_names_note"]
    assert "| Easily confused with |" in packs.relation_table(f)


def test_world_agent_prompt_does_not_change() -> None:
    old = subprocess.run(["git", "show", "a6b7cad:backend/paperfactory/packs/fields/law.json"], capture_output=True,
                         text=True, cwd=packs.PACKS).stdout
    if not old:
        pytest.skip("commit a6b7cad not in this clone")
    old_f = packs.Field(json.loads(old))
    keys = ("setting", "kinds", "relations", "conflict_pairs", "world_notes")
    assert world._pack_text(LAW) == json.dumps({k: old_f.raw[k] for k in keys if k in old_f.raw}, indent=1)


def test_a_paper_planned_twice_is_an_error() -> None:
    """Review finding 9."""
    w = copy.deepcopy(PILOT)
    w["papers"]["L-04"] = copy.deepcopy(w["papers"]["L-01"])
    errs = world.check(w, LAW, ARG)
    assert "L-04: same claims as L-01 (a paper planned twice)" in errs
    assert "L-04: same title as L-01 (a paper planned twice)" in errs
