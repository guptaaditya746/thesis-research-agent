Task: list every limitation a system's answer states, with the thing it is about, its category, and the corpus
papers the answer names it for.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  passage-based system's answer (its text and the headers [paper id, start-end] of the passages it cites).

Categories (write exactly one of these):
<<CATEGORIES>>

Output: `entries`, a list of objects with
- `thing`: the compared thing the limitation is about, written exactly as the answer writes it; null when the
  limitation is about a study as a whole.
- `category`: the category of the limitation, one of the list above.
- `papers`: the corpus paper ids the answer names this limitation for, from the list given.

Rules:
- Report only what the answer says. Add no limitations of your own knowledge.
- One entry per thing and category; a limitation the answer states for several papers is one entry with them all.
- A limitation that fits none of the categories is left out.
- Use only paper ids from the list given.
- When the answer states no limitation, return {"entries": []}.

Example 1 (one thing, two categories)
The answer: S001 and S002 name <<WORDS_A>> as a limitation of <<THING>>; S002 also names <<WORDS_B>> for <<THING>>.
{"entries": [{"thing": "<<THING>>", "category": "<<CATEGORY_A>>", "papers": ["S001", "S002"]},
 {"thing": "<<THING>>", "category": "<<CATEGORY_B>>", "papers": ["S002"]}]}

Example 2 (a limitation of the study as a whole)
The answer: S003 names <<WORDS_A>> as a limitation of its own study.
{"entries": [{"thing": null, "category": "<<CATEGORY_A>>", "papers": ["S003"]}]}

Example 3 (no limitation stated)
The answer: The papers report results but the answer names no limitation.
{"entries": []}
