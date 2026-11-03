"""The word writer: the pinned model writes the names of each thing and the claim cue words, from the question
alone. It never reads a paper: the signatures below have no paper input. Every call is a DSPy `Step`."""
from __future__ import annotations

import dspy

from modelcall.pins import ORCH_ALIAS

from ..plan import WordList
from ..steps import Step

MIN_NAMES, MAX_NAMES = 20, 50


class WriteWords(dspy.Signature):
    """You write the names a thing goes by in research papers.
    Input `question`: the research question being asked of a set of papers.
    Input `thing`: one thing the question talks about (a short phrase).
    Output `names`: between 20 and 50 different names, spellings, abbreviations and short phrases that papers use
    for this thing or for the specific variants of it. One name per list entry. Plain names only, no explanations.
    Do not read or invent paper text."""
    question: str = dspy.InputField()
    thing: str = dspy.InputField()
    names: list[str] = dspy.OutputField()


class WriteMoreWords(dspy.Signature):
    """You add more names a thing goes by in research papers.
    Input `question`: the research question being asked of a set of papers.
    Input `thing`: one thing the question talks about (a short phrase).
    Input `already`: names already written for this thing.
    Output `names`: between 20 and 50 names in total for this thing: repeat none of `already` and add new names,
    spellings, abbreviations and short phrases that papers use for it. One name per list entry."""
    question: str = dspy.InputField()
    thing: str = dspy.InputField()
    already: list[str] = dspy.InputField()
    names: list[str] = dspy.OutputField()


class WriteCues(dspy.Signature):
    """You write the cue words authors use when they state a claim about a result.
    Input `question`: the research question being asked of a set of papers.
    Output `cues`: between 20 and 50 short phrases that authors write when they claim something about a result,
    for example a phrase that announces a finding, a comparison or a conclusion. One phrase per list entry."""
    question: str = dspy.InputField()
    cues: list[str] = dspy.OutputField()


def _tidy(names: list[str]) -> list[str]:
    """Stripped, non-empty, one per case-folded spelling, in reply order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in names:
        name = " ".join(str(raw).split())
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            out.append(name)
    return out


def write_words_report(question: str, things: list[str], *, step: Step | None = None,
                       more_step: Step | None = None, cue_step: Step | None = None) -> tuple[WordList, list[str]]:
    """(the word list, the things whose names stayed under 20 even after one retry)."""
    step = step or Step(WriteWords, "write_words")
    more_step = more_step or Step(WriteMoreWords, "write_more_words")
    cue_step = cue_step or Step(WriteCues, "write_cues")
    written: dict[str, list[str]] = {}
    short: list[str] = []
    for thing in things:
        names = _tidy(list(step(question=question, thing=thing).names))
        if len(names) < MIN_NAMES:
            more = more_step(question=question, thing=thing, already=names).names
            names = _tidy(names + list(more))
        if len(names) < MIN_NAMES:
            short.append(thing)
        written[thing] = names[:MAX_NAMES]
    cues = _tidy(list(cue_step(question=question).cues))[:MAX_NAMES]
    return WordList(things=written, cues=cues, written_by=ORCH_ALIAS, ontology_names={}), short


def write_words(question: str, things: list[str], *, step: Step | None = None,
                more_step: Step | None = None, cue_step: Step | None = None) -> WordList:
    """Names for each thing and the claim cues, written by the pinned `orch-model` alias."""
    return write_words_report(question, things, step=step, more_step=more_step, cue_step=cue_step)[0]
