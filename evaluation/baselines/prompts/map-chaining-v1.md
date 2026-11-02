Task: report whether a system's answer says <<SOURCE>> is better or worse than <<TARGET>> on <<METRIC>>
(<<DIRECTION>> is better), whether the answer says so from a direct comparison or infers it through other things, and
which corpus papers the answer rests this on.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  passage-based system's answer (its text and the headers [paper id, start-end] of the passages it cites).

Output: one object with
- `verdict`: "better" (the answer says <<SOURCE>> reaches a <<DIRECTION>> <<METRIC>> than <<TARGET>>), "worse" (the
  opposite), "no_difference" (the answer says the two do not really differ), "refused" (the answer says the papers
  cannot settle it), or null when the answer does not say.
- `via`: the things the answer goes through to link <<SOURCE>> with <<TARGET>> (each compared with one of them, or
  with the next thing on the way), in the order the answer walks them, names exactly as the answer writes them; an
  empty list when the answer compares the two directly or names nothing in between.
- `papers`: the corpus paper ids the answer rests its verdict on, from the list given.
- `inferred`: true when the answer reaches the verdict through `via` things, false when it reports a direct
  comparison of <<SOURCE>> with <<TARGET>> or gives no verdict.

Rules:
- Report only what the answer says. Do not work out a verdict yourself from numbers the answer gives.
- Use only paper ids from the list given.

Example 1 (inferred through one thing)
The answer: S001 finds <<SOURCE>> ahead of Compound X; S002 finds Compound X ahead of <<TARGET>>. So <<SOURCE>> is
likely better than <<TARGET>>, though no paper tests them together.
{"verdict": "better", "via": ["Compound X"], "papers": ["S001", "S002"], "inferred": true}

Example 2 (a direct comparison)
The answer: S003 compares <<SOURCE>> with <<TARGET>> head to head; <<SOURCE>> does worse on <<METRIC>>.
{"verdict": "worse", "via": [], "papers": ["S003"], "inferred": false}

Example 3 (the answer refuses)
The answer: The papers compare <<SOURCE>> and <<TARGET>> with different things in different groups, so no
conclusion follows.
{"verdict": "refused", "via": [], "papers": [], "inferred": false}
