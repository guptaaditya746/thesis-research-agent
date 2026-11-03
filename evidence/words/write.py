"""The word writer: the pinned model writes the names of each thing and the claim cue words, from the question
alone. It never reads a paper: the signatures below have no paper input. Every call is a DSPy `Step`."""
from __future__ import annotations

import dspy

from modelcall.dspy_lm import RecordedLM
from modelcall.pins import ORCH_ALIAS

from ..plan import WordList
from ..steps import Step, using

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
    Output `improves`: between 20 and 50 short phrases authors write when they claim the thing the question asks
    about makes the result better. Output `worsens`: the same for claims that it makes the result worse.
    Output `no_effect`: the same for claims that it makes no difference. One phrase per list entry."""
    question: str = dspy.InputField()
    improves: list[str] = dspy.OutputField()
    worsens: list[str] = dspy.OutputField()
    no_effect: list[str] = dspy.OutputField()


DIRECTIONS = ("no_effect", "worsens", "improves")   # the order a pack lists its claim patterns in


def cue_entry(direction: str, cue: str) -> str:
    """How a cue with its direction is kept in `WordList.cues` (a flat list of strings): "<direction>: <cue>"."""
    return f"{direction}: {cue}"


def split_cue(entry: str) -> tuple[str, str] | None:
    """(direction, cue) of a `WordList.cues` entry, or None for an entry without a known direction prefix."""
    direction, sep, cue = entry.partition(": ")
    return (direction, cue.strip()) if sep and direction in DIRECTIONS and cue.strip() else None


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


def write_words_report(question: str, things: list[str], *, lm: RecordedLM, step: Step | None = None,
                       more_step: Step | None = None, cue_step: Step | None = None) -> tuple[WordList, list[str]]:
    """(the word list, the things whose names stayed under 20 even after one retry). `lm` is the model the steps run
    on; it must be the pinned orchestrator alias (the list must not be written by the model that wrote the corpora)."""
    if lm.alias != ORCH_ALIAS:
        raise ValueError(f"the word list is written by {ORCH_ALIAS!r}, not {lm.alias!r}")
    with using(lm):
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
        out = cue_step(question=question)
        cues = [cue_entry(d, c) for d in DIRECTIONS for c in _tidy(list(getattr(out, d)))[:MAX_NAMES]]
    return WordList(things=written, cues=cues, written_by=lm.alias, ontology_names={}), short


def write_words(question: str, things: list[str], *, lm: RecordedLM, step: Step | None = None,
                more_step: Step | None = None, cue_step: Step | None = None) -> WordList:
    """Names for each thing and the claim cues (kept as "<direction>: <cue>"), written on `lm`."""
    return write_words_report(question, things, lm=lm, step=step, more_step=more_step, cue_step=cue_step)[0]
