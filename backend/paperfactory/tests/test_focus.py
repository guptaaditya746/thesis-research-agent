"""Focus subjects chosen in code (world.plan_focus): at 20 papers Qwen copied earlier papers' claims (22 Nov 2026)."""
from __future__ import annotations

from paperfactory import packs, world

plan_focus = world.plan_focus          # the real one (some tests replace it with the pilot's focus)
LAW = packs.field("law")


def ents(n: int) -> dict:
    return {"entities": {f"D{i}": {"kind": "decision"} for i in range(n)} | {"P1": {"kind": "provision"}}}


def test_every_subject_leads_once_before_any_leads_twice_and_pairs_never_repeat() -> None:
    fo = plan_focus(ents(80), LAW, 1, 50)
    first = [x for pair in fo[:40] for x in pair]
    assert len(first) == len(set(first)) == 80 and "P1" not in first
    assert len({frozenset(p) for p in fo}) == 50
    assert plan_focus(ents(80), LAW, 1, 50) == fo and plan_focus(ents(80), LAW, 2, 50) != fo


def test_focus_errors_name_the_paper() -> None:
    papers = {"LAW-01": {"focus": ["D1", "D2"], "claims": [["D1", "relies_on", "P1"], ["D3", "rejects", "P1"]]},
              "LAW-02": {"claims": [["D9", "relies_on", "P1"]]}}
    errs = world.focus_errors(papers)
    assert errs == ["LAW-01: claim subject D3 is not one of its FOCUS ['D1', 'D2']",
                    "LAW-01: FOCUS subject D2 is the subject of no claim"]


def test_the_paper_prompt_has_the_focus_rule() -> None:
    assert "FOCUS" in world.PAPER_SYS and "FOCUS" not in world.PAPER_SYS_V2


def test_flipped_decoys_are_replaced_by_near_misses_in_code() -> None:
    """The llm 40 world's LLM-01 answer (22 Nov 2026): two decoys flip a claim's relation."""
    import random
    f = packs.field("llm")
    ents = {"S22": {"kind": "study", "attrs": {"year": 2024}}, "S42": {"kind": "study", "attrs": {"year": 2025}},
            "S7": {"kind": "study", "attrs": {"year": 2023}}, "M3": {"kind": "method"}, "M6": {"kind": "method"},
            "M1": {"kind": "method"}}
    p = {"claims": [["S22", "reports_gain", "M3"], ["S42", "reports_drop", "M3"], ["S42", "reports_gain", "M6"]],
         "decoys": [["S22", "reports_gain", "M6"], ["S42", "reports_drop", "M6"], ["S22", "reports_drop", "M3"]]}
    truth = {("S7", "M1"): "reports_no_gain"}
    notes = world.fix_decoys(p, truth, ents, f, random.Random(1))
    assert p["decoys"][0] == ["S22", "reports_gain", "M6"] and len(notes) == 2
    pairs = [(s, o) for s, _, o in p["claims"] + p["decoys"]]
    assert len(pairs) == len(set(pairs)) and len(p["decoys"]) == 3
    assert all(world.fact_errors(tuple(d), ents, f) == [] for d in p["decoys"])
    assert ("S7", "M1") not in pairs or ["S7", "reports_no_gain", "M1"] in p["decoys"]


def test_too_few_subjects_is_an_entity_error() -> None:
    """The medicine 40 answer (22 Nov 2026): 100 treatments, no trial."""
    med = packs.field("medicine")
    ents = {f"T{i}": {"kind": "treatment"} for i in range(100)}
    errs = world.count_errors(ents, med, 80)
    assert errs == ["0 entities of kind trial: make at least 60 (about 80 asked)"]
    ents |= {f"R{i}": {"kind": "trial"} for i in range(60)}
    assert world.count_errors(ents, med, 80) == []


def test_one_entity_call_per_kind_others_first_and_distinct_id_prefixes() -> None:
    llm, med = packs.field("llm"), packs.field("medicine")
    assert world.kind_order(llm)[-1] == "study" and world.kind_order(med) == ["treatment", "trial"]
    assert {world.id_prefix(llm, k) for k in llm.kinds} == {"M", "MO", "B", "S"}
    assert world.id_prefix(med, "trial") == "TR"
    sch = world._schema_entities(med, "trial")["properties"]["entities"]["items"]["properties"]
    assert sch["kind"]["enum"] == ["trial"] and "drug_class" not in sch["attrs"]["properties"]
