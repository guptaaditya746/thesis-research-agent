import re

import pytest

from jsonio import sha256_hex
from synth3.corpus import build_folder
from synth3.realwrite import (ABSTRACT_LEADS, CAPTIONS, CLOSERS, CONCLUSION_LEADS, HEADINGS, INTROS, claims_block,
                              planted_section)
from synth3.tests.conftest import approved, supported
from synth3.write import TEXT_LEVELS, _claim_sentence, _fact_claim, write_paper

PINS = {
    "table": ("demo3-523375b3", "3ce6684e45bfdd7dc9adb8f4a24d61cd8cea587b1e1f3f0851309397f88bab7d"),
    "prose": ("demo3-a181434a", "80ffdfb6e898379b82f2a49d678b231b4e59d525d8a103fc9123e0e5f7e639ee"),
}   # (corpus id, sha256 of ground_truth.json + manifest.json)


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_template_folders_unchanged_by_the_refactors(tmp_path, SPEC, level):
    out = tmp_path / level
    cid = build_folder(out, SPEC, approved(SPEC, 1), 40, level)
    digest = sha256_hex((out / "ground_truth.json").read_bytes() + (out / "manifest.json").read_bytes())
    assert (cid, digest) == PINS[level]


@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_section_plants_the_same_values_as_the_template(SPEC, level):
    s = supported(SPEC, 1)[0]
    block = planted_section(s, SPEC, level, "x", 3)
    template = write_paper(s, SPEC, level, 1)
    got = {p.fact: block.text[p.start:p.end] for p in block.placements}
    want = {p.fact: template.text[p.start:p.end] for p in template.placements if ".claim." not in p.fact}
    assert got == want and block.text == block.text.strip()


def test_claim_blocks_hold_the_exact_claim_sentences(SPEC):
    s = supported(SPEC, 2)[0]
    for place in ("abstract", "conclusion"):
        block = claims_block(s, SPEC, place, "x")
        got = {p.fact: block.text[p.start:p.end] for p in block.placements}
        assert got == {_fact_claim(s.id, k, place): _claim_sentence(SPEC, k, w) for k, w in s.claims.items()}
    a, c = (claims_block(s, SPEC, p, "x").text for p in ("abstract", "conclusion"))
    assert a not in c and c not in a


def test_only_planted_numbers_and_the_table_number_are_digits(SPEC):
    s = supported(SPEC, 3)[0]
    block = planted_section(s, SPEC, "prose", "x", 3)
    spans = [(p.start, p.end) for p in block.placements]
    for m in re.finditer(r"\d+(?:\.\d+)?", block.text):
        assert any(a <= m.start() and m.end() <= b for a, b in spans)
    assert not re.search(r"\b(ctrl|m1|m2|m3|S\d{3})\b", block.text)


def test_wording_varies_with_the_seed(SPEC):
    s = supported(SPEC, 1)[0]
    assert len({planted_section(s, SPEC, "table", f"x{k}", 3).text.split("\n")[0] for k in range(12)}) >= 2


def test_template_lists_are_words_only_and_long_enough():
    for lst in (HEADINGS, INTROS, CAPTIONS, CLOSERS, ABSTRACT_LEADS, CONCLUSION_LEADS):
        assert len(lst) >= 3 and len(set(lst)) == len(lst)
        assert not any(re.search(r"\d", t.replace("{table_no}", "")) for t in lst)
    assert not set(ABSTRACT_LEADS) & set(CONCLUSION_LEADS)
