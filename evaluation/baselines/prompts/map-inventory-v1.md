Task: list every <<TARGET>> that a system's answer names, with the corpus papers the answer names it for.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  retrieve-then-answer system's answer (its text and the headers [paper id, start-end] of the passages it cites).

What to list: <<TARGET_TEXT>>

Output: `entries`, a list of objects with
- `name`: the name exactly as the answer writes it. One entry per distinct name. When the answer gives a name
  with its abbreviation in brackets, such as "exact match (EM)", write the name without the bracket.
- `papers`: the corpus paper ids the answer links to this name, from the list given. An empty list when the
  answer links it to no paper.

Rules:
- Report only what the answer says. Add no names of your own knowledge.
- Keep different names as separate entries, even when they look like synonyms; the caller merges synonyms.
- Use only paper ids from the list given.
- When the answer names nothing of this kind, return {"entries": []}.

Example 1 (evaluation metrics)
The answer: S001 reports accuracy and latency. S002 reports accuracy.
{"entries": [{"name": "accuracy", "papers": ["S001", "S002"]}, {"name": "latency", "papers": ["S001"]}]}

Example 2 (methods or system variants; an abbreviation and a second name for one paper)
The answer: Row r1: {"conclusion": "a closed-book model and a RAG pipeline are compared", "papers": ["S003"]}
  fact: S003 | compares | retrieve-then-read model (RTR)
{"entries": [{"name": "closed-book model", "papers": ["S003"]}, {"name": "RAG pipeline", "papers": ["S003"]},
 {"name": "retrieve-then-read model", "papers": ["S003"]}]}

Example 3 (datasets; no paper named)
The answer: The systems are evaluated on Natural Questions.
{"entries": [{"name": "Natural Questions", "papers": []}]}
