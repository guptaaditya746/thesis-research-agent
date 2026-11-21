# Prompt for Codex (v2): domain-free settings + removing score-inflating rules

You work in this repo (thesis-research-agent), on the GPU compute node. Read first: AGENTS.md, CLAUDE.md,
docs/prompt-writing.md (mandatory for every prompt change), docs/design/slice1.md, docs/design/population.md
(plan v2, the plan you implement), docs/design/audit-inflation.md (your Part A audit). Do not commit. Never touch
llm-setup/ (read-only). Never print LITELLM_MASTER_KEY or the S2 key in .env. At most 3 LLM calls at once.
LLM = Qwen through the gateway (configs/evqa/*.yaml, `think: false`); run pipeline commands as
`ops/injob.sh uv run ...` (on the node the gateway is 127.0.0.1:4000).

## What changed since v1 (stop and switch)

Aditya: the domain will change (materials science, LLM papers, law). So plan v1 (fixed medical patient fields +
MeSH) is dropped as the main design: it is a domain-bound, pre-LLM style information-extraction schema. Your v1
work (Facet/Population contracts, backend/evqa/population.py, data/vocab/mesh-descriptors-2026.tsv.gz) becomes an
optional medical plug-in (an ablation) or is removed; the pipeline must not depend on it.

THE RULE for every change: no domain word lists, domain regexes, domain field names or domain thresholds in the
pipeline (spec/, find/, extract/, answer/) or the scorer (eval/). The LLM decides meaning; code checks grounding
(quotes, offsets, numbers) and structure (ids, consistency, caps). Domain knowledge may enter only as (a) the LLM's
own knowledge, (b) an optional per-domain plug-in file the pipeline runs without, (c) the benchmark's intent cards
(simulated user answers in data/dataset, not pipeline code).

Other work is going on in the same repo; do not edit: data/seed/medical_holdout/, data/dataset/medical_holdout/,
configs/evqa/holdout-*.yaml, runs/ (except your own run folders), external/paperorchestra/, data/style/,
backend/evqa/research/, data/cache/s2/. A hold-out score run may be running: do not change files it reads until
it ends (ask Aditya if unsure).

## Part B — implement docs/design/population.md (plan v2), in order, tests at each step

1. Spec picks the dimensions per question (LLM): open points proposed from the question, not a fixed medical list.
   Fixed values come from the question text with a quote checked against the question. Prompt examples from three
   domains (medicine, materials, ML), none from our seed (no metformin, HbA1c, sitagliptin, 24 weeks, -0.78).
2. Extract reads settings per paper (LLM): one value per dimension + quote, or "not stated". Code checks: quote in
   paper.md, value supported by the quote, numbers in the value appear in the quote; one repair call with the
   failed checks, then "not stated" (noted). Rows point to their SettingSet. Spec never reads papers.
2b. Extra settings: in the same Extract call, the model may report a dimension Spec did not list that the paper's
   rows vary on (with a quote per value). Code keeps it only when quotes check and the rows really differ on it;
   Answer adds it as a column marked "found in the papers, not asked" (never pooled silently). Test with a fake
   paper that reports fasting and fed values for one dose.
3. Links (LLM generator + separate LLM verifier, docs/prompt-writing.md): only for pairs Answer must compare
   (capped by code); "same / different / unknown", the differing dimension, a quote from each side. Code accepts
   "same" only when both agree and quotes check; groups = connected components, split on pairwise conflicts.
4. Answer: fit and grouping by accepted links; "unknown" shown as "can't tell"; label made by code.
5. Scorer: gold setting set by provenance (row's paper id + quote offsets -> seed context), never by wording;
   delete `group_of` and the measure one-shared-word rule (`GENERIC`); a separate blind LLM judge checks the
   user-visible label against the seed context description, reported separately in eval.json.
6. Delete harmonise/cluster/guard/QUALIFIERS/ON_DRUG, GroupClusters prompt, patient-group FILLER/SPELL, and fix or
   delete every Part A row marked tuned. Replace seed-derived prompt examples with non-seed, multi-domain ones.
7. Add a tiny second-domain test fixture (3 fake materials-science papers + 2 questions, fake LM) that runs Spec ->
   Find -> Extract -> Answer, to prove nothing is medical-bound.
Checkpoint after step 2: show Aditya the dimensions and settings Qwen produced for the practice questions/papers
(P-med-17..20) before building steps 3-7.

## Part C — standard libraries only where they are domain-free

Use a library to remove a hand-written rule only if the library itself is domain-free:
- RapidFuzz (already a dependency): quote anchoring with a score (`partial_ratio_alignment`), alias-to-known-name
  similarity as a candidate signal (the LLM + quote check still decides). Thresholds in configs/evqa/linkage.yaml,
  chosen on practice only.
- markdown-it-py: real Markdown parse for passages (headings, tables) with exact offsets (text == paper[start:end]).
  It was removed from pyproject in the old-code cleanup; re-add pinned if you use it.
- Pint (+ quantulum3 if it helps): numbers with units, any domain (mmol/L, MPa, tokens/s); keep norm.py's sign rule
  and decimals; unit table from QUDT, not hand lists.
- pysbd: sentence splitting for quotes.
- vLLM structured output through the gateway (`response_format: json_schema`) in lm.py, so replies are valid JSON;
  keep code checks and bounded retries.
- Splink / dedupe: only if the LLM link step (Part B.3) is too slow at scale; they need fixed fields, so they fit
  only after settings are extracted. Not now unless Aditya asks.
- Domain-bound libraries (scispaCy, medspaCy, MeSH linkers, GLiNER with medical labels): only as an optional medical
  plug-in, off by default, never needed for the pipeline or the scorer to run.

## Rules for checking yourself

- Tune ONLY on the practice split (copy configs/evqa/bench-qwen.yaml with `split: practice`). Never open
  per-question outputs of test or hold-out runs to fix things. Run test once at the end, for comparison only.
- Generation and verification separate; code checks every LLM output.
- `uv run pytest -q backend` must pass; Workbench `cd frontend && npx vitest run` if you touch UI types.
- Report LLM calls and tokens per question before/after (the link step adds calls).

## Report (short, plain words)

What changed per step; the checkpoint output; which hand rules were deleted and which stayed (why); practice
scores before/after; calls per question; the one test score with the caveat; anything left undone.
