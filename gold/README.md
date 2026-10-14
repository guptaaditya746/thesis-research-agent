# Gold standard: the evidence document D, its review and the judge (M3)

One evidence document **D** per question: everything the corpus says about the question under its
picked concept, built once by a model, then reviewed by people into the answer key that runs are
scored against (`docs/e2e-build-plan.md`, "Gold" and "Judge"). The first half (C1) builds D, sorts its
facts for review, draws the review pool and writes a draft key (`gold/{chunks,calls,screen,extract,
build,docmd,triage,pool,draft}.py`); the second half (C2, [Review](#review-argilla-answer-key-agreement-judge))
puts the facts in front of people in Argilla, exports the reviewed key, measures agreement and
provides and calibrates the judge (`gold/{argilla_io,review,export,agreement,screening_check,judge}.py`).
Reviewers read [`guidelines.md`](guidelines.md).

## The method

It is the method of [`guptaaditya746/labelling`](https://github.com/guptaaditya746/labelling)
(docs/EVIDENCE_DOCS.md there), re-implemented for the frozen Markdown corpus:

1. **Chunks** (`chunks.py`). Each paper of `$CORPUS/manifest.json` is cut at its Markdown headings into
   chunks of whole sections, packed up to 40,000 characters (`GOLD_CHUNK_CHARS`; about 10-16k tokens,
   so a chunk, the prompt and the reply fit the sub-model's 32,768-token context). Headings come from
   a CommonMark parser (markdown-it-py), so a `#` line inside a fenced code block (the prompt templates
   papers print in appendices) does not start a section and setext headings do. A longer section is
   cut at blank lines. Offsets are raw character offsets into the file, the ones anchors use, and the
   chunks cover the file exactly. A chunk too long for one call (the reply hit `max_tokens`, or the
   prompt did not fit the context: a results table over 60 datasets, digit-heavy tables) is cut in
   halves at the paragraph break nearest its middle and each half asked again, down to pieces of
   1,000 characters; only that chunk changes, so every other chunk keeps its cache entries and ids.
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
   stays in D with its reason and never reaches the key. A retry call that fails is recorded on its
   facts (`retry.error`) and counted (`counts.retry_errors`), and the build asks for a rerun.
4. **Rows** (`build.py`, `merge_rows`). Candidates are merged across papers by one generic rule. Table
   shapes: the first string column is the key (normalised: NFKC, casefold, letters and digits, so
   "Natural Questions" = "natural-questions"); list columns are unioned; an integer column named as
   the count of a list column (`paper_count`, `num_papers`, `n_papers`, `number_of_papers`,
   `total_papers`, `first_author_papers` for `papers`; or plain `count`/`total` beside a single list)
   is recomputed as the length of the union. A shared word is not enough: `paper_year`,
   `num_parameters`, `dataset_size` keep their extracted values. An extracted count that disagrees
   with its own row's list is kept under `conflicts`. Other cells keep the first value and list
   conflicting ones. Graph shapes: identical edges (types, predicate, normalised source and target)
   are one row; attributes merge like cells. Name variants that the normalisation does not catch (NQ
   vs Natural Questions) are left for review.
5. **Triage** (`triage.py`, `prompts/triage-v1.md`, ported). Each candidate is sorted into `answers`,
   `context` or `irrelevant` against the concept, 20 per call, given its row, quote and the passage
   around it. When unsure: context. Labels order the review; they are never gold. A label holds for
   the concept and triage prompt it was given under (both hashes on every line); a rebuilt D for
   another concept, or a new prompt, is triaged again. A reply that labels none of its batch is not
   cached, so a rerun asks again.
6. **Pool** (`pool.py`, ported). Every `answers` and `context` candidate (and any unsorted one) plus a
   seeded random sample of 50 `irrelevant` ones, shuffled, without label or stratum: what people
   review in Argilla (C2). `pool.strata.json` keeps the strata for the triage-miss estimate and the D
   it was drawn from.
7. **Draft key** (`draft.py`, ported). Before review: every `answers`/`context` candidate whose quote
   passed the check, merged into rows, in the answer-key format, `version: "v1-draft"`,
   `reviewed: false`. Its rows validate against `agent.concept.answer_schema_for(concept)` once the
   gold-only fact fields are stripped (`draft.validate_key`); C2's reviewed `key.json` replaces it.

Pool and draft key come from a complete D only: a trial or a D with failed calls is refused unless
`--allow-partial`, and a draft with untriaged candidates unless `--allow-untriaged`; both record the
D they came from (`built.doc` / `doc`: coverage, failures, trial settings, doc.json's hash) and say
`partial`, so scoring never reads a 20-paper key as the full one.

Models: `sub-model-1`/`-2` (Qwen3-30B-A3B-Instruct), used in turn, never the agent's orchestrator, to
keep gold apart from the system it scores; thinking off, temperature 0, seed 0
(`gold/llm.py`, pydantic-ai on LiteLLM, schema-constrained output). The model identity in cache keys
and in `doc.json.built.models.model_key` is the pinned name@revision (`agent/rundir.SUBAGENTS`,
`llm.model_identity`), as in the agent's own run records: the server reports only its served name
(`sub-model`), which names no weights. Serving other weights behind the aliases needs a new pin,
which changes every cache key.

Modules: `chunks.py`, `screen.py`, `extract.py`, `build.py` (D), `docmd.py` (doc.md), `triage.py`,
`pool.py`, `draft.py`; `calls.py` is the call layer under all of them (prompt files and hashes,
cache keyed by the full input, concurrency, timeout, failure kinds, cost counters; model-agnostic, so
C2's judge can use its `Caller`); `build_cli.py` registers the subcommands in `gold/cli.py`.

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
gold build q01 --max-papers 20 --out $GOLD-trial   # a trial on the first 20 papers (or --only-papers p3,p7)
gold build q01                     # the full build, once the question's concept pick is final
gold status                        # one line per question (also while building); --json for tools
gold triage q01                    # resumable; run again to retry failed batches
gold pool q01 --sample 50 --seed 0
gold draft q01
```

`gold build` options: `--concept` (default `$CONCEPTS/<qid>/concept.json`), `--question` (default the
concept session's `session.json`, else `questions/questions.json`), `--corpus`/`--manifest`, `--out`
(default `$GOLD`), `--models sub-model-1,sub-model-2`, `--concurrency` (`GOLD_CONCURRENCY`, 6),
`--timeout` seconds per call (`GOLD_CALL_TIMEOUT_S`, 300), `--chunk-chars` (`GOLD_CHUNK_CHARS`, 40000),
`--replace`. Exit codes: 0 D complete; 1 calls failed that a rerun retries (screening, extraction or
quote retry; failures are never cached), so run it again; 3 only failures a rerun cannot fix are left
(a chunk too long even in 1,000-character pieces: lower `GOLD_CHUNK_CHARS`; a paper that fails its
hash: fix the corpus); 143 stopped by SIGTERM (Slurm's time limit), resumable. A stopped build
resumes; delete `$GOLD/<qid>/cache.jsonl` to pay for everything again.

Run trials into their own directory (`--out $GOLD-trial`): any file in `$GOLD/<qid>/` freezes the
question's concept pick (`agent concepts pick --replace` and the web app refuse a change once gold
exists, `concept_step.gold_files`), and the provisional picks (`picked_by: provisional-first`) are meant
to be changed by the user before gold is built. A trial in `$GOLD` itself is fine only for a question
whose pick the user has confirmed; then the full build takes the trial's calls from the cache.

A folder holds D for one concept. `gold build` refuses a concept other than the one its doc.json was
built for (a re-pick after a provisional one): with `--replace` it moves that D and everything made
from it (triage, pool, keys, review files) to `superseded/<concept sha256[:12]>-<time>/`, keeping the
call cache and `ids.jsonl`. It also refuses a trial over a whole-corpus D, which triage, pool and
draft would then read: run trials with their own `--out`, or pass `--replace` (a full build after it
restores the whole D from the cache without model calls).

`gold triage` and `gold pool` need the corpus (passages). `gold pool` and `gold draft` refuse a
partial D unless `--allow-partial`; `gold draft` refuses untriaged candidates unless
`--allow-untriaged`. `gold status` reports a build whose process is gone as `dead` (same host) or
`stale` (no progress for twice the call timeout plus a minute), and a pool or key made for another
concept than D's as `stale`.

## Files (`$GOLD/<qid>/`)

| File | Content |
|---|---|
| `chunks.jsonl` | `{paper_id, chunk, start, end, heading, chars}` |
| `screening.jsonl` | per paper `{paper_id, file, status, chunks, chunks_relevant, chunks_error, chunks_too_long, chunks_split, findings, model, served_model, prompt_sha256, candidates, error?, extraction_errors?, extraction_too_long?, retry_errors?}` |
| `candidates.jsonl` | per fact `{id, qid, paper_id, file, row, s, p, o, quote, anchor, anchor_status, anchor_in_chunk, chunk, piece?, span?, heading, extracted_row, fact, attempts, first_quote?, first_reason?, retry?: {model, served_model, prompt_sha256} \| {error, kind}, model, served_model, prompt_sha256}` |
| `doc.json` | `{qid, question, concept_sha256, kind, concept, built: {git_commit, git: {commit, dirty, diff_sha256}, models, prompts, settings, started_at, ended_at, invocations, corpus, ...}, coverage: {papers, relevant, not_relevant, no_text, error, papers_in_corpus, partial}, rows: [{key, cells, candidates, papers, anchored, conflicts?}], counts: {..., retry_errors, too_long, split_chunks, model_calls: {made, cached, failed, too_long, ..., total}, cost}}` |
| `doc.md` | D for people: coverage, every row with its facts, quotes and anchor status, papers by status |
| `triage.jsonl`, `triage.json` | `{id, label, model, served_model, prompt_sha256, concept_sha256}` (last line per id wins); every triage run with its settings, models, corpus manifest |
| `pool.jsonl`, `pool.strata.json` | review records (fact, quote, passage with the quote highlighted); strata, seed, sizes, the D drawn from, `partial` |
| `key.draft.json` | draft key: `{qid, concept_sha256, kind, version: "v1-draft", reviewed: false, rows, notes, merged_facts, counts, built: {partial, doc, untriaged, git, ...}}` |
| `cache.jsonl`, `ids.jsonl`, `progress.json` | call results and too-long verdicts; candidate ids (stable across trial and full builds, new for a new concept); live progress with pid and host |
| `superseded/` | D and what was made from it for an earlier concept (`--replace`) |

`doc.json.counts.model_calls.total` counts every call D rests on, the cached ones with what they cost
when they were made; `built.invocations` lists each build of this D (calls, tokens, seconds), so a
trial, a full build and a resumed one add up. `built.git` records a dirty tree with the hash of its
diff; when git cannot tell (a shared checkout with "dubious ownership"), the build warns and records
null.

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
relevant chunks again with longer replies (up to 8,192 tokens). A chunk too long for one call costs
that call plus two per halving (its verdict is cached, so a rerun does not pay for it again).
`doc.json.counts.model_calls` and `progress.json` record calls made, cached, failed and too long and
the tokens used, `counts.cost` the sum over every build of this D: a 20-paper trial gives the real
rate before the full build.

## Tests

`gold/tests/` (no network, GPU or cluster): a scripted pydantic-ai `FunctionModel` plays the sub-model
on the 10 D1 papers (`agent/tests/conftest.write_corpus`): chunk offsets round trip, headings in code
fences ignored, screening statuses (relevant, not relevant, no text, error retried on the rerun),
anchors accepted, rejected and retried, failed quote retries counted and retried, too-long chunks read
in halves (and a piece too long even then: exit 3), a rerun with no model call, stable ids across a
trial and a full build, new ids and no old labels for a new concept, SIGTERM and dead builds in
progress, a cut cache line, row merging (and integers that are not counts), triage and pool
determinism with a seed, labels tied to concept and prompt, partial D refused by pool and draft, and
the draft key validating as an answer. The review half is tested against an in-memory Argilla
(`gold/tests/fixtures.py`, every record checked against its dataset spec), the judge with
`FunctionModel`s and a keep-alive fake OpenAI server, kappa, Wilson and miss estimates against hand
computations; `test_build_to_review.py` runs C1's real pipeline into C2's push, pull and export and
checks that the reviewed key groups kept facts exactly as the draft key does (table and graph).

## Review: Argilla, answer key, agreement, judge

The review half of the gold standard, ported from `github.com/guptaaditya746/labelling` (README
workflow steps 4–11, `docs/EVALUATION.md`, `guidelines/annotation.md`, `src/labelling/{argilla_io,gold,
screening}.py`, `infra/README.md`) to facts with quotes from the Markdown corpus. C1 builds D per
question (`gold/{screen,extract,triage,pool,draft}.py`); this part puts D's candidate facts in front of
people, turns their answers into the reviewed answer key `key.json`, measures how far the review can be
trusted (`report.json`), and provides and calibrates the LLM judge that scoring uses
(`judge-report.json`). Contracts: `docs/e2e-build-plan.md`, "Gold" and "Judge". Reviewers read
[`guidelines.md`](guidelines.md).

| Module | Does |
|---|---|
| `gold/argilla_io.py` | dataset specs and settings, record content, push (upsert by stable id), pull |
| `gold/review.py` | the `$GOLD` layout, C1's files, the corpus, pulled responses, overlap snapshots |
| `gold/export.py` | decision rule, missing facts anchored with `agent/anchor.py`, rows, `key.json` |
| `gold/agreement.py` | Cohen's kappa, bootstrap over questions, triage miss estimate, `report.json` |
| `gold/screening_check.py` | sample of papers screened not relevant, false-negative rate |
| `gold/judge.py` | `support`, `same_fact`, `same_row`, the cache, the calibration |
| `gold/review_cli.py` | the `gold` subcommands below |

### Where things run

| What | Where |
|---|---|
| Argilla + Elasticsearch + PostgreSQL + Redis | Omen (Docker), `gold/argilla/compose.yaml` |
| `gold` commands, the sub-models behind LiteLLM | Slurm compute node (or any machine with the tunnel) |
| Review in the browser | laptop, through `scripts/omen-tunnels` (service `argilla`) |

#### Argilla on Omen

```sh
mkdir -p ~/stacks/argilla && cd ~/stacks/argilla
cp /path/to/thesis-research-agent/gold/argilla/compose.yaml .
cp /path/to/thesis-research-agent/gold/argilla/env.example .env   # set passwords and the API key
docker compose up -d && docker compose logs -f argilla            # wait for "Uvicorn running"
```

About 3–4 GB RAM; most start-up problems come from Elasticsearch (`docker compose logs elasticsearch`).
The server version (v2.8.0) matches the pinned `argilla==2.8.0` SDK.

Tunnel: `scripts/omen-tunnels` lists `argilla` (Omen 6900, laptop 26900, gateway 46900, compute 36900).
Laptop first, then the compute node:

```sh
omen-tunnels laptop start argilla      # browser: http://127.0.0.1:26900
omen-tunnels compute start argilla     # scripts: ARGILLA_API_URL=http://127.0.0.1:36900 (the default)
```

Accounts: the owner from `.env` runs the `gold` commands (its API key); people review from accounts
with role `annotator` in workspace `thesis`, the main reviewer too. Add them in the UI, or from Python:

```python
import argilla as rg
client = rg.Argilla(api_url="http://127.0.0.1:36900", api_key="...")
rg.User(username="professor", password="...", role="annotator", client=client).create()
client.workspaces("thesis").add_user("professor")
```

Nothing that could sway an answer is sent to Argilla (no triage label or stratum, no run condition):
Argilla hides metadata marked hidden from annotators only, owners and admins see it.

Environment of the `gold` commands: `GOLD` (default `gold-data`), `CORPUS` (the frozen corpus with its
`manifest.json`; every file is checked against its manifest hash), `CONCEPTS` (default `concepts`),
`QUESTIONS` (default: the repository's `questions/questions.json`), `RUNS` (default `runs`),
`ARGILLA_API_URL` (default `http://127.0.0.1:36900`), `ARGILLA_API_KEY`, `ARGILLA_WORKSPACE` (default
`thesis`), and for the judge `LITELLM_BASE_URL`, `LITELLM_MASTER_KEY`. Keys are read when a client or
model is made and never logged or written.

Trial runs (the Slurm test session) push to their own datasets, `--name gold-e2etest` on every command,
so that answers given while trying things out never meet the real review's records.

### Workflow

| Step | Command | Output |
|---|---|---|
| 1. C1 has built D, triage and the pool | `gold build`, `gold triage`, `gold pool` (C1) | `$GOLD/<qid>/{candidates,pool,triage,screening}.jsonl`, `doc.json` |
| 2. Load the review | `gold push all` | datasets `gold-v1-review`, `-overlap`, `-missing`; `$GOLD/overlap.json` |
| 3. Sample papers screened not relevant (default 5 per question) and load them | `gold screening-sample`, `gold screening-push` | `$GOLD/<qid>/screening.sample.json`; `gold-v1-screening` |
| 4. Review ([guideline](guidelines.md)): you do review, missing and screening; both reviewers do the overlap | Argilla UI | responses |
| 5. Both have finished the overlap, before discussing it | `gold snapshot` | `$GOLD/<qid>/snapshots/overlap-<time>.json` |
| 6. Pull everything (every pull also snapshots a changed overlap) | `gold pull` | `$GOLD/<qid>/review/*.jsonl`, `$GOLD/judge/responses.jsonl` |
| 7. Export the keys; adjudicate the listed disagreements (a third person), pull, export again | `gold export all [--adjudicator NAME]` | `$GOLD/<qid>/key.json`, `export.json` |
| 8. Agreement and what the review missed | `gold agreement` | `$GOLD/<qid>/report.json`, `$GOLD/report.json` |
| 9. After scored runs: sample fact-quote pairs of the real batch, load them, people answer, pull | `gold judge-sample --runs $RUNS/m4-72`, `gold judge-push`, `gold pull` | `$GOLD/judge/sample.jsonl`, `sample.json`; `gold-v1-judge` |
| 10. Calibrate the judge | `gold judge-agreement` | `$GOLD/judge-report.json` |
| One verdict, e.g. to try the prompt | `gold judge '{"s": "p12", "p": "evaluatesOn", "o": "HotpotQA"}' "<quote>"` | JSON verdict |

`push` and the other commands take `<qid>`, a comma-separated list or `all`; pushing again updates the
records in place (stable ids: `<candidate id>-<fact digest>`, `missing-<qid>`, `screening-<qid>-<paper>`,
`judge-<hash>`) and keeps people's answers. A review record's id holds a digest of the fact it shows, so
if D is rebuilt and a candidate id comes to name another fact, that fact gets a new record and the old
answers are listed as stale, never applied to it. `export`, `agreement` and `judge-agreement` work on
the pulled files; `--pull` pulls first. `push`, `export`, `screening-push`, `judge-push` and
`judge-agreement` need the corpus; a record whose file the corpus cannot give (not in the manifest,
missing, hash changed) is not pushed, and the command lists it and exits 1.

The overlap questions are chosen once, at the first `push`, from the whole `questions.json` (seeded,
`ceil(0.2 x questions)`, 3 of 12), and kept in `$GOLD/overlap.json` with where the list came from; their
records are only in `-overlap`. Without `questions.json` the first push stops rather than choose from
the questions built so far. Samples are drawn once as well: `screening-sample` keeps an existing
`screening.sample.json` and `judge-sample` refuses to overwrite `judge/sample.jsonl`, unless `--force`
(the answers already given belong to the old draw). The judge sample records its run ids and the
sha256 of each `pairs.jsonl`.

### The answer key

Decision rule per answer (`gold/export.py`): **correct** keeps the candidate fact, with its quote, paper
and row; with a correction `s | p | o` the corrected fact (an empty part keeps the candidate's; row
values equal to the old subject or object follow the fix); a correction that does not parse drops it
and is listed. **Incorrect** drops; **unsure** drops and is listed. Vital when answered vital yes. On
the overlap, people disagree when they differ on keep/drop or keep different facts; the adjudicator's
answer decides (flagged when the adjudicator is one of the two raters); unresolved disagreements stay
out and are listed. A fact both keep is vital only if both said so.

Quotes: every key fact's quote occurs in its corpus file. A kept candidate is located again in its file
(through the manifest hash check) and its quote is the exact text found; one whose quote is not there
(C1's `not_found`, `partial_number`) is left out and listed under `unanchored`, whatever the reviewer
answered. A quote that occurs several times in its paper (C1: `ambiguous`, no anchor) is kept: the
reviewer saw it marked (the occurrence in the chunk it was read from, else the first, with a note), and
`repeated_quotes` lists it. C1's draft key leaves such candidates out; here people have confirmed them.

Missing facts (from the missing and screening records) are anchored in their file with
`agent/anchor.py`, as the broker anchors the agent's claims; anchored ones become key facts (quote = the
exact text in the file, vital false, `candidate_id` null), the rest are listed in `export.json`
`rejected` with the reason (`not_found`, `partial_number`, `ambiguous`: quote more of the sentence,
`unknown_file`, `missing_file`, `corpus_file_hash_mismatch`, `format`).

Rows: kept facts are grouped into rows by the rule of C1's draft key and `doc.json` (export.py imports
gold/build.py's `norm`, `key_column`, `merge_cells` with its `count_columns`, and `row_key`: one
implementation), so `key.draft.json` and `key.json` group facts the same way: table rows by the normalised value
(NFKC, casefold, letters and digits) of the first string column, list cells unioned, a count column of
a list recomputed, other cells the first value given (differences listed), rows without a key value
never merged; graph rows by (source type, normalised source, predicate, target type, normalised
target), the edge type picked by predicate **and** the row's node types (one predicate may join several
type pairs; when only the name decides between several, the first is taken and the problem listed). An
added fact gets a row built from it, which joins the row its subject (else its object) names. Facts with
the same normalised s/p/o in one row are one (vital if any copy is).

`key.json`: `{qid, concept_sha256, kind, version: "v1", reviewed: true, rows, notes, key_sha256,
review}`; facts `{id, s, p, o, claims: [], origin: "research", paper_id, quote, vital, candidate_id}`
(`claims` and `origin` only so that the rows have the answer schema; the key has no broker claims).
`key_sha256` hashes the rows: scoring records it next to `key_version`, since every re-export is `v1`.
`review.inputs` records what the key was built from (D's `built`, the sha256 of C1's files and of the
pulled `review/*.jsonl`, the exporting commit). Stripping the gold-only fields (`export.as_answer`) gives
a valid answer for `agent.concept.answer_schema_for(concept)`; export writes no key that does not
validate, and none when `doc.json` was built for another concept: then an earlier `key.json` is moved
to `key.stale.json`, so neither the web app nor scoring keeps using a key the review no longer gives
(`export.json` `status: failed`). `export.json` lists every decision, disagreements, unsure facts,
unreviewed records, stale answers, unanchored and repeated quotes, added and rejected lines, merged
duplicates and problems; `key.review` counts them. `complete` is true only when every record is decided,
no disagreement is open, the question's missing-facts record is marked reviewed, and every sampled
screening paper is checked. Export writes key.json after every pull, also half way through: until
`review.complete` is true, scoring marks scores against it provisional (as against the draft key) and
the web app shows the question's gold as `reviewing`, not `reviewed`.

### The numbers (`report.json`)

- **Agreement**: Cohen's kappa (`sklearn.metrics.cohen_kappa_score`) between the two most active
  reviewers of the overlap, on the independent round (per record the earliest snapshot in which both had
  answered), for `label`, `keep` (the export's own rule) and `vital` (where both kept), overall and per
  stratum (triaged / sample, taken from the pool), with a 95 % percentile bootstrap interval resampling
  whole questions (`scipy.stats.bootstrap`, 2000 resamples, seed 1998; undefined resamples are counted
  and left out). It counts `records_from_snapshots` and `records_from_live`; `independent` is false, with
  a warning, when some pairs come from the last pull (no snapshot had both answers: possibly after
  discussion). Answers on stale records are counted (`records_stale`), not used.
- **Triage miss** (labelling `miss_report`, exactly): with N the rest outside the reviewed tiers, n the
  reviewed sample of it and k its kept facts, `estimated_missed = (N - n) k / n` with a 95 % Wilson
  interval (`statsmodels proportion_confint`, method wilson) on k / n scaled by N - n;
  `estimated_recall = tiers_kept / (tiers_kept + k + estimated_missed)`, its interval the Wilson bounds
  in the same ratio.
- **Screening false negatives**: per question, the share of sampled not-relevant papers someone found
  relevant, with a Wilson interval, times the papers screened not relevant; overall the per-question
  estimates summed (bounds summed: conservative) and the pooled rate. Only answers on the papers of the
  drawn sample count (`outside_sample`: others pulled).

### The judge (`gold/judge.py`, for D and E)

```python
from gold import judge
judge.support({"s": "p12", "p": "evaluatesOn", "o": "HotpotQA"}, quote, context=None)
# {"label": "supports" | "partial" | "no", "rationale", "model", "served_model", "prompt_sha256", "cached"}
judge.same_fact(run_fact, key_fact, concept)   # {"match": bool, "rationale", ...}
judge.same_row(run_row, key_row, concept)      # {"match": bool, ...}
j = judge.Judge(cache_only=True)               # never calls a model: unseen input -> None (pending)
await j.gather([j.asupport_pair(p, corpus) for p in pairs])   # many, 6 model calls at a time
await j.asupport(fact, quote)                  # from async code (a FastAPI handler): never the sync call
```

`sub-model-1`/`-2` through `gold/llm.py` (pydantic-ai, structured output, temperature 0, thinking off).
Every model call, from any thread or event loop, runs on one event loop the judge keeps in a daemon
thread: the OpenAI client's keep-alive connections belong to the loop that opened them, so a new loop
per call would fail every other call on a real endpoint ("Event loop is closed"). The sync calls are
safe from scoring's worker threads; they block the caller, so async code awaits the `a...` twins. At
most 6 model calls run at once per judge, and identical inputs in flight together make one call.

Every answer is cached in `$GOLD/judge-cache.jsonl` under sha256 of the task, the prompt hash, the sha256
of the exact user prompt, the model identity (pinned name and revision) and the settings (temperature,
seed, max_tokens), so a rescore costs no model call and a change to a prompt, to how inputs are
rendered, to the model or a setting never reuses an old answer. Each cache line keeps the call's task,
input, hashes, settings, the model the server says answered (`served_model`), token usage and time.
Prompts: `gold/prompts/judge-{support,same-fact,same-row}.txt`. The calibration judges each quote with
`judge.context_for(corpus, file, start, end)` (paper id and 600 characters around the quote); scoring
should do the same (`Judge.support_pair(pairs_line, corpus)` does), so the judge it uses is the one that
was calibrated. A pair whose file the corpus cannot give raises; it is never judged without context.

Calibration: `judge-sample --runs $RUNS/m4-72` draws 240 pairs (default; `--size`) with a quote from the
`pairs.jsonl` of the runs `score batch` scored there (its `report/batch.json`, so cut attempts, smoke
and web runs are not in the population that weights kappa; `--all-runs`, or no batch.json yet, takes
every run below the root and the manifest says so), stratified by condition (equal allocation,
population recorded); people answer supports / partial / no, each record showing the passage the
judge gets (`context_for`'s 600 characters each side, not the review's 1,500; `context_chars` in
sample.json and the report); `judge-agreement` splits the answered pairs into two seeded halves, picks on
the first whether the judge's `partial` counts as yes or no (higher kappa; ties: no), and reports on the
second Cohen's kappa (raw and weighted by condition population, N_h / n_h), the judge's yes-precision
P(person yes | judge yes) and P(person yes | judge no) with Wilson intervals, the 3x3 table and each
person's kappa. People's `supports` is yes, `partial` and `no` are no. Weighted kappa below 0.61: the
report says to report soft scores without the judge, as the labelling repo did, and `score report`
acts on it (`use_judge`: the primary test marked unvalidated, soft outcomes left out). The report records the
model, the models the server reported, the prompt file and hash, `render_sha256` (how inputs become the
user prompt) and the settings.

