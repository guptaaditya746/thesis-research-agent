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


@pytest.mark.parametrize("a,b", [("GPT-3", "GPT-3.5"), ("Drug A", "Drug B"), ("BERT-base", "BERT-large"),
                                  ("Retrieval Augmented Model X1", "Retrieval Augmented Model Y1"),
                                  ("Long term cohort type 1a", "Long term cohort type 1b")])
def test_guard_keeps_different_things_apart(a, b):
    assert len(group_names(ms(a, b), {}).groups) == 2


def test_paper_alias_joins_with_quote():
    texts = {"p1": "compound 12 (hereafter Drug A) was given."}
    g = group_names(ms("compound 12", "Drug A", doc="p1"), texts)
    m = [m for m in g.matches if m.step == "alias"][0]
    assert "hereafter" in m.quote and len(g.groups) == 1


def test_greek_and_fullwidth_names_join():
    assert len(group_names(ms("α-blocker", "alpha blocker", "Ｂｅｔａ２", "Beta2"), {}).groups) == 2


def steps(g):
    return [(m.mention.name, m.step) for m in g.matches]


def test_every_match_records_its_step():
    assert steps(group_names(ms("Drug A", "drug-A"), {})) == [("Drug A", "clean"), ("drug-A", "clean")]
    for order in (("retrieval augmented model", "retrieval augmentd model"),
                  ("retrieval augmentd model", "retrieval augmented model")):
        assert {s for _, s in steps(group_names(ms(*order), {}))} == {"near"}
    texts = {"p1": "compound 12 (hereafter Drug A) was given."}
    assert {s for _, s in steps(group_names(ms("compound 12", "Drug A"), texts))} == {"alias"}


def test_seeded_name_alone_in_its_group_is_not_unresolved():
    g = group_names(ms("RAG"), {}, seed={"retrieval-augmented": ["RAG", "Retrieval Augmented Generation"]})
    assert g.unresolved == [] and steps(g) == [("RAG", "seed")]


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


def real(text: str, doc: str, *names: str) -> list[Mention]:
    """Mentions at their real offsets in `text` (each name's first occurrence after the previous one)."""
    out, at = [], 0
    for n in names:
        start = text.index(n, at)
        out.append(Mention(n, doc, start, start + len(n), "condition"))
        at = start + 1
    return out


def test_group_of_normalises_whitespace_and_falls_back_to_clean():
    g = group_names(ms("Drug A", "Zed"), {})
    assert g.group_of("Drug  A") == g.group_of(" Drug A\n") == "Drug A"
    assert g.group_of("drug-a") == "Drug A" and g.group_of("Nothing") is None


def test_alias_offsets_hold_after_ligatures():
    # casefold turns each "ﬁ" into "fi" (one char longer): the alias must still be found where the paper wrote it
    text = "ﬁ" * 40 + ". compound 12 (hereafter Drug A) was given."
    g = group_names(real(text, "p1", "compound 12", "Drug A"), {"p1": text})
    assert len(g.groups) == 1 and {m.step for m in g.matches} == {"alias"}


def test_shorter_mention_joins_only_at_the_alias_position():
    text = "The ﬁrst agent, compound 12 (hereafter Drug A), was given. Drug use was recorded."
    at_alias = real(text, "p1", "compound 12", "Drug A")
    elsewhere = Mention("Drug", "p1", text.index("Drug use"), text.index("Drug use") + 4, "condition")
    g = group_names([*at_alias, elsewhere], {"p1": text})
    assert g.group_of("Drug") != g.group_of("compound 12")
    here = Mention("Drug", "p1", text.index("Drug A"), text.index("Drug A") + 4, "condition")
    g = group_names([at_alias[0], here], {"p1": text})
    assert g.group_of("Drug") == g.group_of("compound 12")


def test_an_alias_joins_only_mentions_of_its_own_paper():
    t1 = "compound 12 (hereafter Drug A) was given."
    t2 = "Drug A was the comparator; compound 7 (hereafter Drug B) was new."
    mentions = [*real(t1, "p1", "compound 12", "Drug A"), *real(t2, "p2", "Drug A", "compound 7", "Drug B")]
    g = group_names(mentions, {"p1": t1, "p2": t2})
    p1_drug_a = next(m for m in g.matches if m.mention.doc == "p1" and m.mention.name == "Drug A")
    p2_drug_a = [m for m in g.matches if m.mention.doc == "p2" and m.mention.name == "Drug A"]
    assert p1_drug_a.step == "alias"
    assert all(m.group != p1_drug_a.group for m in p2_drug_a)
    assert len(g.groups) == 3 and len(set(g.groups)) == 3          # three distinct groups, none overwritten
    assert sorted(m.name for m in g.unresolved) == ["Drug A"]     # p2's own Drug A is alone
