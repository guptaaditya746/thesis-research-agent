Task: for every corpus paper a system's answer speaks about, report the method kind that the answer says reaches
the best <<METRIC>> in that paper (<<DIRECTION>> is best), or the kinds the answer says tie for the best.

Input fields:
- Question: the research question the system answered.
- Corpus paper ids: the ids of the papers in the corpus.
- The answer: what the system wrote after reading the corpus. Either a research agent's answer (its rows, the
  facts it recorded as subject | predicate | object with the quotes behind them, and its notes) or a
  passage-based system's answer (its text and the headers [paper id, start-end] of the passages it cites).

Method kinds (kind: the method names that belong to it):
<<KINDS>>

Output: `studies`, a list of objects with
- `paper`: a corpus paper id from the list given.
- `winner`: the kind of the method the answer says is best in this paper, written exactly as one of the kind
  names above; null when the answer says two or more methods tie for the best, or does not say which is best.
- `tied`: when the answer says methods tie for the best in this paper, the kinds of those methods (two or more,
  written exactly as kind names above); otherwise an empty list.

Rules:
- Report only what the answer says. Map the method the answer names to its kind by the lists above.
- One entry per paper the answer speaks about. Leave out papers the answer does not mention.
- Use only paper ids from the list given.

Example 1 (a method name mapped to its kind)
The answer: In S001 the <<NAME_B>> scores best.
{"studies": [{"paper": "S001", "winner": "<<KIND_B>>", "tied": []}]}

Example 2 (one method wins in one paper; the answer calls a second paper a tie)
The answer: S002: the <<NAME_A>> beats the <<NAME_B>>. S003: the <<NAME_A>> and the <<NAME_B>> reach the same
score.
{"studies": [{"paper": "S002", "winner": "<<KIND_A>>", "tied": []},
 {"paper": "S003", "winner": null, "tied": [<<TIED_AB>>]}]}

Example 3 (the paper is mentioned, its best method is not)
The answer: S004 compares several methods.
{"studies": [{"paper": "S004", "winner": null, "tied": []}]}
