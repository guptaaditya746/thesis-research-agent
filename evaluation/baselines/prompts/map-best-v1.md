Task: for every corpus paper a system's answer speaks about, report the method kind that the answer says reaches
the best <<METRIC>> in that paper (<<DIRECTION>> is best).

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  retrieve-then-answer system's answer (its text and the headers [paper id, start-end] of the passages it cites).

Method kinds (kind: the method names that belong to it):
<<KINDS>>

Output: `studies`, a list of objects with
- `paper`: a corpus paper id from the list given.
- `winner`: the kind of the method the answer says is best in this paper, written exactly as one of the kind
  names above; null when the answer does not say which method is best there, or says two methods tie.

Rules:
- Report only what the answer says. Map the method the answer names to its kind by the lists above.
- One entry per paper the answer speaks about. Leave out papers the answer does not mention.
- Use only paper ids from the list given.

Example 1 (a method name mapped to its kind)
The answer: In S001 the RAG pipeline scores best.
{"studies": [{"paper": "S001", "winner": "rag"}]}

Example 2 (the closed-book model wins in one paper; the answer calls a second paper a tie)
The answer: S002: the closed-book model beats the retrieval-augmented model. S003: both reach the same score.
{"studies": [{"paper": "S002", "winner": "no-retrieval"}, {"paper": "S003", "winner": null}]}

Example 3 (the paper is mentioned, its best method is not)
The answer: S004 compares several methods.
{"studies": [{"paper": "S004", "winner": null}]}
