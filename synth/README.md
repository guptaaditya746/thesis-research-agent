# synth: the synthetic benchmark

Structured ground truth → papers written from it → fidelity-checked corpora, so extraction, integration
and synthesis can be scored separately against exact truth. Question: *Does retrieval-augmented
generation improve the factual accuracy of LLM-generated answers?* The files written are exactly those of
[docs/evidence-interfaces.md](../docs/evidence-interfaces.md) sections 1 and 2 (deviations at the end).

```
uv run synth build --name rag-s1 --seed 1 --studies 20 --renderer template \
    [--levels explicit,paraphrased|all] [--effects supports=0.6,contradicts=0.2,neutral=0.2] --out corpora/
uv run synth build ... --renderer llm --model sub-model-1 [--verify-model sub-model-2] [--attempts 3]
uv run synth sample --corpus corpora/rag-s1-mixed --n 5 --seed 0     # human review sheet (.md + .csv)
```

`build` writes `<name>-<level>` for each level plus `<name>-mixed` (levels round robin over the studies).
All corpora of one build share the study set and the paper ids, and a mixed paper is byte for byte the
paper of its level's corpus, so a change in score between corpora comes from the rendering alone.

## Ground truth (`truth.py`)

Seeded with one `random.Random(seed)`, no clock. Each study has a baseline and a rag condition plus 0-2
distractor conditions (ablations, other systems), one question metric (`factual_accuracy` or
`hallucination_rate`) plus 1-2 distractor metrics (BLEU, ROUGE-L, latency), two datasets (the first is the
main one) and a measurement for every condition × metric × dataset. Fractions have three decimals with a
non-zero last digit (so 62.4%, never 62.0%), all values within a study are distinct, and the main
rag-baseline difference differs from every value (the complex level writes it). The effect is
`evidence.rules.effect` on the main dataset's rag/baseline pair of the question metric (the second dataset
shows the same direction); the answer is `evidence.rules.label`. `--effects` sets the share of true
effect directions (largest remainder), so corpora with every answer label can be made. The author claim
agrees with the data except in contradictory papers.

## Difficulty levels (`levels.py`, checked by `levelcheck.py`)

Facts per paper: all conditions on the question metric on the main dataset; complex: everything.

| Level | Definition |
|---|---|
| explicit | Each value is stated once, in one Results sentence that names the condition and the metric verbatim (the study's own labels) and the dataset; values as percent (`62.4%`). No tables. |
| paraphrased | Conditions and the metric are never called by their labels, only by descriptive synonyms (`the model that answers from its own parameters`, `share of answers whose facts are all correct`); values in prose, in at least two of three formats: `62.4%`, `0.624`, `624 out of 1,000`. No tables. |
| distributed | Values appear only in one Markdown table whose rows are short codes (`B`, `R`, `A1`, `A2`) and whose value column header is the metric's abbreviation (`FA (%)`, cells `62.4`); the codes and the abbreviation are defined in the Method section, at least 300 characters (in practice an implementation-details subsection) before the table. No sentence states a value; no full condition label is in the table. |
| complex | All conditions with the distractors, the question metric and 1-2 distractor metrics, two datasets, in one table (columns System, Dataset, one per metric; full labels); the rag value on the question metric of the main dataset is `see text` in the table and given only relatively in a sentence (`7.0 percentage points higher than the …`). The reader must pick the question-metric pair on the main dataset. |
| contradictory | Values in a table with full labels, but the stated claim (abstract and conclusion) disagrees with the data: an improvement where the data show none or a worsening, "no effect" where they show an improvement. In odd-index studies the abstract also states a wrong rag value (a decoy, `decoys.json`) that fits the false claim and lies more than 0.0075 (evaluation tolerance 0.005 plus a margin) from every true value of the study, so taking it never scores; in the rare study where no such value exists (about 2 %) there is no decoy. The table is the truth: `effect` comes from it, `author_claim` is the claim as stated. |

## Placements

Every rendering of a fact is a placement `{fact, role, paper, start, end, exact}` with role `value`,
`condition_label`, `metric_label` or `claim`: raw code-point offsets into the stored text
(`agent/anchor.read_text`). The template renderer writes text through `text.Doc`, which records the
offsets as it writes, so placements are exact by construction; the LLM renderer locates them afterwards.
Codes and abbreviations are placements of their condition/metric where the plan puts them, on table lines
and in their definition sentence (one that also holds the full name), so "Appendix B" is not condition B; a metric's description (in the Method
section) is a `metric_label` placement too. Ground truth `label`/`name` are the names the paper uses (the
synonym in paraphrased papers); `aliases` hold the codes.

## Renderers

- `render_template.py`: deterministic Markdown (title, abstract, introduction, method, results, discussion,
  conclusion) with filler from the fixed vocabularies in `vocab.py` (no digits, no fact names in filler).
  Same seed, byte-identical corpus.
- `render_llm.py`: the model gets the rendering plan (facts, level instructions, the exact strings: values,
  claim sentences, decoy, names) and returns `{"markdown": …}` (`gold/llm.structured_reply`). Values, claims
  and the decoy are located with `anchor.find` (missing or ambiguous = failure); names at every
  word-bounded occurrence. Up to `--attempts` tries, each failure's reasons fed into the next prompt. All
  calls cached (`gold/llm.JsonlCache`, `<out>/.synth-cache/llm.jsonl`), key = prompt hash + model identity +
  full prompt (holds the plan) + seed. Models in `corpus.json` `models`. Key only from
  `$LITELLM_MASTER_KEY`; errors pass through `gold/llm.redact`.

## Fidelity (`fidelity.py`, `fidelity.json`)

Per paper: `lf_only`; `facts_rendered` (every planned fact has a rendering of its role); `anchored` (each
placement holds its exact text and `anchor.find` with its context lands on it); `values_match` (the rendered
string reads as the true value; relative ones against the baseline); `values_unique` (a value string occurs
only where placed); `values_associated` (a value's table row names its condition and no other, its column header its metric, its Dataset cell its dataset; in prose its sentence names its condition and metric and no other, a relative value its own condition before and the baseline after; `assoc.py`); `labels_covered` (every occurrence of a name is a recorded placement of that fact);
`stray_numbers` (no other number reads as one of the study's values as is, as percent or per 1,000);
`level_<level>` (the level's property); LLM only: `required_strings`, `model_call`, and with
`--verify-model` `blind_reextraction` (a model that never saw the plan must recover every (condition, value) pair:
the value within 0.005, reported under one of the condition's names or its code). A study failing at any level is left out of every corpus of the set and reported with
`excluded_reason` and its attempt `history`.

`synth sample` writes `review/review-s<seed>.md` and `.csv`: per sampled paper, every placement with its
truth in words, line, offsets, exact text, context, and tick columns `present`, `states_truth`,
`unambiguous`, `notes`.

## Example

`synth/examples/rag-demo-*`: template renderer, seed 1, 6 studies (answer `mixed`: 4 supporting, 1
contradicting, 1 neutral). A test rebuilds it and compares bytes; after changing anything in `synth/`, run
`uv run synth build --name rag-demo --seed 1 --studies 6 --out synth/examples` (the generator's code hash
is in `corpus.json`). `.gitattributes` keeps it LF on every checkout.

## Deviations from docs/evidence-interfaces.md

- `corpus_id` is `<name>-<8 hex>`, the hex from the hash of the papers' ids and sha256s, not
  `<name>-<level>`: the manifest must not hint at the level (a hash of name and level could be guessed).
  Two corpora with the very same papers (a one-level build and its mixed corpus) share the id. The directory name is `<name>-<level>` as documented.
- Extra file `decoys.json` (the contradictory level's wrong stated values with offsets); systems under test
  never read it.
- `fidelity.json` is `{corpus_id, papers: [{id, ok, checks, attempts, history, excluded_reason?}],
  excluded}`: `history` holds the failed checks of each failed attempt.
