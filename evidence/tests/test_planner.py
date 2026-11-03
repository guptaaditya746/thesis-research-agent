"""Planner steps with a fake model: no network."""
from __future__ import annotations

import json
import threading
import time

import pytest

from evidence import steps
from evidence.plan import WordList
from evidence.planner import MAIN_RULE_ID, NOT_PLANNED, check_plan, clarify, confirm_all, critic, decision_params
from evidence.planner import how_sentences, propose, set_rule, using
from evidence.planner.plan import OVERSELL_QUERY
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM

GOOD = "SELECT ?c WHERE { ?c a ev:Claim ; ev:number ?n . FILTER(?n >= $threshold) }"
BAD = "SELECT ?c WHERE { ?c a "
PLAIN = "SELECT ?c WHERE { ?c a ev:Claim }"


def words(question, things):
    return WordList(things={t: [t] for t in things}, cues=["improves"], written_by="fake", ontology_names={})


@pytest.fixture
def lm(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    replies: list[str] = []
    seen: list[str] = []

    def ask(prompt: str) -> str:
        seen.append(prompt)
        return replies.pop(0)

    steps.configure(RecordedLM("alias", ask, cache=JsonlCache(tmp_path / "calls.jsonl")))
    return replies, seen


def j(**kw):
    return json.dumps(kw)


def line(kind="effect", question="Does it help?", template=None):
    return {"question": question, "kind": kind, "template": template}


def script(replies, drafts, queries=None, decisions=None, things=("a",), rule="any_line"):
    """The replies of propose in order: lines, things, rule, decisions per line, queries, explanations."""
    replies.append(j(lines=drafts))
    replies.append(j(field="cs", measures=[], lower_is_better=[], things=list(things)))
    replies.append(j(rule=rule))
    for _ in drafts:
        replies.append(j(decisions=decisions if decisions is not None else [
            {"type": "threshold", "value": "0.05", "reason": "secret-noise-reason"}]))
    for q in queries or [GOOD] * len(drafts):
        replies.append(j(query=q))
    for d in drafts:
        if not d["template"]:
            replies.append(j(sentences=["It looks at claims.", "It keeps big numbers."]))


def make(replies, drafts, templates=None, question="Does it help?", **kw):
    """Replies are cached by prompt, so a second plan in one test needs its own question."""
    script(replies, drafts, **kw)
    return propose(question, write_words=words, templates=templates)[0]


def flags(*ids):
    return j(flags=[{"decision_id": i, "reason": "doubt"} for i in ids])


def test_clarify_cuts_to_two(lm):
    replies, _ = lm
    q = {"question": "Better at what?", "options": ["a", "b"]}
    replies.append(j(clarifications=[q, q, q]))
    assert clarify("Is it better?") == [q, q]


def test_oversell_line_added_and_not_removable(lm):
    replies, _ = lm
    plan = make(replies, [line("effect")])
    over = [x for x in plan.lines if not x.removable]
    assert [x.id for x in over] == ["oversell"] and over[0].template is None  # no saved template: built-in query
    assert "firm" in over[0].query and "hedged" not in over[0].query and "$threshold" in over[0].query
    assert plan.words.things == {"a": ["a"]}
    replies.clear()
    assert all(x.removable for x in make(replies, [line("inventory")], queries=[PLAIN], question="List them").lines)


def test_oversell_uses_the_saved_template_when_given(lm):
    replies, _ = lm
    plan = make(replies, [line("effect")], templates={"oversell": OVERSELL_QUERY})
    over = plan.lines[-1]
    assert over.template == "oversell" and over.query == OVERSELL_QUERY and not over.removable
    assert any(d.type == "threshold" for d in plan.decisions)  # the template's parameter has a decision


def test_critic_flags_one_or_two(lm):
    replies, seen = lm
    plan = make(replies, [line()])
    n = len(seen)
    # 0 flags refused, then 4 flags (d1 twice, d2 twice): duplicates merged, none dropped
    replies.extend([flags(), flags("d1", MAIN_RULE_ID, "d1", MAIN_RULE_ID)])
    dropped: list = []
    out = critic(plan, record=dropped.append)
    assert sum(d.flagged for d in out.decisions) == 2 and dropped == []
    assert len(seen) == n + 2
    assert "secret-noise-reason" not in "".join(seen[n:])  # the planner's reasons are not shown to the critic
    replies.append(flags("d1", MAIN_RULE_ID, "d1", "zz", MAIN_RULE_ID))
    out = critic(plan, record=dropped.append)
    assert sum(d.flagged for d in out.decisions) == 2
    other = make(replies, [line()], question="Another question?")
    replies.extend([flags(), flags()])
    critic(other, record=dropped.append)
    assert dropped and dropped[-1]["decision_id"] == ""  # nothing flagged after the retry is recorded


def test_confirm_all_confirms_flagged(lm):
    replies, _ = lm
    plan = make(replies, [line()])
    replies.append(flags("d1"))
    plan = critic(plan)
    assert plan.decisions[0].flagged and plan.decisions[0].flag_reason == "doubt" and not plan.ready()
    done = confirm_all(plan, "aditya")
    assert done.ready() and all(d.confirmed_by == "aditya" for d in done.decisions)


def test_run_disabled_until_ready(lm):
    replies, _ = lm
    plan = make(replies, [line()])
    first = plan.decisions[0].model_copy(update={"confirmed_by": "a"})
    assert not plan.ready()
    assert not plan.model_copy(update={"decisions": [first, *plan.decisions[1:]]}).ready()


def test_query_must_parse(lm):
    replies, seen = lm
    script(replies, [line("inventory")], queries=[BAD])
    replies.insert(replies.index(j(query=BAD)) + 1, j(query=GOOD))  # the repair reply
    plan, _ = propose("q", write_words=words)
    assert plan.lines[0].query == GOOD and any("expected one of" in s for s in seen)
    replies.clear()
    script(replies, [line("inventory", "other?")], queries=[BAD + "{"])
    replies.insert(replies.index(j(query=BAD + "{")) + 1, j(query=BAD + " "))
    plan, _ = propose("q2", write_words=words)
    assert NOT_PLANNED in plan.lines[0].question and plan.lines[0].query == ""


def test_placeholder_without_a_decision_is_refused(lm):
    replies, _ = lm
    q = "SELECT ?c WHERE { ?c ev:name $metric }"
    fixed = 'SELECT ?c WHERE { ?c ev:name "f1" }'
    script(replies, [line("inventory")], queries=[q])
    replies.insert(replies.index(j(query=q)) + 1, j(query=fixed))
    plan, _ = propose("q", write_words=words)
    assert plan.lines[0].query == fixed


def test_plan_checks_in_code(lm):
    replies, _ = lm
    # no line twice (one retry), no thing twice
    replies.extend([j(lines=[]), j(lines=[]), j(field="cs", measures=[], lower_is_better=[], things=[]), j(field="cs", measures=[], lower_is_better=[], things=[])])
    plan, _ = propose("q", write_words=words)
    problems = check_plan(plan, {})
    assert any("no evidence line" in p for p in problems) and any("no thing" in p for p in problems)
    # unknown template name: refused once, the retry names a real one
    replies.clear()
    replies.append(j(lines=[line(template="ghost")]))
    replies.append(j(lines=[line(template="real")]))
    replies.extend([j(field="cs", measures=[], lower_is_better=[], things=["a"]), j(rule="any_line"), j(decisions=[]), j(query=PLAIN)])
    plan, _ = propose("q3", write_words=words, templates={"real": "# What it finds.\n" + PLAIN})
    assert plan.lines[0].template == "real" and check_plan(plan, {"real": ""}) == []
    assert any("unknown template" in p for p in check_plan(plan, {"other": ""}))


def test_rule_is_from_the_fixed_set_and_a_decision(lm):
    replies, _ = lm
    plan = make(replies, [line()], rule="majority")
    row = next(d for d in plan.decisions if d.id == MAIN_RULE_ID)
    assert plan.main_rule == "majority" and row.value == "majority" and row.confirmed_by is None
    assert next(d for d in set_rule(plan, "all_lines", "ada").decisions if d.id == MAIN_RULE_ID).confirmed_by == "ada"
    with pytest.raises(ValueError):
        set_rule(plan, "whatever you like", "ada")


def test_changed_decision_changes_the_parameters_that_run(lm):
    replies, _ = lm
    plan = make(replies, [line()])
    query = plan.lines[0].query
    assert decision_params(plan, query)["threshold"] == 0.05
    changed = plan.model_copy(update={"decisions": [
        d.model_copy(update={"value": "0.2"}) if d.type == "threshold" else d for d in plan.decisions]})
    assert decision_params(changed, query)["threshold"] == 0.2


def test_how_is_sentences_not_code(lm):
    replies, _ = lm
    plan = make(replies, [line()])
    first = how_sentences(plan.lines[0], plan, None, ["It looks at claims."])
    assert first[0] == "It looks at claims." and any("0.05" in s for s in first)
    over = how_sentences(plan.lines[-1], plan, None)
    assert any("0.05" in s for s in over)
    assert not any("SELECT" in s or "{" in s or "$" in s for s in first + over)


def test_two_requests_record_on_their_own_model(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    got: dict[str, list[str]] = {"one": [], "two": []}

    def lm_for(name: str) -> RecordedLM:
        def ask(prompt: str) -> str:
            got[name].append(prompt)
            time.sleep(0.05)
            return j(clarifications=[])
        return RecordedLM("alias", ask, cache=JsonlCache(tmp_path / f"{name}.jsonl"))

    def request(name: str) -> None:
        with using(lm_for(name)):
            for i in range(3):
                clarify(f"question {name} {i}")

    threads = [threading.Thread(target=request, args=(n,)) for n in ("one", "two")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(got["one"]) == 3 and len(got["two"]) == 3
    assert all("question two" not in p for p in got["one"]) and all("question one" not in p for p in got["two"])


# --- Wave 2: the rule's own decision type, "how?" kept on the line, the measures among the things ---------------------

def test_rule_row_has_its_own_type_and_is_no_query_parameter(lm):
    replies, _ = lm
    plan = make(replies, [line()], rule="majority")
    row = next(d for d in plan.decisions if d.id == MAIN_RULE_ID)
    assert row.type == "main_rule" and check_plan(plan) == []
    assert "main_rule" not in decision_params(plan, plan.lines[0].query)


def test_fresh_line_keeps_its_how_sentences_in_the_plan(lm):
    replies, _ = lm
    plan = make(replies, [line()])
    assert plan.lines[0].how == ["It looks at claims.", "It keeps big numbers."]
    assert how_sentences(plan.lines[0], plan, None)[:2] == ["It looks at claims.", "It keeps big numbers."]


def test_measures_come_from_the_things_step_and_must_be_things(lm):
    replies, _ = lm
    replies.append(j(lines=[line("inventory")]))
    replies.append(j(field="cs", things=["a", "b", "m"], measures=["m", "ghost"], lower_is_better=["m"]))
    replies.extend([j(rule="any_line"), j(decisions=[]), j(query=PLAIN), j(sentences=["It lists."])])
    plan, _ = propose("Does a beat b on m?", write_words=words)
    assert plan.measures == ["m"] and list(plan.words.things) == ["a", "b", "m"]
    bad = plan.model_copy(update={"measures": ["zz"]})
    assert any("measure" in p for p in check_plan(bad))


# --- Fix round 1: the planner's lines address the graph by the plan's ids; every measure gets a direction -----------

SIDES_QUERY = ("SELECT DISTINCT ?paper WHERE { ?v a ev:Value ; kg:side ?s ; ev:onMetric ?m ; ev:inExperiment ?e . "
               "?m ev:name ?metric . ?e ev:inPaper ?p . ?p ev:name ?paper . VALUES ?s { $sides } VALUES ?metric { $metrics } }")


def test_a_query_keeping_the_run_params_is_accepted_and_the_query_step_sees_the_ids(lm):
    replies, seen = lm
    replies.append(j(lines=[line("inventory", "Which papers compare a and b on m?")]))
    replies.append(j(field="cs", things=["a", "b", "m"], measures=["m"], lower_is_better=["m"]))
    replies.extend([j(rule="any_line"), j(decisions=[]), j(query=SIDES_QUERY), j(sentences=["It lists papers."])])
    plan, _ = propose("Does a beat b on m?", write_words=words)
    assert plan.lines[0].query == SIDES_QUERY and check_plan(plan) == []
    query_prompt = next(p for p in seen if "choice_params" in p and "Which papers compare" in p)
    assert '["a", "b"]' in query_prompt and '["m"]' in query_prompt
    direction = next(d for d in plan.decisions if d.type == "direction")
    assert (direction.id, direction.value) == ("direction:m", "lower") and direction.confirmed_by is None
    assert "direction" not in decision_params(plan, SIDES_QUERY)
