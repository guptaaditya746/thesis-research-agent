import re

import pytest

from synth3.reference import draw_supported_studies
from synth3.world import draw_world
from synth3.write import TEXT_LEVELS, missing_facts, write_paper


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_every_planted_fact_is_where_it_says(SPEC, level):
    w = draw_world(SPEC, 1); studies, _ = draw_supported_studies(SPEC, w, 1, 40)
    assert all(missing_facts(write_paper(s, SPEC, level, 1), s, SPEC) == [] for s in studies)


def test_only_planted_numbers_and_the_year_are_digits(SPEC):
    w = draw_world(SPEC, 2); s = draw_supported_studies(SPEC, w, 2, 40)[0][0]
    p = write_paper(s, SPEC, "prose", 2)
    planted = [(pl.start, pl.end) for pl in p.placements]
    year = re.search(r"\((\d{4})\)", p.text).span(1)
    for m in re.finditer(r"\d+(?:\.\d+)?", p.text):
        assert m.span() == year or any(a <= m.start() and m.end() <= b for a, b in planted)
    assert not re.search(r"\b(ctrl|m1|m2|m3)\b", p.text)


def test_lower_is_better_claim_reads_reduces(SPEC):
    w = draw_world(SPEC, 3); studies, _ = draw_supported_studies(SPEC, w, 3, 40)
    s = next(s for s in studies if any(k.endswith("|m2") and v == "helps" for k, v in s.claims.items()))
    assert "reduces" in write_paper(s, SPEC, "table", 3).text


def test_unknown_text_level_is_refused(SPEC):
    s = draw_supported_studies(SPEC, draw_world(SPEC, 1), 1, 40)[0][0]
    with pytest.raises(ValueError, match="text level"):
        write_paper(s, SPEC, "split", 1)
