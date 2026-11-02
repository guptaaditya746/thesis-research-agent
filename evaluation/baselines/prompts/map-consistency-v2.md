Task: for every corpus paper a system's answer speaks about, report the authors' conclusion the answer attributes
to that paper and whether the answer says that conclusion agrees with the paper's reported results.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  passage-based system's answer (its text and the headers [paper id, start-end] of the passages it cites).

The authors' conclusion: <<CLAIM_TEXT>>

Output: `studies`, a list of objects with
- `paper`: a corpus paper id from the list given.
- `claim`: the authors' conclusion the answer attributes to this paper: "improves", "no_effect" or "worsens";
  null when the answer does not say what the authors conclude.
- `agrees`: true when the answer says the conclusion agrees with the paper's reported results, false when the
  answer says it disagrees with them, null when the answer does not say.

Rules:
- Report only what the answer says. Do not judge the agreement yourself from numbers the answer gives.
- One entry per paper the answer speaks about. Leave out papers the answer does not mention.
- Use only paper ids from the list given.

Example 1 (agreement stated)
The answer: In S001 the authors conclude that <<TREATMENT>> improves the <<METRIC>>, and their table confirms it.
{"studies": [{"paper": "S001", "claim": "improves", "agrees": true}]}

Example 2 (disagreement stated; a second paper with results but no stated conclusion)
The answer: S002 claims <<TREATMENT>> made no difference, yet its own table shows a <<BETTER>> <<METRIC>> by a wide
margin. S003 reports a <<BETTER>> <<METRIC>> with <<TREATMENT>>.
{"studies": [{"paper": "S002", "claim": "no_effect", "agrees": false},
 {"paper": "S003", "claim": null, "agrees": null}]}

Example 3 (conclusion given, agreement not stated)
The answer: The authors of S004 write that <<TREATMENT>> makes the <<METRIC>> worse than <<CONTROL>> does.
{"studies": [{"paper": "S004", "claim": "worsens", "agrees": null}]}
