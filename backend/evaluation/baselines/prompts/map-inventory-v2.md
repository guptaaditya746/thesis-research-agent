Task: list every <<TARGET>> that a system's answer names, with the corpus papers the answer names it for.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  passage-based system's answer (its text and the headers [paper id, start-end] of the passages it cites).

What to list: <<TARGET_TEXT>>

Output: `entries`, a list of objects with
- `name`: the name exactly as the answer writes it. One entry per distinct name. When the answer gives a name
  with its abbreviation in brackets, such as "<<NAME_A>> (<<ABBR_A>>)", write the name without the bracket.
- `papers`: the corpus paper ids the answer links to this name, from the list given. An empty list when the
  answer links it to no paper.

Rules:
- Report only what the answer says. Add no names of your own knowledge.
- Keep different names as separate entries, even when they look like synonyms; the caller merges synonyms.
- Use only paper ids from the list given.
- When the answer names nothing of this kind, return {"entries": []}.

Example 1 (two names, one of them in two papers)
The answer: S001 reports <<NAME_A>> and <<NAME_B>>. S002 reports <<NAME_A>>.
{"entries": [{"name": "<<NAME_A>>", "papers": ["S001", "S002"]}, {"name": "<<NAME_B>>", "papers": ["S001"]}]}

Example 2 (an agent's row and fact; an abbreviation in brackets)
The answer: Row r1: {"conclusion": "S003 covers <<NAME_B>>", "papers": ["S003"]}
  fact: S003 | reports | <<NAME_A>> (<<ABBR_A>>)
{"entries": [{"name": "<<NAME_B>>", "papers": ["S003"]}, {"name": "<<NAME_A>>", "papers": ["S003"]}]}

Example 3 (no paper named)
The answer: The papers mention <<NAME_B>>.
{"entries": [{"name": "<<NAME_B>>", "papers": []}]}
