"""The planner reads sub-questions through new versioned steps; with none, the old steps run unchanged."""
from __future__ import annotations

import json
import re

import pytest

from evidence import steps
from evidence.plan import WordList
from evidence.planner import propose
from evidence.planner.plan import LinesSig, ThingsSig
from evidence.planner.subq import LINES_SUB, THINGS_SUB, LinesSubSig, ThingsSubSig
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM
from synth3.questions import spec_names
from synth3.spec import SPECS, load_spec

GOOD = "SELECT ?c WHERE { ?c a ev:Claim ; ev:number ?n . FILTER(?n >= $threshold) }"


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


def flags(*ids):
    return j(flags=[{"decision_id": i, "reason": "doubt"} for i in ids])


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


def test_sub_questions_reach_the_lines_and_things_steps_only(lm):
    replies, seen = lm
    script(replies, [line()])
    plan, _ = propose("Does it help?", sub_questions=["Which papers measured it?"], write_words=words)
    assert plan.sub_questions == ["Which papers measured it?"] and plan.question == "Does it help?"
    with_sub = [p for p in seen if "Which papers measured it?" in p]
    assert len(with_sub) == 2 and all("sub_questions" in p for p in with_sub)


def test_without_sub_questions_the_old_steps_run(lm):
    replies, seen = lm
    script(replies, [line()])
    plan, _ = propose("Does it help?", write_words=words)
    assert plan.sub_questions == [] and not any("sub_questions" in p for p in seen)


def spec_name_hits(text: str) -> list[str]:
    names = {n for f in [*SPECS.glob("*.yaml"), *(SPECS / "drafts").glob("*.yaml")]
             for n in spec_names(load_spec(f.stem, f.parent))}
    assert names, "no spec names found: the check would pass on nothing"
    return sorted(n for n in names if re.search(rf"(?i)(?<!\w){re.escape(n)}(?!\w)", text))


@pytest.mark.parametrize("sig", [LinesSubSig, ThingsSubSig])
def test_examples_use_no_domain_name(sig):
    assert spec_name_hits(sig.__doc__) == []
    assert "Method K" in sig.__doc__ and "Usual method" in sig.__doc__


@pytest.mark.parametrize("base,sub", [(LinesSig, LinesSubSig), (ThingsSig, ThingsSubSig)])
def test_sub_signature_is_the_base_plus_sub_questions(base, sub):
    assert set(sub.input_fields) == set(base.input_fields) | {"sub_questions"}
    assert {k: v.annotation for k, v in sub.output_fields.items()} == {
        k: v.annotation for k, v in base.output_fields.items()}


def test_the_new_steps_have_their_own_names():
    assert (LINES_SUB.name, THINGS_SUB.name) == ("planner_lines_sub", "planner_things_sub")
