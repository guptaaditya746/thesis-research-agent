# Protected corpus rendering

The three-study EV2 development pilot (seed 1) retained no studies. Its
distributed level passed one of three papers and its contradictory level passed
none. Replaying cached drafts showed duplicated values: S001's distributed draft
put 29.9, 21.4 and 47.2 in a Method table and repeated them in Results prose.
Its contradictory draft stated those values in the Abstract, a Results table,
and Results prose. Retries preserved these violations. These are actual model
outputs, preserved in `synth/tests/fixtures/pilot-repeated-values.json` with their
original cache keys. The exact-string validator correctly rejected them.

## Contract

`synth build --renderer llm --assembly protected` is a hybrid generator.
Code renders factual passages using the existing plan and template renderer:
labels, definitions, claim sentences, decoy, result sentences or table, and
distributed spacing. The model writes the Introduction and Discussion, in
separate calls. Each receives only the section and main dataset and returns a
bounded `ProseReply.text`; it receives no measurements, claims, or effect label.
Each prose reply is checked for digits, headings, table markers, and additional
effect claims. A failed reply is repaired independently, with its rejected text
and specific checks, within the configured attempt limit. Failed passages and
checks are retained in fidelity history. Exhausted attempts exclude the study;
the template context left in a rejected artifact does not make it acceptable.

The final paper is assembled and anchored again. All existing deterministic
fidelity and level checks run on the final bytes. If `--verify-model` is supplied,
the existing independent blind extractor still reads the entire final paper.
A failed blind check excludes the study. The versioned `blind-reading-v1.txt`
verifier copies source numbers, units, quotes, and relative comparisons into a
typed schema. Code anchors the quotes, checks numeric tokens, normalizes units,
and computes percentage-point differences using Decimal. The reference condition,
metric and dataset must identify one extracted reference. This prevents the
observed verifier error of treating "6.7 percentage points higher" than 33.5 as
26.8 instead of 40.2. Invalid source readings get bounded repairs against the
source and failed check only; private truth never enters the repair prompt.
Assembly does not weaken validators,
change truth, or resolve disagreements in favor of the generator.

## Run

```bash
uv run synth build --name rag-llm-protected-pilot --seed 1 --studies 3 \
  --renderer llm --assembly protected --levels all \
  --model sub-model-1 --verify-model sub-model-2 --concurrency 1 \
  --out "$CORPORA" --cache "$EV/cache/synth-protected.jsonl"
```

On Slurm, invoke this through the runbook's `launch.sh`. Keep the original pilot
and use a separate name and cache. Build defaults to the original freeform mode;
variants inherit their base corpus's assembly mode unless explicitly overridden.
Protected mode bypasses the prose Results statement stage because code owns those
sentences. Metadata records this, the assembly mode, prompt/schema hash, assembly
source hash, model identities, served aliases and call settings. The cache retains
each model output and token usage. The original prompts are unchanged.

Use `--name rag-llm-protected-final-pilot` and a distinct output directory when
comparing the final verifier with the intermediate assembly-only pilot.

## Verification and limits

`uv run pytest synth/tests/test_protected.py` replays the observed failure and
checks all five levels, final anchors, targeted repair, cache replay, exhausted
retries and rejection by an independent verifier. The full synth suite checks
compatibility with existing corpus and variant behavior.

Measure retention on the same seed-1 development families before and after;
record any new blind-verification failures. Freeze separate study families before
making a general quality claim. A small pilot establishes feasibility only.
The two sub-model aliases share weights, so their agreement is correlated evidence.

This mode changes the generated text distribution: factual passages come from
templates and context is model-written. Its extraction scores must be reported
as hybrid-corpus results, separately from freeform LLM-corpus results. Higher
retention does not demonstrate better scientific prose or a stronger extractor.
The overnight engine comparisons continue to use the unchanged EV1 corpus.
