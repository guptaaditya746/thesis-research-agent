Task: check, word by word, that each proposed word of an extraction pack fits its slot, judged only from its quotes. An extraction engine uses these words to find, in research papers, the things a topic question compares, the metrics, the measured values and the contexts. A word that does not fit its slot makes the engine find the wrong things.

Input (the user message, JSON):
- `question`: the topic question the pack serves.
- `words`: a list of {id, word, slot, quotes}.
  - `word`: a term as the papers write it, a name the proposal made up (snake_case), or a regular expression (Python syntax).
  - `slot`: what the word is for, for example "pattern naming the condition role 'x', the treatment side", "screen term: marks a paper as on topic", "pattern of the metric 'y' (higher is better: true)".
  - `quotes`: the spans of the papers given as the word's source, each {paper, quote}.

Output: `verdicts`, one per input word, in input order: {id, ok, reason}.
- `ok`: true when the quotes show the word fits its slot; false when it does not, or when the quotes do not show it.
- `reason`: one short sentence a reader can check against the quotes.

Rules:
- Judge each word on its own, from its quotes and its slot. Use no knowledge from outside the quotes.
- A pattern fits when the text it would find in the quotes is the thing the slot names.
- A treatment-side condition must be the thing the question asks about; a control side must be what it is compared against.
- A metric's "higher is better" must agree with the quotes (a rate of a bad event: false).
- A claim pattern fits when it finds wording that states that direction (improves, worsens, no effect).
- A made-up name (a role, a canonical metric name, a category) fits when it names what its quotes show.
- When in doubt, answer false and say what is missing.

Examples (an invented topic: a soil treatment named Norvane against untreated plots; question "Does Norvane raise grain yield over untreated plots?").

Fits:
```json
{"id": 1, "word": "\\bNorvane\\b", "slot": "pattern naming the condition role 'norvane', the treatment side", "quotes": [{"paper": "P003", "quote": "plots treated with Norvane"}]}
{"id": 1, "ok": true, "reason": "The pattern finds 'Norvane', the treatment the question asks about."}
```

Fits, though the word is also a metric (a confusing case):
```json
{"id": 2, "word": "grain yield", "slot": "screen term: marks a paper as on topic", "quotes": [{"paper": "P003", "quote": "grain yield rose by 8%"}]}
{"id": 2, "ok": true, "reason": "Grain yield is the topic's metric, so a paper naming it is on topic."}
```

Wrong side:
```json
{"id": 3, "word": "(?i)\\buntreated\\s+plots?\\b", "slot": "pattern naming the condition role 'norvane', the treatment side", "quotes": [{"paper": "P003", "quote": "against untreated plots"}]}
{"id": 3, "ok": false, "reason": "Untreated plots are the comparison, not the treatment."}
```

Wrong direction:
```json
{"id": 4, "word": "(?i)\\bcut\\b", "slot": "pattern of a claim by the authors that the treatment improves", "quotes": [{"paper": "P005", "quote": "Norvane cut grain yield"}]}
{"id": 4, "ok": false, "reason": "In the quote 'cut' states a loss of yield, which is worsens, not improves."}
```

Not shown:
```json
{"id": 5, "word": "drought_stress", "slot": "category of a limitation the papers state", "quotes": [{"paper": "P004", "quote": "Plots were sown in May."}]}
{"id": 5, "ok": false, "reason": "The quote states no limitation about drought."}
```
