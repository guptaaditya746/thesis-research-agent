import json
import re

import pytest

from synth2 import templedit
from synth2.realedit import CONTROL_WORDS, apply_edits, check_paper

INPUT = {
    "label": "Lee et al. (2021)", "treatment": {"name": "retrieval-augmented model"},
    "control": {"name": "closed-book model"},
    "system_names": {"treatment": "FindSys", "control": "the no-retrieval baseline"}, "benchmark": "TrivBench",
    "metric": "factual accuracy (number of questions answered correctly)",
    "claim_sentence": "Overall, the retrieval-augmented model lowers factual accuracy compared with the closed-book model.",
    "cells": [{"levels": [{"name": "rare-fact questions", "suggested": "questions on facts seldom seen in training"},
                          {"name": "full-scale generator", "suggested": "the large generator"}],
               "treatment_correct": 41, "treatment_total": 80, "control_correct": 30, "control_total": 79},
              {"levels": [{"name": "common-fact questions", "suggested": "questions about popular entities"},
                          {"name": "full-scale generator", "suggested": "the large generator"}],
               "treatment_correct": 55, "treatment_total": 90, "control_correct": 61, "control_total": 90}],
}
SOURCE = (
    "# Dense Readers at Scale\n\n## Abstract\n\nWe study dense readers. They work well on open questions.\n\n"
    "## Introduction\n\nReaders matter. A closed-book model answers from memory alone. We build on Vogel et al. (2020).\n\n"
    "## Results\n\nTable 2 lists the scores.\n\n| System | EM |\n|---|---|\n| No retrieval | 21.0 |\n| Ours | 44.1 |\n\n"
    "Without retrieval the reader fails. Ours is best.\n\n## Conclusion\n\nDense readers help. We release code.\n"
)


def build(source=SOURCE, inp=INPUT, claim="hurts", seed="s1"):
    edits = templedit.make_edits(source, inp, claim, seed)
    paper, inserted, problems = apply_edits(source, edits, inp["label"])
    return edits, paper, inserted, problems


def test_the_template_paper_passes_every_code_check_including_claim_rules():
    _, paper, inserted, problems = build()
    assert problems == []
    assert check_paper(paper, inserted, INPUT, {}, claim_rules=True) == []


def test_no_retrieval_sentences_and_rows_are_removed_and_the_rest_kept():
    _, paper, inserted, _ = build()
    rest = paper
    for t in sorted(inserted, key=len, reverse=True):
        rest = rest.replace(t.strip(), " ")
    assert not CONTROL_WORDS.search(rest)
    assert "Readers matter." in paper and "Ours is best." in paper and "| Ours | 44.1 |" in paper
    assert "| No retrieval |" not in paper


def test_the_planted_section_sits_before_the_conclusion_with_counts_and_wordings():
    _, paper, _, _ = build()
    section = paper[paper.index("21.0") if "21.0" in paper else 0:paper.index("## Conclusion")]
    for x in ("41", "80", "30", "79", "51.2", "38.0", "55", "90", "61", "61.1", "67.8"):
        assert re.search(rf"(?<![\d.]){re.escape(x)}(?![\d])", section), x
    assert "questions on facts seldom seen in training" in section.lower()
    assert paper.count("TrivBench") >= 2 and "rare-fact questions" not in paper.lower()


def test_the_claim_is_added_to_the_abstract_and_the_conclusion():
    _, paper, _, _ = build()
    abstract = paper.split("## Abstract")[1].split("##")[0]
    conclusion = paper.split("## Conclusion")[1]
    for part in (abstract, conclusion):
        assert "FindSys" in part or "retriev" in part.lower()


def test_edits_are_deterministic_for_a_seed_and_vary_across_seeds():
    assert build(seed="a")[0] == build(seed="a")[0]
    papers = {build(seed=str(i))[1] for i in range(8)}
    assert len(papers) >= 4


@pytest.mark.parametrize("claim,word", [("helps", "improve"), ("hurts", "hurt"), ("no_effect", "no clear")])
def test_the_claim_template_follows_the_direction(claim, word):
    texts = " ".join(templedit.claim_text(INPUT, claim, "firm", f"s{i}", "conclusion") for i in range(12)).lower()
    others = {"helps": "hurt", "hurts": "improve", "no_effect": "hurt"}[claim]
    assert word in texts and others not in texts


def test_a_hedged_claim_sentence_gives_a_hedged_template():
    hedged = {**INPUT, "claim_sentence": "The retrieval-augmented model may slightly lower factual accuracy."}
    assert templedit.confidence(hedged) == "hedged" and templedit.confidence(INPUT) == "firm"
    texts = " ".join(templedit.claim_text(hedged, "hurts", "hedged", f"s{i}", "abstract") for i in range(8)).lower()
    assert re.search(r"\b(may|might|appears?|seems?|suggests?)\b", texts)


def test_without_a_conclusion_heading_the_section_goes_at_the_end():
    src = SOURCE.split("## Conclusion")[0].rstrip() + "\n"
    _, paper, _, problems = build(source=src)
    assert problems == [] and paper.rstrip().endswith(paper.rstrip().split("\n")[-1])
    assert paper.index("41") > paper.index("Ours is best.")


def test_only_new_text_counts_as_inserted():
    _, _, inserted, _ = build()
    joined = " ".join(inserted)
    assert "We study dense readers" not in joined and "Dense readers help" not in joined


def test_checked_edits_redraw_until_no_mapped_word_or_copied_claim_is_left():
    mapping = {w: "Zz" for w in ("Finally", "Taken", "Retrieval", "Beyond")}
    edits, problems = templedit.checked_edits(SOURCE, INPUT, "hurts", "s1", mapping)
    paper, inserted, _ = apply_edits(SOURCE, edits, INPUT["label"])
    assert problems == [] and check_paper(paper, inserted, INPUT, mapping, claim_rules=True) == []


def wordings(inp):
    return {lv.get("suggested") or lv["name"] for c in inp["cells"] for lv in c["levels"]}


@pytest.mark.parametrize("seed", ["a", "b", "c", "d"])
def test_each_level_wording_appears_once_in_the_section(seed):
    section = templedit.planted_section(INPUT, "hurts", seed, 3)
    for w in wordings(INPUT):
        assert section.count(w) == 1, w


def test_rows_are_labelled_by_the_wording_that_differs():
    rows = [ln for ln in templedit.planted_section(INPUT, "hurts", "a", 3).split("\n") if ln.startswith("| ")][1:]
    assert rows[0].startswith("| questions on facts seldom seen in training |")
    assert rows[1].startswith("| questions about popular entities |")


def test_a_single_cell_row_is_labelled_by_the_benchmark():
    one = {**INPUT, "cells": INPUT["cells"][:1]}
    section = templedit.planted_section(one, "hurts", "a", 3)
    assert "| TrivBench | 41 / 80 (51.2%) | 30 / 79 (38.0%) |" in section
    for w in wordings(one):
        assert section.count(w) == 1, w


def test_the_text_after_the_table_gives_the_gaps_not_the_counts_again():
    section = templedit.planted_section(INPUT, "hurts", "a", 3)
    after = section.split("|\n\n")[-1]
    assert "13.2 points" in after and "6.7 points" in after and "41" not in after
    tie = {**INPUT, "cells": [{**INPUT["cells"][0], "control_correct": 41, "control_total": 80}]}
    assert "level" in templedit.planted_section(tie, "hurts", "a", 3).split("|\n\n")[-1]


@pytest.mark.parametrize("claim", ["helps", "hurts", "no_effect"])
@pytest.mark.parametrize("conf", ["firm", "hedged"])
def test_no_claim_sentence_is_used_twice_in_a_paper(claim, conf):
    for i in range(12):
        texts = [templedit.claim_text(INPUT, claim, conf, f"s{i}", w).lower()
                 for w in ("abstract", "section", "conclusion")]
        cores = [t.split("that ", 1)[-1] if t.startswith(("we also", "an analysis", "our analysis")) else t
                 for t in texts]
        cores = [c[len("finally, "):] if c.startswith("finally, ") else c for c in cores]
        assert len(set(cores)) == 3, cores


def test_a_framed_claim_drops_its_opening_phrase():
    texts = [templedit.claim_text(INPUT, c, "firm", f"s{i}", w).lower() for c in ("helps", "hurts", "no_effect")
             for i in range(20) for w in ("abstract", "conclusion")]
    assert not [t for t in texts if re.search(r"(that|finally,) (in short|taken together),", t)]


def test_write_edits_writes_one_edits_file_per_study(edit_base, tmp_path):
    truth = {"studies": [{"id": "S001", "claim": "helps"}]}
    grid = tmp_path / "grid"
    grid.mkdir()
    (grid / "ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
    done = templedit.write_edits(edit_base, grid)
    assert [d["study"] for d in done] == ["S001"]
    edits = json.loads((edit_base / "edits" / "S001.json").read_text(encoding="utf-8"))
    assert edits["title"] and edits["insert_after"] and done[0]["problems"] != []   # no `suggested`: name verbatim
