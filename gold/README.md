# Gold standard: the evidence document D and what follows it (M3)

One evidence document **D** per question: everything the corpus says about the question under its
picked concept, built once by a model, then reviewed by people into the answer key that runs are
scored against (`docs/e2e-build-plan.md`, "Gold"). This part (C1) builds D, sorts its facts for review,
draws the review pool and writes a draft key; review, agreement and the judge are C2's
(`gold/{argilla_io,review,export,agreement,screening_check,judge}.py`).

## The method

It is the method of [`guptaaditya746/labelling`](https://github.com/guptaaditya746/labelling)
(docs/EVIDENCE_DOCS.md there), re-implemented for the frozen Markdown corpus:

1. **Chunks** (`chunks.py`). Each paper of `$CORPUS/manifest.json` is cut at its Markdown headings into
   chunks of whole sections, packed up to 40,000 characters (`GOLD_CHUNK_CHARS`; about 10-16k tokens,
   so a chunk, the prompt and the reply fit the sub-model's 32,768-token context). A longer section is
   cut at blank lines. Offsets are raw character offsets into the file, the ones anchors use, and the
   chunks cover the file exactly.
2. **Screening, every chunk of every paper** (`screen.py`, `prompts/screen-v1.md`). Is this part
   relevant to the concept, and what does it say? When unsure the model answers relevant. A paper is
   `relevant` if any chunk is, `not_relevant` if all were screened and none is, `no_text` for a failed
   conversion (the scanned p38), `error` if a call failed (retried on the next build). Absence is
   recorded per paper, not assumed.
3. **Extraction, every relevant chunk** (`extract.py`, `prompts/extract-v1.md`). Rows of the concept's
   answer shape (table columns, or graph edges), each with facts `{s, p, o}` and an exact quote per
   fact, decoded under a JSON schema derived from the concept, so cells are typed as the answer schema
   types them. Every quote goes through **the broker's claim check** (`agent/broker.py`: request
   fields, file name, manifest hash, `agent/anchor.find` in the whole file), so a gold quote passes
   exactly the test an agent's claim passes. A quote rejected for a reason a new quote can fix
   (`not_found`, `ambiguous`, `partial_number`, `empty_quote`) is sent back once with the reason,
   explained in the words of the agent's prompt (`prompts/extract-retry-v1.md`); what still fails
   stays in D with its reason and never reaches the key.
4. **Rows** (`build.py`, `merge_rows`). Candidates are merged across papers by one generic rule. Table
   shapes: the first string column is the key (normalised: NFKC, casefold, letters and digits, so
   "Natural Questions" = "natural-questions"); list columns are unioned; an integer column that counts
   a list column (`paper_count` and `papers`) is recomputed as the length of the union; other cells
   keep the first value and list conflicting ones. Graph shapes: identical edges (types, predicate,
   normalised source and target) are one row; attributes merge like cells. Name variants that the
   normalisation does not catch (NQ vs Natural Questions) are left for review.
5. **Triage** (`triage.py`, `prompts/triage-v1.md`, ported). Each candidate is sorted into `answers`,
   `context` or `irrelevant` against the concept, 20 per call, given its row, quote and the passage
   around it. When unsure: context. Labels order the review; they are never gold.
6. **Pool** (`pool.py`, ported). Every `answers` and `context` candidate (and any unsorted one) plus a
   seeded random sample of 50 `irrelevant` ones, shuffled, without label or stratum: what people
   review in Argilla (C2). `pool.strata.json` keeps the strata for the triage-miss estimate.
7. **Draft key** (`draft.py`, ported). Before review: every `answers`/`context` candidate whose quote
   passed the check, merged into rows, in the answer-key format, `version: "v1-draft"`,
   `reviewed: false`. Its rows validate against `agent.concept.answer_schema_for(concept)` once the
   gold-only fact fields are stripped (`draft.validate_key`); C2's reviewed `key.json` replaces it.

Models: `sub-model-1`/`-2` (Qwen3-30B-A3B-Instruct), used in turn, never the agent's orchestrator, to
keep gold apart from the system it scores; thinking off, temperature 0, seed 0
(`gold/llm.py`, pydantic-ai on LiteLLM, schema-constrained output).

## What changed from the labelling repo, and why

| Labelling repo | Here | Why |
|---|---|---|
| GROBID passage index; a screening reader saw each paper's top passages by the harness ranker (`hybrid_rank`); extraction took the cited passages plus the top 12 | Every chunk of every paper is screened, and every relevant chunk is extracted; no ranker anywhere | No passage index on the Markdown corpus. It also **removes the ranker bias** the labelling repo documented (EVALUATION.md, flaw 1): a fact in a passage the ranker scored low could not reach D, which favoured the paths that use the same ranker. The cost is more calls (below). |
| Open extraction into triples in a fixed vocabulary (schema inference, EDC), claims built from them | Rows of the picked concept's answer shape, each fact `{s, p, o}` with a quote | The key must have the agent's answer shape, so scoring compares like with like. |
| Interpretations of an ambiguous question proposed during the build, one section each | The concept picked in the concept step (`$CONCEPTS/<qid>/concept.json`); one D per question | The pick is made once, before gold is built, and the runs use the same concept. |
| Evidence = the passage a triple came from | Evidence = an exact quote anchored in the file with `agent/anchor.py`, retried once on rejection | The same check as the agent's claims, so "the gold quote supports the fact" and "the agent's quote supports the fact" mean the same. |
| Harness model clients, a thread pool | pydantic-ai structured calls, asyncio with `GOLD_CONCURRENCY` calls in flight and a per-call timeout, every result in `cache.jsonl` keyed by its full input | Prefer maintained libraries; resumable at call granularity, and a rerun costs no calls. |
| Triage given the interpretation's label and gloss | Triage given the concept (title, definition, measure, scope, shape), the fact's row, quote and passage | The concept is what the key answers. |

Unchanged: every paper screened with absence recorded per paper, errors retried on the next build,
triage labels never gold, the stratified pool (all answers + context, a seeded sample of the rest,
shuffled, blind), the draft key marked as such.

## Commands

```sh
export CORPUS=/path/to/corpus GOLD=gold-data CONCEPTS=concepts   # LITELLM_BASE_URL, LITELLM_MASTER_KEY as for runs
gold build q01 --max-papers 20     # a trial on the first 20 papers of the manifest (or --only-papers p3,p7)
gold build q01                     # the full build; the trial's calls come from the cache
gold status                        # one line per question (also while building); --json for tools
gold triage q01                    # resumable; run again to retry failed batches
gold pool q01 --sample 50 --seed 0
gold draft q01
```

`gold build` options: `--concept` (default `$CONCEPTS/<qid>/concept.json`), `--question` (default the
concept session's `session.json`, else `questions/questions.json`), `--corpus`/`--manifest`, `--out`
(default `$GOLD`), `--models sub-model-1,sub-model-2`, `--concurrency` (`GOLD_CONCURRENCY`, 6),
`--timeout` seconds per call (`GOLD_CALL_TIMEOUT_S`, 300), `--chunk-chars` (`GOLD_CHUNK_CHARS`, 40000).
It exits 1 while any screening or extraction call failed: run it again. A stopped build resumes;
delete `$GOLD/<qid>/cache.jsonl` to pay for everything again.

## Files (`$GOLD/<qid>/`)

| File | Content |
|---|---|
| `chunks.jsonl` | `{paper_id, chunk, start, end, heading, chars}` |
| `screening.jsonl` | per paper `{paper_id, file, status, chunks, chunks_relevant, chunks_error, findings, model, served_model, prompt_sha256, candidates, error?, extraction_errors?}` |
| `candidates.jsonl` | per fact `{id, qid, paper_id, file, row, s, p, o, quote, anchor, anchor_status, anchor_in_chunk, chunk, heading, extracted_row, fact, attempts, first_quote?, first_reason?, retry?, model, served_model, prompt_sha256}` |
| `doc.json` | `{qid, question, concept_sha256, kind, concept, built: {git_commit, models, prompts, settings, started_at, ended_at, corpus, ...}, coverage: {papers, relevant, not_relevant, no_text, error, papers_in_corpus, partial}, rows: [{key, cells, candidates, papers, anchored, conflicts?}], counts}` |
| `doc.md` | D for people: coverage, every row with its facts, quotes and anchor status, papers by status |
| `triage.jsonl` | `{id, label, model, served_model, prompt_sha256}` (last line per id wins) |
| `pool.jsonl`, `pool.strata.json` | review records (fact, quote, passage with the quote highlighted); strata, seed, sizes |
| `key.draft.json` | draft key: `{qid, concept_sha256, kind, version: "v1-draft", reviewed: false, rows, notes, merged_facts, counts, built}` |
| `cache.jsonl`, `ids.jsonl`, `progress.json` | call results; candidate ids (stable across trial and full builds); live progress |

Every output line records `prompt_sha256` (template plus output schema), the model alias and the
served model name; `doc.json.built.prompts` has each template's file and hashes. Key facts carry
`claims: []` and `origin: "research"` only so that, stripped of `paper_id`, `quote`, `vital` and
`candidate_id`, a key row is a valid answer row.

## Costs

Calls per question: one screening call per chunk, one extraction call per relevant chunk, at most one
retry call per relevant chunk, and one triage call per 20 candidates; so **calls ~ chunks x questions**,
plus extraction for the relevant share. The corpus (336 converted papers, 28.6 MB of Markdown, mean
85 KB) makes about 1,000 chunks (the 10 D1 papers, 1.36 M characters, give 44), so about 1,000
screening calls and 7-8 M prompt tokens per question (the text once, plus about 1,000 tokens of
instructions and concept per call), and about 12,000 screening calls and 90-100 M prompt tokens for
the 12 questions. Screening replies are short, so screening is prefill-bound. Extraction adds the
relevant chunks again with longer replies (up to 8,192 tokens). `doc.json.counts.model_calls` and
`progress.json` record calls made, cached and failed and the tokens used: a 20-paper trial gives the
real rate before the full build.

## Tests

`gold/tests/` (no network, GPU or cluster): a scripted pydantic-ai `FunctionModel` plays the sub-model
on the 10 D1 papers (`agent/tests/conftest.write_corpus`): chunk offsets round trip, screening
statuses (relevant, not relevant, no text, error retried on the rerun), anchors accepted, rejected
and retried, a rerun with no model call, stable ids across a trial and a full build, row merging,
triage and pool determinism with a seed, and the draft key validating as an answer.
