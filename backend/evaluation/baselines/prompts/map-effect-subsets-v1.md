Task: report the conclusion a system's answer amounts to (one overall effect, or an effect that depends on one
condition) and, for every corpus paper the answer relies on, the stance the answer attributes to that paper.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  passage-based system's answer (its text and the headers [paper id, start-end] of the passages it cites).

The question compares <<TREATMENT>> with <<CONTROL>>. The question metric is <<METRIC>>. A <<BETTER>> <<METRIC>>
with <<TREATMENT>> than with <<CONTROL>> is the improvement; a <<WORSE>> one is the worsening.

Candidate conditions, each as "condition id (what it is): level id = what the level means; level id = what the
level means":
<<CONDITIONS>>

Output:
- `verdict`: depends, supported, refuted, no_effect or insufficient.
- `condition`: for depends, the id of the one candidate condition the effect depends on; for every other verdict
  null.
- `sides`: for depends, one object per level of that condition (two objects), with `level` (the level id) and
  `effect`: supports (at that level <<TREATMENT>> gives a <<BETTER>> <<METRIC>> than <<CONTROL>>), contradicts (a
  <<WORSE>> one) or neutral (no real difference). For every other verdict an empty list.
- `untested`: every level the answer says no paper tested, written "condition id.level id"; an empty list when
  the answer names none.
- `studies`: one object per corpus paper the answer relies on, with `document` (a paper id from the list given)
  and `stance`: supports (with <<TREATMENT>> the paper shows a <<BETTER>> <<METRIC>> than with <<CONTROL>>),
  contradicts (with <<TREATMENT>> a <<WORSE>> <<METRIC>>) or neutral (no real difference).
- `answer_text`: the answer in a few sentences.

Verdicts (the same rule for every system):
- depends: the answer says the effect of <<TREATMENT>> is different at the two levels of one candidate condition
  (an improvement at one level and no real difference, or a worsening, at the other);
- supported: the answer says <<TREATMENT>> gives a <<BETTER>> <<METRIC>> overall and ties no difference to a
  candidate condition;
- refuted: the answer says <<TREATMENT>> gives a <<WORSE>> <<METRIC>> overall and ties no difference to a
  candidate condition;
- no_effect: the answer says the differences are too small to matter overall;
- insufficient: the answer does not answer the question.

Rules:
- Report only what the answer says. Add no knowledge of your own.
- Use only paper ids, condition ids and level ids from the lists given.
- The answer may name a level in its own words. Choose the level id whose meaning matches.
- When the answer ties a difference to something that is no candidate condition, give the overall verdict.

Example 1 (one overall effect)
The answer: In S001 and S002 <<TREATMENT>> gave a <<BETTER>> <<METRIC>> than <<CONTROL>>.
{"verdict": "supported", "condition": null, "sides": [], "untested": [],
 "studies": [{"document": "S001", "stance": "supports"}, {"document": "S002", "stance": "supports"}],
 "answer_text": "<<TREATMENT>> gave a <<BETTER>> <<METRIC>> than <<CONTROL>> in S001 and S002."}

Example 2 (the effect depends on a candidate condition; the answer names the levels in its own words)
The answer: For <<LEVEL_A1_NAME>> <<TREATMENT>> gave a <<BETTER>> <<METRIC>> (S001). For <<LEVEL_A2_NAME>> there
was no real difference (S002).
{"verdict": "depends", "condition": "<<COND_A>>",
 "sides": [{"level": "<<LEVEL_A1>>", "effect": "supports"}, {"level": "<<LEVEL_A2>>", "effect": "neutral"}],
 "untested": [],
 "studies": [{"document": "S001", "stance": "supports"}, {"document": "S002", "stance": "neutral"}],
 "answer_text": "<<TREATMENT>> helps for <<LEVEL_A1_NAME>> and makes no real difference for <<LEVEL_A2_NAME>>."}

Example 3 (papers disagree, but the answer ties the difference to no candidate condition)
The answer: S001 found a <<BETTER>> <<METRIC>> with <<TREATMENT>> and S002 a <<WORSE>> one, perhaps because S002
is older. Taken together <<TREATMENT>> still gave a <<BETTER>> <<METRIC>>.
{"verdict": "supported", "condition": null, "sides": [], "untested": [],
 "studies": [{"document": "S001", "stance": "supports"}, {"document": "S002", "stance": "contradicts"}],
 "answer_text": "Taken together <<TREATMENT>> gave a <<BETTER>> <<METRIC>>; S002 found a <<WORSE>> one."}

Example 4 (no result stated)
The answer: The papers study <<TREATMENT>> but the answer gives no result.
{"verdict": "insufficient", "condition": null, "sides": [], "untested": [], "studies": [],
 "answer_text": "The answer gives no result."}
