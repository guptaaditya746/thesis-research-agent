"""The readable program's rules for the written answer: copied from the engine, pinned to it, standard library only."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import evidence.readable.rules
from evidence import written
from evidence.plan import with_answer
from evidence.readable import inputs_of
from evidence.readable.rules import common, written as rules_written
from evidence.readable.runview import answer_text, checked_view, read_run
from evidence.tests.readable_cases import item, stdlib_only
from evidence.tests.test_plan_run import make_plan
from evidence.tests.test_written_stage import clean_registry, written_run  # noqa: F401  (autouse fixture)
from evidence.written import NO_FACTS_TEXT, Fact, Sentence, WrittenReply, check_written, fact_text

ALLOWED = set(sys.stdlib_module_names) | {"__future__"}

GOOD = {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}
BAD = {"sentences": [{"text": "Up 987654%.", "says": "finding", "facts": [1]}]}


def rebuilt(root):
    ra = read_run(root)
    i = inputs_of(ra)
    return ra, rules_written.rebuild_answer(i.settings, i.facts, i.papers, i.model_text)


@pytest.mark.parametrize("replies, status", [([GOOD], "ok"), ([BAD, GOOD], "ok"), ([BAD, BAD], "failed")])
def test_the_written_answer_is_rebuilt_from_its_replies(tmp_path, replies, status):
    it = iter(replies)
    ra, view = rebuilt(written_run(tmp_path, lambda p: next(it)))
    assert view == checked_view(ra) and view["status"] == status
    assert rules_written.answer_lines({}, view, {}) == [view["answer_text"]]
    if status == "ok":
        assert rules_written.answer_lines({}, view, {}) == [answer_text(ra)]
        assert rules_written.notes_of(view) == [common.NOTE_WRITTEN]
    else:
        assert view["answer_text"] == "" and view["sentences"] == []
        assert rules_written.notes_of(view) == [common.FAILED_NOTE.format(problems="; ".join(view["tries"][-1]))]


def test_no_fact_means_the_fixed_text(tmp_path):
    nothing = with_answer(make_plan(things={"zz": ["no such words anywhere"], "yy": ["nor these"]}, measures=()),
                          "written", None)
    ra, view = rebuilt(written_run(tmp_path, lambda p: GOOD, plan=nothing))
    assert view == checked_view(ra) and view["answer_text"] == NO_FACTS_TEXT
    assert view["status"] == "no_facts" and rules_written.notes_of(view) == []


def test_the_inputs_name_every_writer_fact_and_its_links(tmp_path):
    ra, _ = rebuilt(written_run(tmp_path, lambda p: GOOD))
    i = inputs_of(ra)
    assert i.settings == {"kind": "written", "question": ra.answer["question"]}
    assert [p["n"] for p in i.papers] == [f["n"] for f in ra.answer["facts"]]
    assert i.papers[0]["fact"] == "F1" and i.model_text == [t["reply"] for t in ra.answer["tries"]]
    assert all({"paper", "item", "type"} <= set(f) for f in i.facts.values())


def test_fact_texts_rebuild_from_values():
    c = item("condition", {"label": "Method K", "role": "rag"})
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True})
    for value in (0.62, 1e-05, 10, 1250.0):
        m = item("measurement", {"value": value, "dataset": None}, {"condition": c.item_id, "metric": k.item_id},
                 exact="x" * 250)
        by_id = {i.item_id: i for i in (c, k, m)}
        facts = {"F1": {"paper": "S001", "item": m.item_id, "type": "measurement", "value": value, "dataset": None,
                        "condition": "F2", "metric": "F3", "quote": "x" * 250},
                 "F2": {"paper": "S001", "item": c.item_id, "type": "condition", "label": "Method K"},
                 "F3": {"paper": "S001", "item": k.item_id, "type": "metric", "name": "Yield",
                        "higher_is_better": True}}
        assert rules_written.fact_text_from_values(facts["F1"], facts) == fact_text(m, by_id)


def test_claims_and_missing_values_rebuild_from_values():
    a = item("author_claim", {"direction": "improves"})
    c = item("claim", {"subject": "Method K", "relation": "beats", "object": None, "strength": "strong"})
    m = item("measurement", {"value": None, "dataset": "Set A"})
    by_id = {i.item_id: i for i in (a, c, m)}
    facts = {"F1": {"paper": "S001", "item": a.item_id, "type": "author_claim", "direction": "improves",
                    "quote": "0.5"},
             "F2": {"paper": "S001", "item": c.item_id, "type": "claim", "subject": "Method K", "relation": "beats",
                    "object": None, "strength": "strong", "quote": "0.5"},
             "F3": {"paper": "S001", "item": m.item_id, "type": "measurement", "value": None, "dataset": "Set A",
                    "condition": None, "metric": None, "quote": "0.5"}}
    for key, it in (("F1", a), ("F2", c), ("F3", m)):
        assert rules_written.fact_text_from_values(facts[key], facts) == fact_text(it, by_id)


def test_the_checks_match_the_engine():
    facts = [Fact(n=1, item="m", paper="S001", type="measurement", text="Method K on Yield: 0.45, 1,250 cases")]
    plain = [f.model_dump() for f in facts]
    for text, says, cited in [("Up to 45% in 1 study.", "finding", [1]), ("Up by 12%.", "finding", [1]),
                              ("Better in S001.", "finding", [1]), ("Unknown.", "cannot_tell", [1]),
                              ("1,250 cases in 2026.", "finding", [9]), ("", "finding", [1])]:
        reply = WrittenReply(sentences=[Sentence(text=text, says=says, facts=cited)])
        assert rules_written.check_reply(reply.model_dump(), plain, "In 2026?") == check_written(reply, facts, "In 2026?")


def test_the_sentence_count_and_repeats_match_the_engine():
    facts = [Fact(n=1, item="m", paper="S001", type="measurement", text="Method K: 0.45")]
    plain = [f.model_dump() for f in facts]
    many = [Sentence(text=f"Point {i}.", says="finding", facts=[1]) for i in range(9)]
    twice = [Sentence(text="Same thing.", says="finding", facts=[1]),
             Sentence(text="same  THING.", says="finding", facts=[1])]
    for sentences in ([], many, twice, [Sentence(text="x" * 401, says="finding", facts=[1])]):
        reply = WrittenReply(sentences=sentences)
        assert rules_written.check_reply(reply.model_dump(), plain, "") == check_written(reply, facts, "")


def test_the_answer_text_and_rows_match_the_engine():
    facts = [Fact(n=1, item="a", paper="S003", type="claim", text="t"),
             Fact(n=2, item="b", paper="S010", type="claim", text="t")]
    reply = WrittenReply(sentences=[Sentence(text=" Both did. ", says="finding", facts=[2, 1, 2]),
                                    Sentence(text="Unknown.", says="cannot_tell", facts=[])])
    assert (rules_written.answer_text_and_rows(reply.model_dump(), [f.model_dump() for f in facts])
            == written.answer_text_of(reply, facts))


def test_the_copies_match_the_engine():
    assert (rules_written.MAX_SENTENCES, rules_written.MAX_SENTENCE_CHARS, rules_written.MAX_REPAIRS,
            rules_written.MAX_QUOTE, rules_written.NO_FACTS_TEXT) == (
        written.MAX_SENTENCES, written.MAX_SENTENCE_CHARS, written.MAX_REPAIRS, written.MAX_QUOTE,
        written.NO_FACTS_TEXT)
    assert [r.pattern for r in (rules_written.PAPER_ID, rules_written.THOUSANDS, rules_written.NUMBER)] == [
        r.pattern for r in (written.PAPER_ID, written.THOUSANDS, written.NUMBER)]
    assert rules_written.numbers_in("S001 had 1,250 and 0.5") == written.numbers("S001 had 1,250 and 0.5")


def test_a_rule_file_imports_only_the_standard_library():
    assert stdlib_only(Path(evidence.readable.rules.__file__).parent / "written.py") <= ALLOWED


def _hand_run(directions: dict | None):
    """A written run's answer built by hand: one paper whose metric item says higher is better, under a plan that
    says lower. `directions` is the key the stage writes (None: a run made before it was written)."""
    from evidence.readable.runview import RunAnswer
    from evidence.tests.readable_cases import case_protocol
    c = item("condition", {"label": "Method P", "role": "rag"})
    k = item("metric", {"name": "Error count", "canonical": "accuracy", "higher_is_better": True}, exact="Error count",
             start=20)
    m = item("measurement", {"value": 15, "dataset": None}, {"condition": c.item_id, "metric": k.item_id},
             exact="15", start=100)
    plan = with_answer(make_plan(direction="lower"), "written", None)
    facts, _ = written.fact_lines({"S001": [c, k, m]}, plan, 10_000)
    answer = {"question": plan.question, "facts": [f.model_dump() for f in facts], "tries": [{"reply": GOOD}]}
    if directions is not None:
        answer["directions"] = directions
    p = case_protocol("written", direction="lower")
    ra = RunAnswer(run=Path("case"), kind="written", protocol=p, roles=p.roles(), plan=plan, names={}, answer=answer,
                   items={"S001": [c, k, m]}, texts=None, record={}, outputs={}, inferred=None)
    return facts, ra


def test_the_program_rebuilds_a_fact_text_with_the_plans_direction():
    """Review round 1, engine-I1: the fact text takes the plan's direction; the program must rebuild the same."""
    facts, ra = _hand_run({"accuracy": False})
    i = inputs_of(ra)
    view = rules_written.rebuild_answer(i.settings, i.facts, i.papers, i.model_text)
    assert view["fact_texts"] == [facts[0].text] and "(lower is better)" in facts[0].text


def test_a_run_made_before_the_directions_were_recorded_rebuilds_with_the_papers_flag():
    """Old written runs told the writer the paper's own flag; their recorded fact texts must still rebuild."""
    _, ra = _hand_run(None)
    i = inputs_of(ra)
    view = rules_written.rebuild_answer(i.settings, i.facts, i.papers, i.model_text)
    assert view["fact_texts"] == ['Method P on Error count (higher is better): 15, no dataset named. Quote: "15"']


def test_the_stage_records_the_directions_it_told_the_writer(tmp_path):
    root = written_run(tmp_path, lambda p: GOOD)
    assert read_run(root).answer["directions"] == {"accuracy": True}
