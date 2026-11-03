"""Planner steps with a fake model: no network."""
from __future__ import annotations

import json

import pytest

from evidence import steps
from evidence.plan import WordList
from evidence.planner import NOT_PLANNED, clarify, confirm_all, critic, propose
from evidence.steps import configure
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM

GOOD = "SELECT ?c WHERE { ?c a ev:Claim }"
BAD = "SELECT ?c WHERE { ?c a "


def words(question, things, *, step=None):
    return WordList(things={t: [t] for t in things}, cues=["improves"], written_by="fake", ontology_names={})


@pytest.fixture
def lm(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    replies: list[str] = []
    seen: list[str] = []

    def ask(prompt: str) -> str:
        seen.append(prompt)
        return replies.pop(0)

    configure(RecordedLM("alias", ask, cache=JsonlCache(tmp_path / "calls.jsonl")))
    return replies, seen


def proposal(lines, things=("retrieval",)):
    return json.dumps({"field": "cs", "lines": lines, "main_rule": "majority of lines",
                       "decisions": [{"type": "threshold", "value": "0.01", "reason": "secret-noise-reason"},
                                     {"type": "include", "value": "all", "reason": "small corpus"}],
                       "things": list(things)})


def line(kind="effect", query=GOOD):
    return {"question": "Does it help?", "kind": kind, "template": None, "query": query}


def flags(*ids):
    return json.dumps({"flags": [{"decision_id": i, "reason": "doubt"} for i in ids]})


def test_clarify_cuts_to_two(lm):
    replies, _ = lm
    q = {"question": "Better at what?", "options": ["a", "b"]}
    replies.append(json.dumps({"clarifications": [q, q, q]}))
    assert clarify("Is it better?") == [q, q]


def test_oversell_line_added_and_not_removable(lm):
    replies, _ = lm
    replies.append(proposal([line("effect")]))
    plan = propose("Does retrieval help?", write_words=words)
    over = [x for x in plan.lines if not x.removable]
    assert len(over) == 1 and over[0].id == "oversell"
    assert plan.words.things == {"retrieval": ["retrieval"]}
    replies.append(proposal([line("inventory")]))
    assert all(x.removable for x in propose("List systems", write_words=words).lines)


def test_critic_flags_one_or_two(lm):
    replies, seen = lm
    replies.append(proposal([line()]))
    plan = propose("q", write_words=words)
    # 0 flags refused, then 4 flags clamped to 2; the other 2 are dropped and recorded
    replies.extend([flags(), flags("d1", "d2", "d1", "d2")])
    dropped: list = []
    out = critic(plan, record=dropped.append)
    assert [d.flagged for d in out.decisions] == [True, True] and len(dropped) == 2
    assert len(seen) == 3  # propose + two critic calls (refused once, retried once)
    assert "secret-noise-reason" not in seen[1] + seen[2]  # the planner's reasons are not shown to the critic


def test_confirm_all_confirms_flagged(lm):
    replies, _ = lm
    replies.extend([proposal([line()]), flags("d1")])
    plan = critic(propose("q", write_words=words))
    assert plan.decisions[0].flagged and plan.decisions[0].flag_reason == "doubt" and not plan.ready()
    done = confirm_all(plan, "aditya")
    assert done.ready() and all(d.confirmed_by == "aditya" for d in done.decisions)


def test_run_disabled_until_ready(lm):
    replies, _ = lm
    replies.append(proposal([line()]))
    plan = propose("q", write_words=words)
    first = plan.decisions[0].model_copy(update={"confirmed_by": "a"})
    assert not plan.ready()
    assert not plan.model_copy(update={"decisions": [first, *plan.decisions[1:]]}).ready()


def test_query_must_parse(lm):
    replies, seen = lm
    replies.extend([proposal([line(query=BAD)]), json.dumps({"fixed_query": GOOD})])
    plan = propose("q", write_words=words)
    assert plan.lines[0].query == GOOD and len(seen) == 2
    replies.extend([proposal([line(query=BAD + "{")]), json.dumps({"fixed_query": BAD + " "})])  # new query: not cached
    plan = propose("q2", write_words=words)
    assert NOT_PLANNED in plan.lines[0].question and plan.lines[0].query == ""
