"""The llm field pack (DRAFT) on a tiny hand-written world: checks, seed + gold, materials. No model calls."""
from __future__ import annotations

from paperfactory import materials, packs, seed, world
from paperfactory.tests.test_field_words import LAW_TERMS
from paperfactory.tests.test_offline import ARG

LLM = packs.field("llm")


def _study(label: str, alt: str, year: int, bench: str) -> dict:
    return {"kind": "study", "label": label, "alt": [alt],
            "attrs": {"year": year, "model": "X1", "benchmark": bench, "setting": "zero-shot"}}


WORLD = {
    "field": "llm", "genre": "argument",
    "entities": {
        "M1": {"kind": "method", "label": "Lattice Echo prompting", "alt": ["Lattice Echo"], "attrs": {"family": "prompting"}},
        "M2": {"kind": "method", "label": "the Brindle adapter", "alt": ["Brindle"], "attrs": {"family": "fine-tuning"}},
        "M3": {"kind": "method", "label": "Quarrow decoding", "alt": ["Quarrow"], "attrs": {"family": "decoding"}},
        "M4": {"kind": "method", "label": "Tessel retrieval", "alt": ["Tessel"], "attrs": {"family": "retrieval"}},
        "X1": {"kind": "model", "label": "Tamsel-13B", "alt": [], "attrs": {"size": "13 billion parameters"}},
        "B1": {"kind": "benchmark", "label": "the Corvane-QA benchmark", "alt": ["Corvane-QA"],
               "attrs": {"task": "multi-step question answering"}},
        "B2": {"kind": "benchmark", "label": "the Mirrolet-Code benchmark", "alt": ["Mirrolet-Code"],
               "attrs": {"task": "code generation"}},
        "S1": _study("the Hadley 2020 study", "Hadley 2020", 2020, "B1"),
        "S2": _study("the Orlen 2021 study", "Orlen 2021", 2021, "B1"),
        "S3": _study("the Vasko 2022 study", "Vasko 2022", 2022, "B1"),
        "S4": _study("the Pruett 2023 study", "Pruett 2023", 2023, "B2"),
        "S5": _study("the Calder 2024 study", "Calder 2024", 2024, "B2"),
    },
    "papers": {
        "LLM-01": {"title_hint": "Does Lattice Echo prompting help on multi-step questions?",
                   "issue": "Whether Lattice Echo prompting raises scores on Corvane-QA.",
                   "thesis": "The reported gain does not hold up on re-runs.",
                   "claims": [["S2", "reports_gain", "M1"], ["S3", "reports_no_gain", "M1"],
                              ["S3", "fails_to_replicate", "S2"]],
                   "decoys": [["S2", "reports_gain", "M2"], ["S3", "reports_no_gain", "M3"],
                              ["S4", "fails_to_replicate", "S2"]],
                   "conflict": [["S2", "reports_gain", "M1"], ["S3", "reports_no_gain", "M1"]]},
        "LLM-02": {"title_hint": "Adapters and decoding for code generation",
                   "issue": "Whether the Brindle adapter or Quarrow decoding helps on Mirrolet-Code.",
                   "thesis": "Decoding changes help more than adapters on code generation.",
                   "claims": [["S4", "reports_drop", "M2"], ["S5", "reports_gain", "M3"],
                              ["S5", "fails_to_replicate", "S1"]],
                   "decoys": [["S4", "reports_drop", "M4"], ["S5", "reports_gain", "M4"],
                              ["S5", "fails_to_replicate", "S3"]]},
    },
}


def test_tiny_llm_world_passes_the_checks() -> None:
    assert world.check(WORLD, LLM, ARG, n_papers=2) == []
    assert world.decoy_warnings(WORLD, LLM) == []


def test_tiny_llm_world_seeds_with_gold_for_every_question_type() -> None:
    _, gold = seed.make(WORLD, LLM, per_question=2, seed=1)
    assert len(gold["facts"]) == 12
    assert {q["question_type"] for q in gold["questions"]} == {"pair", "subject_relation", "conflict"}
    assert all(q["gold"] for q in gold["questions"])
    q = next(q for q in gold["questions"] if q["id"] == "LLM-01:conflict")
    assert {"S2-reports_gain-M1", "S3-reports_no_gain-M1"} <= set(q["gold"])


def test_tiny_llm_world_materials_use_field_words() -> None:
    assert not LAW_TERMS.search(str(LLM.words)), LAW_TERMS.findall(str(LLM.words))
    for pid in WORLD["papers"]:
        idea, log = materials.materials(WORLD, LLM, ARG, pid)
        own = idea + log.split("## 5. Argument Plan")[0]    # section 5 is the genre pack's plan (it says "holdings")
        assert "{" not in log and not LAW_TERMS.search(own), LAW_TERMS.findall(own)
    _, log = materials.materials(WORLD, LLM, ARG, "LLM-01")
    assert "| the Orlen 2021 study | reported a gain from | Lattice Echo prompting |" in log
    assert "model: Tamsel-13B; benchmark: the Corvane-QA benchmark" in log
    assert "## 4. Conflict" in log
