# Four-domain benchmark: build state (22 Nov 2026)

Goal and rules: `../archive/prompt-four-domain-benchmark.md`. This note records what is built, how to run the rest, and what is
open. Earlier decisions: `../archive/codex-log.md`.

## Shape: one fact row for every domain (Aditya chose option A)

evqa's seed graph, questions and scoring knew only the diabetes-drug shape (drug, dose, week, patient group). The
paperfactory domains state other facts ("decision D relied on section 4", "the ZIMOR-3 trial randomised 210
patients", "HR 0.64 for tukrapurtinib"). Every such fact is now one row:

| field | meaning |
|---|---|
| id, paper | the number row id (R-med-07-03) or `<paper>:<s>-<r>-<o>`; the paper that states it |
| what | `relation` (planted fact), `attr` (a number of one entity), `effect` (a study's estimate or CI bound for an object), `pool` (a pooled estimate over studies) |
| subject, relation, object, attr, stat | world ids and keys |
| value, unit | as written in the paper (numbers only) |

The paperfactory export writes the rows (`data/seed/<d>/facts.jsonl`), the entities and the field's words. Each
number row carries what it is (`about`, from `plan.number_rows`) in `papers/<pid>/numbers.json`; the writer never
sees it.

## Pipeline

| step | code | needs Qwen |
|---|---|---|
| join the old worlds per field | `paperfactory join-worlds` -> `src/paperfactory/worlds/bench-<field>.json` | no (done) |
| papers (43 planned per field) | `paperfactory run --config configs/qwen/bench-<field>.json` | yes |
| export passed papers | `paperfactory export-workbench --domain bench_<field>` | no |
| 40 questions + gold | `evqa seed pfbench bench_<field>` (`backend/evqa/seed/pfbench.py`) | no |
| runs (ours, closed book, 4 baselines) | `configs/evqa/bench4/<field>-<system>.yaml`, `evqa run ... --text` | yes |
| compare | `evqa compare` | no |

All of it, resumable: `nohup ops/bench4.sh <job> > runs/bench4.log 2>&1 &` (`STOP_AFTER=papers|export|questions|runs`).

## Joining the worlds

Per field: the v1 40-paper pilot world (`runs/paperfactory/qwen40-<field>/world.json`) + the v2 3-paper pilot world.
Nothing is deleted; the old runs and Workbench domains stay.

| field | papers | entities | same thing (unified) | accidental shared words renamed | clashes |
|---|---|---|---|---|---|
| law | 43 | 120 | 3 (the courts) | 36 | 0 |
| llm | 43 | 131 | 0 | 39 | 0 |
| materials | 43 | 111 | 0 | 14 | 0 |
| medicine | 43 | 111 | 0 | 4 | 0 |

The seeded name maker drew the same invented words in both worlds (e.g. "the THUGRON-2 trial" is a type 2 diabetes
trial in v1 and a hyperparathyroidism trial in v2): accidents, so the second world's word is replaced by a fresh one
that is neither part of nor contains a used word (no "tukrapur" beside "tukrapurtinib"). Entities with the same label,
kind and attributes are one entity. No subject-object pair carries different relations in different papers, so there
are no real clashes; planted conflicts inside papers stay as they were. Every joined world passes `world.check`.

## Questions (pfbench)

40 per domain: lookup 4, effect 4, best 4, trend 3, list 4, conflict 3 (22 in corpus); absent 6, near_miss 6,
out_of_scope 6 (18 not reported). A type with too few candidates gives its share to lookup: law has no effect
measure, so law has lookup 8, effect 0. Gold rows come only from facts.jsonl; a value stated in several papers is one
gold row with all its papers. Wording is a fixed template; a model may reword later, checked by a verifier.

Tried on a stand-in export (every planned paper treated as passed): 40 questions in each field; llm, materials and
medicine fill every type as planned; law has no effect questions (its 4 went to lookup).

## Scoring (L3-text, `eval/text_answer.py`)

For a paperfactory domain: a separate reader prompt `ReadClaimsPF` (the medical one tells the reader to skip sample
sizes, which these questions ask for); numbers are compared without units (the units are field words such as
"sites"); the paper is not a setting to state (one gold row may stand in several papers); list and name-only conflict
questions are scored by the entity names the answer gives (F1, code only). L0-L3 from prism do not apply (no seed
graph): `evqa eval <run> --text` only.

## Open

1. Our own system (evqa spec/find/extract/answer) still assumes the drug shape; it will run on these questions but
   needs work to answer them well (option A, step 3; about 2-3 days).
2. The evqa `medical` set (40 papers, 174 questions, frozen) is not yet in `bench_medicine`: its facts would need
   the row shape and its questions its own gold path. `data/seed/materials` (seed-pipeline draft, no papers) is not
   joined either.
3. Nothing has run on Qwen: the GPU job ended before the paper runs started.
