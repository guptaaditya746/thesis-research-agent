# Evidence-level research questions

A system that turns a research question about a corpus of scientific papers into a protocol, runs it, and answers from the extracted evidence rather than from the authors' conclusions.

## Language

**Research question**:
The natural-language question a user asks of a corpus, either picked from the question list or written by the user.
_Avoid_: query, prompt

**Question list**:
The fixed set of ready-made research questions offered to the user, all answerable from the same synthetic corpus.
_Avoid_: question bank, presets

**Question kind**:
The shape of a research question, which decides what evidence it needs: effect ("does X improve Y?"), inventory ("which metrics or conditions are used?"), consistency ("do the authors' claims match their numbers?") or best ("which condition scores highest on Z?").
_Avoid_: question type, template

**Protocol**:
The explicit, frozen plan that says which evidence to collect, how to extract and connect it, and how to synthesize the answer.
_Avoid_: plan, config, YAML

**Proposal**:
The step in which a protocol is built for a research question before it is frozen.
_Avoid_: protocol generation, draft

**Card**:
One methodological decision in a proposal, shown to the user with a drafted choice and its reason; each question kind has its own set of cards.
_Avoid_: setting, field, option

**Run trace**:
The step-by-step record of one run, showing every step and model call with its inputs, outputs, timing and errors, so a user can inspect how the answer was reached.
_Avoid_: log, timeline, debug output

**Checker**:
The assistant that reviews a proposal while the user edits it and lists problems, each marked serious or advisory.
_Avoid_: critic, validator, linter

**Waiver**:
A written reason the user gives to freeze a protocol despite a serious problem the checker found.
_Avoid_: override, skip, exception

**Consistency check**:
How a consistency question compares a claim with the numbers: by direction (agree or disagree) by default, or by size (how far apart, within an allowed margin).
_Avoid_: claim check, validation

**Extractor**:
A reusable component that finds one kind of evidence in a paper, such as conditions, metrics or measurements, by one method (patterns, a small tagger or a language model).
_Avoid_: parser, scraper

**Funnel**:
The order in which extractors are tried on a paper, cheapest first, with only the evidence still missing passed on to the next, costlier one.
_Avoid_: cascade, pipeline
