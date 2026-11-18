"""The written answer's pure parts: the facts given to the writer (bearing on the plan, every paper first), the
code checks of a reply, the text with paper ids added by code, and the writer prompt's examples."""
from __future__ import annotations

import re
from typing import Any

from evidence.contract import Item, Span
from evidence.records import CLAIM
from evidence.tests.test_plan_run import make_plan
from evidence.tests.test_planner_subq import spec_name_hits
from evidence.written import (PROMPT, Fact, Sentence, WrittenReply, answer_text_of, check_written, fact_budget,
                              fact_lines, numbers, repair_input, writer_input)


def item(type: str, fields: dict[str, Any], links: dict[str, str] | None = None, paper: str = "S001",
         exact: str = "0.5", start: int = 0) -> Item:
    """An item with one span in papers/<paper>.md at `start`, quoting `exact`."""
    selector = {"file": f"papers/{paper}.md", "start": start, "end": start + len(exact), "exact": exact}
    return Item.build(type, fields, [Span(role="value", selector=selector)], links=links)


def plan():
    """The plan run's test plan: things rag and closed_book, measure accuracy (higher is better)."""
    return make_plan()


def paper_facts(p: str, k: int) -> list[Item]:
    """One condition (role rag), one metric (canonical accuracy, higher is better) and k measurements linked to them,
    all in paper `p`; the values 10 to 10+k-1 render with the same length for k <= 90."""
    c = item("condition", {"label": "Method K", "role": "rag"}, paper=p, exact="Method K")
    m = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True}, paper=p, exact="Yield",
             start=20)
    return [c, m, *(item("measurement", {"value": 10 + j, "dataset": None}, {"condition": c.item_id, "metric": m.item_id},
                         paper=p, exact=str(10 + j), start=100 + 10 * j) for j in range(k))]


def test_a_measurement_reads_its_condition_metric_and_direction():
    c = item("condition", {"label": "Method K", "role": "rag"})
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True})
    m = item("measurement", {"value": 0.62, "dataset": None}, {"condition": c.item_id, "metric": k.item_id},
             exact="0.62")
    facts, cut = fact_lines({"S001": [c, k, m]}, plan(), 10_000)
    assert [f.n for f in facts] == [1] and cut == {"pulled": 1, "kept": 1, "left_out": {}, "off_plan": 0}
    assert facts[0].text == 'Method K on Yield (higher is better): 0.62, no dataset named. Quote: "0.62"'


def test_a_fact_off_the_plan_is_left_out_and_counted():
    c = item("condition", {"label": "Other model", "role": "other"})
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True})
    m = item("measurement", {"value": 0.5, "dataset": None}, {"condition": c.item_id, "metric": k.item_id})
    facts, cut = fact_lines({"S001": [c, k, m]}, plan(), 10_000)
    assert facts == [] and cut["off_plan"] == 1


def test_a_measure_off_the_plan_and_missing_fields():
    c = item("condition", {"label": "Method K", "role": "rag"})
    k = item("metric", {"name": "Cost", "canonical": "cost"})
    off = item("measurement", {"value": 3, "dataset": "Small batches"}, {"condition": c.item_id, "metric": k.item_id})
    bare = item("measurement", {"dataset": "Small batches"}, {"condition": c.item_id}, start=40)
    facts, cut = fact_lines({"S001": [c, k, off, bare]}, make_plan(measures=()), 10_000)
    assert [f.text for f in facts] == ['Method K on Cost: 3, Small batches. Quote: "0.5"',
                                       'Method K on ?: ?, Small batches. Quote: "0.5"']
    facts, cut = fact_lines({"S001": [c, k, off]}, plan(), 10_000)
    assert facts == [] and cut["off_plan"] == 1


def test_an_author_claim_comes_with_a_paper_that_has_a_fact_on_the_plan():
    claim = item("author_claim", {"direction": "improves"}, exact="Method K improves the yield.", start=300)
    long_quote = item("author_claim", {"direction": "worsens"}, exact="x" * 250, start=400)
    on_plan = paper_facts("S001", 1)
    facts, cut = fact_lines({"S001": [*on_plan, claim, long_quote], "S002": [claim]}, plan(), 10_000)
    assert [(f.paper, f.type) for f in facts] == [("S001", "measurement"), ("S001", "author_claim"),
                                                 ("S001", "author_claim")]
    assert facts[1].text == 'The authors say: improves. Quote: "Method K improves the yield."'
    assert facts[2].text == f'The authors say: worsens. Quote: "{"x" * 200}"'
    assert cut == {"pulled": 3, "kept": 3, "left_out": {}, "off_plan": 1}


def test_every_paper_is_represented_when_the_budget_is_small():
    by_paper = {f"S{i:03d}": paper_facts(f"S{i:03d}", 10) for i in range(1, 41)}
    one = len(fact_lines({"S001": by_paper["S001"]}, plan(), 10_000)[0][0].text) + 16
    facts, cut = fact_lines(by_paper, plan(), budget=60 * one)
    assert {f.paper for f in facts} == set(by_paper) and len(facts) < 400
    assert cut["pulled"] == 400 and cut["kept"] == len(facts) and sum(cut["left_out"].values()) == 400 - len(facts)
    assert [f.n for f in facts] == list(range(1, len(facts) + 1))
    assert [f.paper for f in facts] == sorted(f.paper for f in facts)
    # 40 firsts, then 20 seconds before the budget stops: S001-S020 keep 2 facts, S021-S040 keep 1
    assert cut["left_out"] == {f"S{i:03d}": 8 if i <= 20 else 9 for i in range(1, 41)}


def test_a_plan_with_no_compared_thing_takes_the_any_role():
    c = item("condition", {"label": "Method K", "role": "any"})
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True})
    m = item("measurement", {"value": 0.5, "dataset": None}, {"condition": c.item_id, "metric": k.item_id})
    facts, cut = fact_lines({"S001": [c, k, m]}, make_plan(things={"accuracy": ["accuracy"]}), 10_000)
    assert [f.item for f in facts] == [m.item_id] and cut["off_plan"] == 0
    facts, cut = fact_lines({"S001": [c, k, m]}, plan(), 10_000)
    assert facts == [] and cut["off_plan"] == 1


def test_an_other_condition_is_the_comparison_point_of_an_on_plan_measurement():
    on = paper_facts("S001", 1)
    other = item("condition", {"label": "Usual method", "role": "other"}, exact="Usual method", start=60)
    cost = item("metric", {"name": "Cost", "canonical": "cost", "higher_is_better": False}, exact="Cost", start=70)
    point = item("measurement", {"value": 9, "dataset": None}, {"condition": other.item_id, "metric": on[1].item_id},
                 exact="9", start=500)
    off_measure = item("measurement", {"value": 7, "dataset": None}, {"condition": other.item_id, "metric": cost.item_id},
                       exact="7", start=510)
    alone = [item("condition", {"label": "Usual method", "role": "other"}, paper="S002"),
             item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True}, paper="S002", start=9)]
    alone.append(item("measurement", {"value": 9, "dataset": None},
                      {"condition": alone[0].item_id, "metric": alone[1].item_id}, paper="S002", start=30))
    facts, cut = fact_lines({"S001": [*on, other, cost, point, off_measure], "S002": alone}, plan(), 10_000)
    assert [f.item for f in facts] == [on[2].item_id, point.item_id] and cut["off_plan"] == 2
    assert facts[1].text == 'Usual method on Yield (higher is better): 9, no dataset named. Quote: "9"'


def test_the_quote_is_the_value_span_and_values_print_plainly():
    c = item("condition", {"label": "Method K", "role": "rag"}, exact="Method K")
    k = item("metric", {"name": "Yield", "canonical": "accuracy", "higher_is_better": True}, exact="Yield", start=20)
    sel = lambda start, exact: {"file": "papers/S001.md", "start": start, "end": start + len(exact), "exact": exact}
    m = Item.build("measurement", {"value": 0.00001, "dataset": None},
                   [Span(role="condition_label", selector=sel(0, "Method K")), Span(role="value", selector=sel(50, "1e-5"))],
                   links={"condition": c.item_id, "metric": k.item_id})
    facts, _ = fact_lines({"S001": [c, k, m]}, plan(), 10_000)
    assert facts[0].text == 'Method K on Yield (higher is better): 0.00001, no dataset named. Quote: "1e-5"'


def test_a_claim_reads_subject_relation_object_and_strength():
    claim = item(CLAIM, {"subject": "Method K", "relation": "shortens", "object": None, "strength": "firm"},
                 exact="Method K shortens the delay.", start=300)
    facts, _ = fact_lines({"S001": [*paper_facts("S001", 1), claim]}, plan(), 10_000)
    assert facts[1].type == CLAIM
    assert facts[1].text == 'Method K shortens ? (firm). Quote: "Method K shortens the delay."'


def test_the_budget_follows_the_model_limit():
    assert fact_budget(65_536) == 131_072


def test_checks_name_each_problem():
    facts = [Fact(n=1, item="m-1", paper="S001", type="measurement", text="Method K on Yield: 0.45")]
    s = lambda text, says="finding", f=(1,): WrittenReply(sentences=[Sentence(text=text, says=says, facts=list(f))])
    assert check_written(s("Up to 45% with Method K, in 1 study."), facts) == []
    assert check_written(s("Up by 12%."), facts) == ["sentence 1: the number 12 is in none of its facts"]
    assert check_written(s("Better.", f=(9,)), facts) == ["sentence 1: fact 9 is not listed"]
    assert check_written(s("Better in S001."), facts) == ["sentence 1: leave paper ids out; the code adds them"]
    assert check_written(s("No study.", "cannot_tell", ()), facts) == []
    assert check_written(s("Unknown.", "cannot_tell", (1,)), facts) == ["sentence 1: a cannot_tell sentence cites no fact"]
    assert check_written(WrittenReply(sentences=[]), facts) == ["give 1 to 8 sentences"]
    assert numbers("In S001 and S010, 1,250 cases and 0.45.") == [1250.0, 0.45]
    assert check_written(s("Yield fell by 0.45."), facts) == []   # the minus sign is not read


def test_a_number_of_the_question_may_be_repeated():
    facts = [Fact(n=1, item="m-1", paper="S001", type="measurement", text="Method K on Yield: 0.45")]
    reply = WrittenReply(sentences=[Sentence(text="No fact reports CIFAR-10 results.", says="cannot_tell", facts=[])])
    assert check_written(reply, facts, "Does Method K help on CIFAR-10?") == []
    assert check_written(reply, facts) == ["sentence 1: the number 10 is in none of its facts"]


def test_checks_name_the_other_problems():
    facts = [Fact(n=1, item="m-1", paper="S001", type="measurement", text="Method K on Yield: 0.45")]
    one = Sentence(text="Method K did better.", says="finding", facts=[1])
    reply = WrittenReply(sentences=[one, Sentence(text="  ", says="finding", facts=[1]),
                                    Sentence(text="x" * 401, says="finding", facts=[1]),
                                    Sentence(text="Method  K did better.", says="finding", facts=[1]),
                                    Sentence(text="Method K is fine.", says="finding", facts=[])])
    assert check_written(reply, facts) == ["sentence 2: empty", "sentence 3: longer than 400 characters",
                                           "sentence 4: said twice", "sentence 5: a finding cites at least one fact"]
    assert check_written(WrittenReply(sentences=[one] * 9), facts)[0] == "give 1 to 8 sentences"


def test_the_code_adds_the_papers():
    facts = [Fact(n=1, item="a", paper="S003", type="measurement", text="x 1"),
             Fact(n=2, item="b", paper="S010", type="measurement", text="x 2")]
    reply = WrittenReply(sentences=[Sentence(text="Method K did better.", says="finding", facts=[2, 1]),
                                    Sentence(text="No study measured cost.", says="cannot_tell", facts=[])])
    text, rows = answer_text_of(reply, facts)
    assert text == "Method K did better (S010, S003). No study measured cost."
    assert rows[0]["papers"] == ["S010", "S003"]
    assert rows[1] == {"text": "No study measured cost.", "says": "cannot_tell", "facts": [], "papers": []}


def test_the_writer_and_repair_inputs():
    facts = [Fact(n=1, item="a", paper="S003", type="measurement", text="x 1"),
             Fact(n=2, item="b", paper="S010", type="author_claim", text="y")]
    first = writer_input("Does Method K help?", facts)
    assert first == "Question: Does Method K help?\n\nFacts:\n[1] S003 x 1\n[2] S010 y"
    rejected = WrittenReply(sentences=[Sentence(text="Up 12.", says="finding", facts=[1])])
    assert repair_input(first, rejected, ["a", "b"]) == (
        f"{first}\n\nYour reply:\n{rejected.model_dump_json()}\n\nFix only these problems:\na\nb")


def test_the_prompt_uses_no_domain_name_and_holds_its_three_examples():
    text = PROMPT.read_text(encoding="utf-8")
    assert spec_name_hits(text) == []   # from test_planner_subq.py
    assert text.splitlines()[0].startswith("Write a short answer to the question")
    assert all(w in text for w in ("Method K", "Method P", "Usual method", "Error count", "45%", "cannot_tell"))
    # the examples show better, worse (more errors where lower is better) and no real difference
    assert all(w in text for w in ("higher Yield", "Method P gave more errors than the Usual method, 15 against 12.",
                                   "no real difference"))
    assert "number written in the question" in text


def test_the_prompt_examples_pass_the_code_checks():
    """Each example's output passes check_written against that example's own facts."""
    text = PROMPT.read_text(encoding="utf-8")
    examples = re.findall(r"Facts:\n(.*?)\nOutput:\n(\{.*?\})\n", text, re.S)
    assert len(examples) == 3
    for block, output in examples:
        facts = [Fact(n=int(n), item=f"m-{n}", paper=paper, type="measurement", text=rest)
                 for n, paper, rest in re.findall(r"^\[(\d+)\] (S\d{3}) (.*)$", block, re.M)]
        assert facts and check_written(WrittenReply.model_validate_json(output), facts) == []
