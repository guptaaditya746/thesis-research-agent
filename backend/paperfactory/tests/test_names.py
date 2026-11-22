"""Names made in code for drafted worlds (names.py): the Qwen 20-paper law and llm failures of 22 Nov 2026."""
from __future__ import annotations

import copy
from pathlib import Path

from paperfactory import config, names, packs, world
from paperfactory.tests.test_world import ENTS, PAPERS, ents_answer

ARG = packs.genre("argument")


def law_answer(n: int) -> list[dict]:
    """Tonight's law shape: 3 courts, 2 statutes, n decisions (Qwen gave about 40 and reused party names)."""
    out = [{"id": f"C{i}", "kind": "court", "name_parts": {"court_type": t}, "attrs": {"level": i}}
           for i, t in enumerate(["Supreme Court", "Court of Appeal", "District Court"], 1)]
    out += [{"id": f"P{i}", "kind": "provision", "name_parts": {"section": str(i), "statute": "Data Act"},
             "attrs": {"topic": "consent"}} for i in range(1, 7)]
    out += [{"id": f"D{i}", "kind": "decision", "name_parts": {"org": "Media"},
             "attrs": {"court": "C3", "year": 2010 + i % 15, "facts": "a worker's messages were read"}}
            for i in range(1, n + 1)]
    return out


def test_forty_decisions_never_clash() -> None:
    f = packs.field("law")
    ents, errs = names.assign(law_answer(40), f, seed=7)
    assert errs == [] and world.check({"entities": ents, "papers": {}}, f, ARG) == []
    assert ents["C2"]["label"].endswith(" Court of Appeal") and ents["P3"]["label"].startswith("section 3 of the ")
    assert len({e["label"].split(" v. ")[0] for k, e in ents.items() if k.startswith("D")}) == 40


def test_every_field_names_twenty_paper_worlds_without_clashes() -> None:
    answers = {
        "llm": [{"id": f"M{i}", "kind": "method", "name_parts": {"type": "prompting"}, "attrs": {"family": "x"}}
                for i in range(6)] + [{"id": "L1", "kind": "model", "name_parts": {"size": "13B"},
                                       "attrs": {"size": "13B"}},
                                      {"id": "B1", "kind": "benchmark", "name_parts": {"code": "QA"},
                                       "attrs": {"task": "qa"}}]
               + [{"id": f"S{i}", "kind": "study", "name_parts": {},
                   "attrs": {"year": 2019 + i % 7, "model": "L1", "benchmark": "B1", "setting": "x"}}
                  for i in range(40)],
        "medicine": [{"id": f"T{i}", "kind": "treatment", "name_parts": {"stem": "-mab"},
                      "attrs": {"drug_class": "antibody"}} for i in range(6)]
        + [{"id": f"R{i}", "kind": "trial", "name_parts": {},
            "attrs": {"condition": "asthma", "year": 2012 + i % 13, "design": "RCT", "patients": 100}}
           for i in range(40)],
        "materials": [{"id": f"A{i}", "kind": "material", "name_parts": {"type": "alloy"},
                       "attrs": {"family": "steel"}} for i in range(6)]
        + [{"id": f"S{i}", "kind": "study", "name_parts": {},
            "attrs": {"property": "wear", "year": 2012 + i % 13, "method": "pin-on-disc"}} for i in range(40)]}
    for field, got in answers.items():
        f = packs.field(field)
        ents, errs = names.assign(got, f, seed=1)
        assert errs == [] and world.check({"entities": ents, "papers": {}}, f, ARG) == [], field
    meds, _ = names.assign(answers["medicine"], packs.field("medicine"), seed=1)
    assert meds["T0"]["label"].endswith("mab") and meds["T0"]["label"].islower()


def test_same_seed_same_names_and_pack_words_are_never_used() -> None:
    f = packs.field("law")
    a, _ = names.assign(law_answer(10), f, seed=3)
    b, _ = names.assign(law_answer(10), f, seed=3)
    c, _ = names.assign(law_answer(10), f, seed=4)
    assert a == b and a != c
    assert "Court" not in [e["label"].split(" v. ")[0] for e in a.values()]


def test_bad_name_parts_go_to_the_repair(tmp_path: Path, pilot_focus) -> None:
    f = packs.field("law")
    _, errs = names.assign([{"id": "C1", "kind": "court", "name_parts": {"wrong": "x"}, "attrs": {"level": 1}}], f, 1)
    assert any("'court_type' missing" in e for e in errs) and any("'wrong' is not one" in e for e in errs)
    bad = copy.deepcopy(ENTS)
    for e in bad["entities"]:
        if e["kind"] == "court":
            e["name_parts"] = {}
    seen: list[str] = []

    def call(role, step, system, user, schema, check=None, cache=True):
        seen.append(step)
        if step.startswith("world:entities"):
            return ents_answer(step, bad if step == "world:entities:court" else ENTS)
        return {"papers": copy.deepcopy(PAPERS)}
    w = world.draft(config.Settings("law", "argument", papers=3, out=str(tmp_path)), f, ARG, call)
    assert seen[:3] == ["world:entities:court", "world:entities:court:repair", "world:entities:provision"]
    assert world.check(w, f, ARG, n_papers=3) == []


def test_the_world_prompt_shows_parts_not_patterns() -> None:
    text = world._pack_text(packs.field("law"))
    assert "court_type" in text and "{COUNTRY}" not in text and "name_parts" in world.ENT_SYS
