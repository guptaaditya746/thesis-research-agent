import json
import pytest
from synth2.corpus import Settings, build_base, load_studies, load_truth
from synth2.family import KINDS, RELATION, make_family


@pytest.fixture(scope="module")
def family(tmp_path_factory):
    root = tmp_path_factory.mktemp("fam")
    build_base(root / "base", Settings("rag", 11, 20, "opposed", "table", exact=True))
    return root, make_family(root / "base")


def test_relations_hold(family):
    root, records = family
    assert [r["kind"] for r in records] == list(KINDS)
    for r in records:
        assert r["relation"] == RELATION[r["kind"]]
        assert (r["key_before"] != r["key_after"]) == (r["relation"] == "must_change")
        assert json.loads((root / r["kind"] / "variant.json").read_text(encoding="utf-8")) == r


def test_twin_keeps_untouched_papers_byte_identical(family):
    root, _ = family
    law = load_truth(root / "base")["law"]
    b = [lv["id"] for c in load_truth(root / "base")["conditions"] if c["id"] == law["condition"] for lv in c["levels"]][1]
    for s in load_studies(root / "base"):
        same = (root / "base" / "papers" / f"{s.id}.md").read_bytes() == (root / "twin" / "papers" / f"{s.id}.md").read_bytes()
        assert same == all(c.levels[law["condition"]] != b for c in s.cells)


def test_spun_keeps_every_count_and_base_is_honest(family):
    root, _ = family
    base = load_studies(root / "base")
    spun = load_studies(root / "spun")
    assert [s.cells for s in spun] == [s.cells for s in base]
    assert all(s.claim == "helps" for s in spun)
    assert not any(s.overclaims for s in base)
    assert [s.overclaims for s in spun] == [b.claim != "helps" for b in base]
    assert any(s.overclaims for s in spun)


def test_duplicate_adds_one_marked_paper(family):
    root, _ = family
    studies = load_studies(root / "duplicate")
    assert len(studies) == 21 and studies[-1].id == "S021" and studies[-1].duplicate_of == "S001"
    assert studies[-1].cells == studies[0].cells


def test_a_relation_that_fails_is_reported_not_hidden(tmp_path, monkeypatch):
    import synth2.family as fam
    build_base(tmp_path / "base", Settings("rag", 11, 20, "opposed", "table", exact=True))
    monkeypatch.setattr(fam, "pooled", lambda studies, recipe: fam.Answer("helps", None, {}, ()))
    with pytest.raises(ValueError, match="twin: relation must_change does not hold for seed 11"):
        make_family(tmp_path / "base")
