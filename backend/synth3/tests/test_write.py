import re

import pytest

from synth3.reference import draw_supported_studies
from synth3.world import draw_world
from synth2.write import Paper, Placement
from synth3.write import TEXT_LEVELS, missing_facts, write_paper


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_every_planted_fact_is_where_it_says(SPEC, level):
    w = draw_world(SPEC, 1); studies, _ = draw_supported_studies(SPEC, w, 1, 40)
    assert all(missing_facts(write_paper(s, SPEC, level, 1), s, SPEC) == [] for s in studies)


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_only_planted_numbers_and_the_year_are_digits(SPEC, level):
    w = draw_world(SPEC, 2); s = draw_supported_studies(SPEC, w, 2, 40)[0][0]
    p = write_paper(s, SPEC, level, 2)
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


def _edit(paper, fact, new):
    """A copy of the paper where the span of `fact` holds `new`; later placements shift."""
    pl = next(x for x in paper.placements if x.fact == fact)
    text = paper.text[:pl.start] + new + paper.text[pl.end:]
    shift = len(new) - (pl.end - pl.start)
    out = []
    for x in paper.placements:
        if x.fact == fact:
            out.append(Placement(x.fact, x.start, x.end + shift))
        elif x.start >= pl.end:
            out.append(Placement(x.fact, x.start + shift, x.end + shift))
        else:
            out.append(x)
    return Paper(paper.study, text, tuple(out))


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_missing_facts_detects_each_kind_of_damage(SPEC, level):
    studies, _ = draw_supported_studies(SPEC, draw_world(SPEC, 1), 1, 40)
    s = next(s for s in studies if any(c.results[0].mean is not None for c in s.cells)
             and any(c.results[0].k is not None for c in s.cells))
    p = write_paper(s, SPEC, level, 1)
    assert missing_facts(p, s, SPEC) == []
    count = next(c for c in s.cells if c.results[0].k is not None)
    value = next(c for c in s.cells if c.results[0].mean is not None)
    k_fact = f"{s.id}.c{count.index}.{count.results[0].arm}.k"
    mean_fact = f"{s.id}.c{value.index}.{value.results[0].arm}.mean"
    claim_fact = next(pl.fact for pl in p.placements if pl.fact.endswith(".conclusion"))
    spans = {pl.fact: p.text[pl.start:pl.end] for pl in p.placements}
    bumped = spans[k_fact][:-1] + str((int(spans[k_fact][-1]) + 1) % 10)
    cases = {
        "dropped": (Paper(p.study, p.text, tuple(x for x in p.placements if x.fact != k_fact)), k_fact),
        "digit": (_edit(p, k_fact, bumped), k_fact),
        "value": (_edit(p, mean_fact, spans[mean_fact] + "9"), mean_fact),
        "claim": (_edit(p, claim_fact, spans[claim_fact].replace("Overall", "Mostly")), claim_fact),
        "setting": (_edit(p, f"{s.id}.setting", "Nowhere"), f"{s.id}.setting"),
    }
    for name, (damaged, fact) in cases.items():
        assert fact in missing_facts(damaged, s, SPEC), name


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_an_arm_label_never_follows_the(SPEC, level):
    # "Overall, the Cardivel lowers ... compared with the Standard care" was the clearest synthetic cue
    from synth3.realwrite import claims_block, planted_section
    studies = draw_supported_studies(SPEC, draw_world(SPEC, 1), 1, 40)[0]
    labels = "|".join(re.escape(a.label) for a in SPEC.arms)
    for s in studies[:10]:
        texts = [write_paper(s, SPEC, level, 1).text, planted_section(s, SPEC, level, "x", 3).text,
                 *(claims_block(s, SPEC, p, "x").text for p in ("abstract", "conclusion"))]
        for t in texts:
            assert not re.search(rf"\bthe ({labels})\b", t, re.I), t
