# The 12 evaluation questions

`questions.json` holds the questions every later step works on (row 2.3; `docs/e2e-build-plan.md`, "The 12
questions"): the concept step proposes readings of each (`agent concepts propose-all`), gold D is built for the
picked reading, and the batch runs answer it in both conditions. Six are corpus-wide (one reading, the answer
spans many papers) and six ambiguous (more than one reasonable reading; the concept step proposes them).

```json
{"schema_version": 1, "questions": [
  {"id": "q01", "category": "corpus_wide",
   "question": "Which benchmarks and datasets do the retrieval-augmented generation papers in the corpus evaluate on?",
   "source": "nlp33", "notes": "Was: '...' (how and why it was reworded)"}]}
```

The schema is `agent/schemas/questions.schema.json`; `agent/tests/test_questions.py` checks the file against it
and against the plan (q01–q06 corpus-wide, q07–q12 ambiguous). Code reads it with
`agent.concept_step.load_questions`.

## Where they come from

From the question set of the labelling project, `github.com/guptaaditya746/labelling`, file
`questions/questions.json` at commit `a75b372`. That set has 28 questions written for the earlier harness and
its search index: 16 corpus-wide (`nlp32`–`nlp47`) and 12 ambiguous (`nlp30`, `nlp48`–`nlp53`, `nlp62`–`nlp66`).
The build plan (13 Oct) took six of each:

| id | source | category |
|---|---|---|
| q01–q05 | nlp33, nlp34, nlp35, nlp36, nlp42 | corpus_wide |
| q06 | nlp44 | corpus_wide |
| q07 | nlp30 | ambiguous |
| q08–q12 | nlp48, nlp49, nlp53, nlp62, nlp66 | ambiguous |

## How they were reworded

Only as far as the Markdown corpus needs; each entry's `notes` holds the original wording.

- "the indexed papers" became "the papers in the corpus": the agent reads the frozen Markdown files with shell
  tools, there is no index (q01–q06, q10, q11).
- q07 (nlp30) also lost "2025" (every paper in the corpus is from ACL 2025 or EMNLP 2025) and "and by which
  evaluation measure": which measure decides "best" is one of the readings the concept step should propose.
- q08, q09 and q12 are unchanged.

## Replacing a question

The set is provisional: a later session with access to the corpus may replace questions that the corpus cannot
answer. Do it **before gold is built**:

1. Edit the entry in `questions.json`: keep its id and its category (the ids are slots that the run manifests in
   `agent/manifests/` name; q01–q06 are corpus-wide, q07–q12 ambiguous) and the schema; set `source` (a
   labelling id, or `own`) and say in `notes` what changed and why.
2. Update the table in `docs/e2e-build-plan.md` ("The 12 questions") to match, and run
   `uv run pytest agent/tests/test_questions.py` (one test compares the file with that table).
3. Propose concepts for it: `agent concepts propose-all questions/questions.json --root "$CONCEPTS" ...` skips
   every question that already has a proposal.

Changing a question's text **invalidates its concept, its gold and its runs**. The concept session records the
sha256 of the question it was proposed for (`session.json`, `question_sha256`); after an edit,
`agent concepts status` shows the question as `stale` and `agent concepts propose` refuses the old session. Move
the old material aside before proposing again: `$CONCEPTS/<id>/` (and its entry in `$CONCEPTS/picks.json`, which
the next pick rewrites), `$GOLD/<id>/` and every run whose key starts with `<id>-`.
