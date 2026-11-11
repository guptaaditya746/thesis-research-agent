import re
import pytest
from synth2.recipe import load_recipe
from synth2.world import draw_law, draw_studies
from synth2.write import CLAIMS, TEXT_LEVELS, Paper, missing_facts, write_paper

R = load_recipe("rag")
LAW = draw_law(R, 5, "opposed")
STUDIES = draw_studies(R, LAW, 5, 20)


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_every_planted_fact_is_where_the_placement_says(level):
    for s in STUDIES:
        p = write_paper(s, R, level, 5)
        assert missing_facts(p, s) == []
        counts = [pl for pl in p.placements if re.search(r"\.c\d+\.", pl.fact)]
        assert len(counts) == 4 * len(s.cells)
        first = s.cells[0]
        by = {pl.fact: p.text[pl.start:pl.end] for pl in p.placements}
        assert by[f"{s.id}.c0.k_t"] == str(first.k_t) and by[f"{s.id}.c0.n_c"] == str(first.n_c)
        claim = CLAIMS[s.claim].format(t=R.treatment.label, c=R.control.label, m=R.metric)
        assert by[f"{s.id}.claim.abstract"] == claim == by[f"{s.id}.claim.conclusion"]


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_layout_and_no_stray_digits(level):
    s = STUDIES[0]
    p = write_paper(s, R, level, 5)
    assert [h for h in re.findall(r"^## (.+)$", p.text, flags=re.M)] == ["Abstract", "Setup", "Results", "Conclusion"]
    assert "\r" not in p.text
    covered = set()
    for pl in p.placements:
        covered.update(range(pl.start, pl.end))
    head_end = p.text.index("\n")
    stray = [i for i, ch in enumerate(p.text) if ch.isdigit() and i not in covered and i > head_end]
    assert stray == []
    assert all(lv.id not in p.text.split() for c in R.conditions for lv in c.levels)


def test_levels_differ_as_specified():
    s = next(x for x in STUDIES if len(x.cells) == 2)
    table, prose, split = (write_paper(s, R, lv, 5).text for lv in TEXT_LEVELS)
    assert "| Subset | System | Correct | Total |" in table and "| Subset | System | Correct | Total |" in split
    assert "|" not in prose and f"{s.cells[0].k_t} of {s.cells[0].n_t} {R.unit}" in prose
    results = split.split("## Results")[1].split("## Conclusion")[0]
    assert "Subset A" in results and "Subset B" in results
    assert all(lv.name not in results for c in R.conditions for lv in c.levels)


def test_missing_facts_catches_a_changed_number():
    s = STUDIES[0]
    p = write_paper(s, R, "table", 5)
    pl = next(x for x in p.placements if x.fact == f"{s.id}.c0.k_t")
    broken = Paper(p.study, p.text[:pl.start] + "9" * (pl.end - pl.start) + p.text[pl.end:], p.placements)
    assert missing_facts(broken, s) == [f"{s.id}.c0.k_t"]


def test_same_input_same_bytes():
    assert write_paper(STUDIES[3], R, "prose", 5) == write_paper(STUDIES[3], R, "prose", 5)
