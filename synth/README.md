# synth: the synthetic benchmark

Structured ground truth → papers written from it → fidelity-checked corpora, so extraction, integration
and synthesis can be scored separately against exact truth. The topic comes from a recipe,
`domains/<name>/generator.yaml` (`synth/recipe.py`; `--domain`, default the default pack of
domains/default.yaml): the condition and metric names, the contexts, the filler and claim sentences, the
prompt words and the value ranges. The code holds no topic word (D35; `evidence/tests/test_no_topic_words.py`
checks synth/). The question is the one of the recipe's `effect_protocol`. The files written are exactly
those of [docs/evidence-system.md](../docs/evidence-system.md) A1 and A2 (deviations at the end), and
`corpus.json` records the recipe (`recipe: {domain, sha256}`, generator version 3).

```
uv run synth build --name demo-s1 --seed 1 --studies 20 --renderer template [--domain D] \
    [--levels explicit,paraphrased|all] [--effects supports=0.6,contradicts=0.2,neutral=0.2] --out corpora/ \
    [--duplicates N] [--missing N] [--outliers N] [--irrelevant N]
uv run synth build ... --renderer llm --model sub-model-1 [--verify-model sub-model-2] [--attempts 3]
uv run synth variant --corpus corpora/demo-s1-mixed --study S003 --direction contradicts [--out DIR] [--protocol P]
uv run synth sample --corpus corpora/demo-s1-mixed --n 5 --seed 0     # human review sheet (.md + .csv)
```

`build` writes `<name>-<level>` for each level plus `<name>-mixed` (levels round robin over the studies).
All corpora of one build share the study set and the paper ids, and a mixed paper is byte for byte the
paper of its level's corpus, so a change in score between corpora comes from the rendering alone.

## Knobs (`--duplicates`, `--missing`, `--outliers`, `--irrelevant`; `truth.with_knobs`)

The supervisor's variants of section 6 (duplicates, missing information, unusually large effects); the
mechanics and the irrelevant papers are ours (docs/evidence-system.md F2). Each knob draws from its own
`random.Random(f"synth:{seed}:{knob}")`, so the plain build (every knob 0) is byte for byte what it was and
adding one knob does not reshuffle another. The plain build is byte-identical for every seed unless two
drawn studies share a treatment/control pair, which forces the later one to be drawn again (it never
happens for the seeds in use). Outliers are applied first, duplicates copy the (possibly redrawn) study,
missing never touches an outlier or a duplicated original, irrelevant papers come last.

| Knob | Papers | Ground truth |
|---|---|---|
| `--duplicates N` | N extra papers (ids after the set) that report an existing study again: same conditions, metrics, datasets and values (fact ids under the new study id), a different title (the template takes the next title template; the LLM renderer is told the original's title and a `title_differs` check enforces it) and filler, in the mixed corpus at the original's level | `duplicate_of`, `flags: ["duplicate"]`, effect as the original's; in `answer.duplicates`, not counted |
| `--missing N` | N studies lack the control (alternately the treatment) measurement on the question metric on both datasets: no sentence states it, a table cell holds an en dash (`levels.MISSING_CELL`), no relative value, no decoy | `missing: "control" \| "treatment"`, `effect: {direction: "undetermined", delta: null, metric, treatment: id \| null, control: id \| null, reason: "missing_control" \| "missing_treatment"}`; in `answer.undetermined` |
| `--outliers N` | N supporting studies get their pair redrawn with an improvement in the recipe's `effects.large` | `flags: ["large_effect"]`; counted |
| `--irrelevant N` | N extra papers with no experiment, from the recipe's `text.irrelevant`: a survey of the question's topic (the term screen lets it through; the screening question must say no) alternating with a paper on another topic (no screen term at all, not even as a substring of a word, so a screen without word boundaries finds nothing either); no digits; the same text at every level and in both renderers (the LLM renderer makes no call for them) | `relevant: false`, no conditions, metrics, measurements or claim, `effect.reason: "screened_out"`; in `answer.undetermined` |

Every study record has `relevant`, `flags` (sorted), `duplicate_of` and `missing`; the flags are what
`evidence.rules.duplicates` and `rules.large_effects` find on the studies actually written (after fidelity
exclusions) with the protocol's `synthesis.flags` (so a natural large effect is flagged in a plain build too), plus `claim_disagrees` for a
contradictory-level paper whose effect is determined. The generator asserts the rules find exactly the
planted duplicates and outliers (otherwise `SystemExit` naming the knob: too few supporting studies, a
natural large effect next to a planted one, a protocol with `flags.duplicates: false`), and keeps the
treatment/control pairs of distinct studies apart on both datasets (a colliding study is drawn again).
`answer` gains `undetermined`, `duplicates` and `flags: {claim_disagrees, duplicate, large_effect}`; the
label is the label table over the counted studies. `corpus.json` gains `settings: {name, studies, mix,
levels, duplicates, missing, outliers, irrelevant}`.

## Counterfactual variant (`synth variant`, `variant.py`)

The supervisor's controlled variant: change one study's result and the answer should shift predictably
(docs/evidence-system.md F3). `synth variant --corpus DIR --study S --direction D` draws the base corpus's
study set again from its `settings`, redraws S's treatment/control pair on both datasets with direction D
from `random.Random(f"synth:{seed}:{S}:variant:{D}")` (same ids, names, datasets and distractor values;
the claim follows the new effect, a contradictory-level paper keeps a false claim), re-renders only S's
paper at its level (default: the base corpus's renderer; the usual renderer options) with the same
fidelity checks (a failure is an error), re-applies the flags to the whole set, and writes
`<corpus>-cf-<S>-<D>` (or `--out`): every other paper copied byte for byte (sha256 verified against the
base manifest), `corpus.json` with `variant: {base_corpus_id, study, from, to}`, and `variant.json`
`{base_corpus_id, corpus_id, study, paper, from, to, changed: [{measurement, from, to}], expected:
{before: {label, counts}, after: {label, counts}, label_changes}}`. S must be a counted study (not a
duplicate, not missing, not irrelevant) and D must differ from its effect. The base corpus does not hold
the protocol file, so `--protocol` (default the recipe's effect protocol) must hash to the base's
`protocol.sha256`, and the recipe it names (`corpus.json` `recipe`; none before generator version 3: the
default pack's) must hash to its `sha256`; otherwise the command refuses.

## Ground truth (`truth.py`)

Seeded with one `random.Random(seed)`, no clock. Each study has a control and a treatment condition (the
protocol's compared roles, named from the recipe's `sides`) plus 0-2 distractor conditions (the recipe's
`others`: ablations, other systems), one question metric (one of the protocol's synthesis metrics, named from
the recipe's `question_metrics`) plus 1-2 distractor metrics (`other_metrics`), two datasets (the recipe's
`contexts`; the first is the main one) and a measurement for every condition × metric × dataset, drawn in the
metric's `range` (a compared pair from `pair_range`, its difference from `effects`). Fractions have three decimals with a
non-zero last digit (so 62.4%, never 62.0%), all values within a study are pairwise more than 0.0075 apart
(`truth.DECOY_GAP`, the evaluation tolerance 0.005 plus a margin; checked as `values_apart`), so a value
read from the wrong cell never matches another fact by value alone (hence a neutral effect is a
difference of 0.008 or 0.009, above the gap and below the protocol's `min_effect`), and the main
treatment-control difference differs from every value (the complex level writes it). The effect is
`evidence.rules.effect` with the protocol's parameters on the main dataset's treatment/control pair of the
question metric (the second dataset shows the same direction); the answer is the protocol's label table
(`evidence.rules.label`). Which protocol: `--protocol P` (default the recipe's `effect_protocol`);
its `synthesis` block gives the condition roles, the question metrics and their direction, the neutral
band, the claim vocabulary and the label table, and its id and sha256 are recorded in `corpus.json` and
`ground_truth.json` (docs/evidence-system.md Part C). `--effects` sets the share of true effect directions
(largest remainder), so corpora with every answer label can be made. The author claim agrees with the
data except in contradictory papers.

## Difficulty levels (`levels.py`, checked by `levelcheck.py`)

Facts per paper: all conditions on the question metric on the main dataset; complex: everything.

| Level | Definition |
|---|---|
| explicit | Each value is stated once, in one Results sentence that names the condition and the metric verbatim (the study's own labels) and the dataset; values as percent (`62.4%`). No tables. |
| paraphrased | Conditions and the metric are never called by their labels, only by descriptive synonyms (`the model that answers from its own parameters`, `share of answers whose facts are all correct`); values in prose, in at least two of three formats: `62.4%`, `0.624`, `624 out of 1,000`. No tables. |
| distributed | Values appear only in one Markdown table whose rows are short codes (`B`, `R`, `A1`, `A2`) and whose value column header is the metric's abbreviation (`FA (%)`, cells `62.4`); the codes and the abbreviation are defined in the Method section, at least 300 characters (in practice an implementation-details subsection) before the table. No sentence states a value; no full condition label is in the table. |
| complex | All conditions with the distractors, the question metric and 1-2 distractor metrics, two datasets, in one table (columns System, Dataset, one per metric; full labels); the treatment value on the question metric of the main dataset is `see text` in the table and given only relatively in a sentence (`7.0 percentage points higher than the …`). The reader must pick the question-metric pair on the main dataset. |
| contradictory | Values in a table with full labels, but the stated claim (abstract and conclusion) disagrees with the data: an improvement where the data show none or a worsening, "no effect" where they show an improvement. In odd-index studies the abstract also states a wrong treatment value (a decoy, `decoys.json`) that fits the false claim and lies more than 0.0075 (evaluation tolerance 0.005 plus a margin) from every true value of the study, so taking it never scores; in the rare study where no such value exists (about 2 %) there is no decoy. The table is the truth: `effect` comes from it, `author_claim` is the claim as stated. |

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
  conclusion) with filler and sentence templates from the recipe's `text` (no digits, no fact names in
  filler). Same seed, byte-identical corpus.
- `render_llm.py`: the model gets the rendering plan (facts, level instructions, the exact strings: values,
  claim sentences, decoy, names) and returns `{"markdown": …}` (`modelcall.ask`). Its prompts
  (`prompts/render-v3.txt`, `statements-v2.txt`, `blind-v3.txt`) are templates filled from the recipe
  (`text.prompt_words`, `text.blind_examples`, `reporting.dataset_size`); the older prompt files stay for
  replay. Values, claims
  and the decoy are located with `anchor.find` (missing or ambiguous = failure); names at every
  word-bounded occurrence. Up to `--attempts` tries, each failure's reasons fed into the next prompt. All
  calls cached (`modelcall.JsonlCache`, `<out>/.synth-cache/llm.jsonl`), key = prompt hash + model identity +
  full prompt (holds the plan) + seed. Models in `corpus.json` `models`. Key only from
  `$LITELLM_MASTER_KEY`; errors pass through `modelcall.redact`.

## Fidelity (`fidelity.py`, `fidelity.json`)

Per paper: `lf_only`; `facts_rendered` (every planned fact has a rendering of its role); `anchored` (each
placement holds its exact text and `anchor.find` with its context lands on it); `values_match` (the rendered
string reads as the true value; relative ones against the baseline); `values_unique` (a value string occurs
only where placed); `values_associated` (a value's table row names its condition and no other, its column header its metric, its Dataset cell its dataset; in prose its sentence names its condition and metric and no other, a relative value its own condition before and the baseline after; `assoc.py`); `labels_covered` (every occurrence of a name is a recorded placement of that fact);
`stray_numbers` (no other number reads as one of the study's values as is, as percent or per the recipe's
`count_base`); `added_numbers` (no number outside the value placements, the decoys and
`fidelity.allowed_numbers(recipe)`: the recipe's `reporting.allowed_numbers` (the dataset size), `Table n`,
`Section n`, `Figure n`, `Appendix n`, `Equation n`, list markers, plus the `A1`-style codes of the recipe's
`other_codes`; fails with the number, its offset and context); `added_claims` (no sentence outside the claim
placements matches the recipe's `text.claim_subject` and one of its `text.claim_cues`, the generator's copy of
the claim wording, over the regex extractor's own sentence split); `level_<level>` (the level's property;
`irrelevant` for a paper with no experiment: nothing placed,
no table); LLM only: `required_strings`, `model_call`, and with `--verify-model` `blind_reextraction` (a
model that never saw the plan must recover every (condition, value) pair: the value within 0.005, reported
under one of the condition's names or its code) and `blind_extra` (it must return nothing else; the decoy
and the complex level's relative difference, which the paper does state, are allowed). The two added-content
checks enforce the writer prompt's rules 3 and 4 (docs/evidence-system.md G.2); the template renderer's own
papers pass them. What they cannot catch: a number spelled out in words ("seventy percent"), a claim that
names the condition by a synonym the `claim_subject` regex does not match, and
anything in a heading or a table line, which the sentence split leaves out; `blind_extra` with a verify
model is the check for those. A study failing at any level is left out of every corpus of the set and
reported with `excluded_reason` and its attempt `history`.

`synth sample` writes `review/review-s<seed>.md` and `.csv`: per sampled paper, every placement with its
truth in words, line, offsets, exact text, context, and tick columns `present`, `states_truth`,
`unambiguous`, `notes`.

## Example

`synth/examples/rag-demo-*`: template renderer, seed 1, 6 studies (answer `mixed`: 4 supporting, 1
contradicting, 1 neutral), built by generator version 2. Its files are pinned by sha256
(`synth/tests/data/example_sha256.json`; D36: an old corpus keeps its bytes) and no longer rebuilt, since
`corpus.json` holds the generator's code hash. That the generator still draws the same set and writes the
same papers is pinned in `synth/tests/data/rag_set_sha256.json`. `.gitattributes` keeps it LF on every checkout.

## Deviations from docs/evidence-system.md (Part A)

- `corpus_id` is `<name>-<8 hex>`, the hex from the hash of the papers' ids and sha256s, not
  `<name>-<level>`: the manifest must not hint at the level (a hash of name and level could be guessed).
  Two corpora with the very same papers (a one-level build and its mixed corpus) share the id. The directory name is `<name>-<level>` as documented.
- Extra file `decoys.json` (the contradictory level's wrong stated values with offsets); systems under test
  never read it.
- `fidelity.json` is `{corpus_id, papers: [{id, ok, checks, attempts, history, excluded_reason?}],
  excluded}`: `history` holds the failed checks of each failed attempt.
