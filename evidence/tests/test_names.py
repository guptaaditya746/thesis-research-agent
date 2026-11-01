"""Name grouping (D38): spelling variants join, paper aliases join with their defining quote, near-matches never
merge different versions or letters, Greek and full-width forms fold, seed names group first."""
from __future__ import annotations

import pytest

from evidence.names import Mention, group_names


def ms(*names: str, doc: str = "p1") -> list[Mention]:
    return [Mention(n, doc, i * 20, i * 20 + len(n), "condition") for i, n in enumerate(names)]


def test_spelling_variants_join():
    g = group_names(ms("Drug A", "drug-A", "DRUG A"), {})
    assert len(g.groups) == 1 and g.unresolved == []


@pytest.mark.parametrize("a,b", [("GPT-3", "GPT-3.5"), ("Drug A", "Drug B"), ("BERT-base", "BERT-large")])
def test_guard_keeps_different_things_apart(a, b):
    assert len(group_names(ms(a, b), {}).groups) == 2


def test_paper_alias_joins_with_quote():
    texts = {"p1": "compound 12 (hereafter Drug A) was given."}
    g = group_names(ms("compound 12", "Drug A", doc="p1"), texts)
    m = [m for m in g.matches if m.step == "alias"][0]
    assert "hereafter" in m.quote and len(g.groups) == 1


def test_greek_and_fullwidth_names_join():
    assert len(group_names(ms("α-blocker", "alpha blocker", "Ｂｅｔａ２", "Beta2"), {}).groups) == 2


def test_every_match_records_its_step():
    g = group_names(ms("Drug A", "drug-A"), {})
    assert {m.step for m in g.matches} <= {"clean", "alias", "near", "seed", "model"}


def test_near_spelling_joins_and_group_key_is_most_frequent_form():
    g = group_names(ms("Retrieval Augmented Model", "Retrieval Augmented Model", "Retrieval-Augmented Models", "retrieval augmented model",
                       "retrieval augmentd model"), {})
    assert len(g.groups) == 1 and g.group_of("retrieval augmentd model") == "Retrieval Augmented Model"


def test_seed_groups_form_first_and_unmatched_names_are_unresolved():
    g = group_names(ms("RAG", "retrieval augmented generation", "Zed"), {},
                    seed={"retrieval-augmented": ["RAG", "Retrieval Augmented Generation"]})
    assert g.group_of("RAG") == "retrieval-augmented" == g.group_of("retrieval augmented generation")
    assert {m.step for m in g.matches} == {"seed"}
    assert [m.name for m in g.unresolved] == ["Zed"] and g.group_of("Zed") == "Zed"
