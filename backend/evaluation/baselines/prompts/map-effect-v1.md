Task: report the label a system's answer amounts to and, for every corpus paper the answer relies on, the stance
the answer attributes to that paper.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  retrieve-then-answer system's answer (its text and the headers [paper id, start-end] of the passages it cites).

The question metric is <<METRIC>>. A <<BETTER>> <<METRIC>> is the improvement; a <<WORSE>> <<METRIC>> is the
worsening.

Output:
- `label`: supported, refuted, mixed, no_effect or insufficient.
- `studies`: one object per corpus paper the answer relies on, with `document` (a paper id from the list given)
  and `stance`: supports (with retrieval the paper shows a <<BETTER>> <<METRIC>>), contradicts (with retrieval a
  <<WORSE>> <<METRIC>>) or neutral (no real difference).
- `answer_text`: the answer in a few sentences.

Labels (the same rule for every system):
- supported: at least one paper shows retrieval giving a <<BETTER>> <<METRIC>> and none shows a <<WORSE>> one;
- refuted: at least one paper shows retrieval giving a <<WORSE>> <<METRIC>> and none shows a <<BETTER>> one;
- mixed: some papers show a <<BETTER>> <<METRIC>> with retrieval and others a <<WORSE>> one;
- no_effect: the papers show only differences too small to matter;
- insufficient: the answer does not answer the question.

Rules:
- Report only what the answer says. Add no knowledge of your own.
- Use only paper ids from the list given.

Example 1 (an improvement)
The answer: In S001 retrieval gave a <<BETTER>> <<METRIC>> than the model without retrieval.
{"label": "supported", "studies": [{"document": "S001", "stance": "supports"}],
 "answer_text": "Retrieval improved <<METRIC>> in S001."}

Example 2 (one paper each way: mind which direction is the improvement)
The answer: S002: <<METRIC>> was <<WORSE>> with retrieval. S003: <<METRIC>> was <<BETTER>> with retrieval.
{"label": "mixed", "studies": [{"document": "S002", "stance": "contradicts"}, {"document": "S003", "stance": "supports"}],
 "answer_text": "Retrieval worsened <<METRIC>> in S002 and improved it in S003."}

Example 3 (no result stated)
The answer: The papers study retrieval but the answer gives no result.
{"label": "insufficient", "studies": [], "answer_text": "The answer gives no result."}
