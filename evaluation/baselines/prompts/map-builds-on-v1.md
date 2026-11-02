Task: report which corpus papers a system's answer says build on which, what each reuses, and, for every compared
thing the answer names, the corpus papers the answer says follow from (build on) the work that introduced it.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  passage-based system's answer (its text and the headers [paper id, start-end] of the passages it cites).

What a paper can reuse (write exactly one of these): <<REUSES>>

Output: one object with
- `links`: a list of objects, one per paper that builds on another, with `from` (the paper that builds on the
  other), `to` (the earlier paper it builds on), both corpus paper ids from the list given, and `reuses` (what it
  takes from it, one of the list above).
- `followers`: a list of objects, one per compared thing the answer says later papers build on, with `thing` (its
  name exactly as the answer writes it) and `papers` (the corpus paper ids the answer says build on it, directly or
  through another paper; the paper that introduced it is not one of them).

Rules:
- Report only what the answer says. Do not work out links yourself from dates or names.
- Use only paper ids from the list given; a paper outside the corpus is left out.
- When the answer names no link and no follower, return {"links": [], "followers": []}.

Example 1 (a chain of two links)
The answer: S002 reuses the <<REUSE_A>> of S001, which introduced <<THING>>; S003 builds on S002 by reusing its
<<REUSE_B>>.
{"links": [{"from": "S002", "to": "S001", "reuses": "<<REUSE_A>>"},
 {"from": "S003", "to": "S002", "reuses": "<<REUSE_B>>"}],
 "followers": [{"thing": "<<THING>>", "papers": ["S002", "S003"]}]}

Example 2 (a link with no thing named)
The answer: S005 takes its <<REUSE_B>> from S004.
{"links": [{"from": "S005", "to": "S004", "reuses": "<<REUSE_B>>"}], "followers": []}

Example 3 (nothing stated)
The answer: The papers are independent of each other.
{"links": [], "followers": []}
