# Qwen as the paper writer (writer prompt v2)

Status: test-run level, 21 Nov 2026. Measurements: `runs/scratch/qwen_quality/` (`summary.json`, `metrics.json`, `verifier.jsonl`).

## What it is

The synthetic benchmark papers are written by the vendored PaperOrchestra (`external/paperorchestra`), driven by
`backend/evqa/paperwriter.py`. Two things can now be switched:

- **Model**: `claude-*` (Claude Code headless, the frozen benchmark set used `claude-haiku-5-5`) or `qwen:<alias>`
  (the llm-setup LiteLLM gateway, thinking off, JSON schema enforced by the server). Same cache, call log and 3
  shared slot locks (`data/cache/claude-slots`) for both.
- **Prompt version**: `v1` (default; the prompts the frozen Claude-written papers were made with, unchanged
  byte for byte, so their cache keys still hit) or `v2` (below).

## How to switch the writer to Qwen

Run on the GPU job (Qwen is only reachable there), from the repo root:

```
srun --jobid <job> --overlap ops/injob.sh uv run evqa paper write <domain> --model qwen:orch-model --prompt-version v2
```

`--paper P-xyz-01` writes one paper. Careful: `evqa paper write` writes `data/dataset/<domain>/<paper>/paper.md`,
so do not run it on a domain whose papers are frozen (medical). For experiments, call
`paperwriter.write_paper(<copy of the brief>, paper_out=..., model="qwen:orch-model", prompt_version="v2",
style_examples=...)` as `runs/scratch/qwen_quality/run.py` does.

v2 needs style examples. `write_paper` builds them with `evqa.research.style.build` when not given; that calls
Semantic Scholar, which needs the network: on a node without it, the stored excerpts are used and retrieval is
skipped (S2 answers are cached under `data/cache/s2/`, so prebuilding on the login node also works).

## What v2 changes (and what it does not)

| Call | v1 | v2 |
|---|---|---|
| Outline | unchanged | unchanged (reads `guidelines_v2.md`) |
| Introduction + Related Work | 4-6 paragraphs intro, 350-500 words related work in `###` clusters | 3-4 paragraphs (300-450 words); Related Work 2 paragraphs (150-250), no subsections, only work on the same question, this study in at most one sentence |
| Section writing | long "critical instructions" | short contract per section + `STYLE_RULE_V2` + new input `style_examples` |
| Refinement | unchanged | + short plain-writing rule (`REFINE_STYLE_V2`) |
| Review, value repair | unchanged | unchanged |
| Guidelines | 2,400-3,200 words total | per-section word ranges (total about 1,600-2,500) |

`STYLE_RULE_V2` (in `methods/prompts/writer_v2.py`): copy only the manner of the examples; never a number, drug
name, sample size, CI, p-value, population detail or claim from them; leave out what the log lacks and say so once
in the limitations; each paragraph adds new information; vary sentence openings; drop sentences that fit any trial.
It has the three examples the prompt policy asks for: normal (a sentence value written journal-style), confusing
(an example shows a CI and P value the log does not have) and missing (an example opens with a participant count
the log does not give).

## Style examples (code-chosen, never model-chosen)

`backend/evqa/research/style.py` builds the `style_examples` input per paper:

1. two stored excerpt sets from `data/style/<domain>/` (short CC BY excerpts of 4 real add-on-to-metformin
   trials: participants paragraph, a mean-difference-vs-placebo Results paragraph, one results table, a limitations
   paragraph; licence and source in each `source.json`), picked by a hash of the paper title so papers do not all
   see the same two;
2. up to two real abstracts retrieved from Semantic Scholar (`backend/evqa/research/s2.py`): one query built by
   code from the brief's design, population and first measure, never the made-up drug name; CC BY / CC0 only; if
   the query returns nothing, words after the design words are dropped one at a time.

S2 client rules: key from `S2_API_KEY` (environment or the git-ignored `.env`), sent only as `x-api-key`, never
logged or cached; one request per 1.1 s across threads; retry with backoff on 429 / 5xx; responses cached under
`data/cache/s2/` keyed by the URL (which holds no key).

## Checks in code

`utils/fact_check.py`, reported in every run's final check (`writer_log.jsonl`, `facts_check.json`):

- `unsupported_numbers`: every number in the paper (integers too) that is in neither brief file, except heading
  lines, labels (`Table 2`, `type 2`) and years. Stricter than the old `extra_numbers` (decimals only).
- `exemplar_leaks`: numbers (decimals, or integers with 3+ digits) that are in a style example but not in the
  brief, and example drug names used in the paper.
- The old value check, placement check and bounded repair are unchanged.

Tests (fake backends, no network, no GPU): `backend/evqa/tests/test_qwen_writer.py` (Qwen v2 end to end through a
fake LiteLLM gateway, CLI flags, S2 throttle / retry / cache / key privacy / licence filter, query without the
drug name, number audit) and the existing `test_paperwriter.py`.

## Result of the first comparison (5 briefs, 21 Nov 2026)

On P-med-01, -10, -11 (test) and P-med-17, -18 (practice), Qwen v2 found all 67 values, each in its planned place,
with no naming problems and nothing copied from the style examples. It scored best of the three writers on
repetition (repeated 4-grams 0.144 vs 0.176 for Qwen v1 and 0.164 for Claude; distinct-2 0.637 vs 0.576 and
0.573), and was about 35% faster than Qwen v1. A blind Haiku verifier preferred v2 over Claude 7/10 and v1 over
Claude 9/10. No writer was ever taken for a real paper (0/10 each), because the briefs give no n, CIs or P values.

Known faults of v2:
- It is short: 1,635 words against 2,546 for Claude.
- In 2 of 5 papers it invented a number about prior work ("12 to 24 weeks"). `unsupported_numbers` catches this,
  but nothing repairs it yet.
- It still writes a "not reported in this study" sentence in Methods.

Candidate v3: a bounded repair call for `unsupported_numbers`, and a rule plus an example that keeps the "not
reported" sentence out of Methods.

## v2r: v2 + a research tool Qwen uses itself (C8)

`--prompt-version v2r`. Before writing, `evqa.research.agent.research` runs a bounded loop:

- Each step is one DSPy call (`ResearchStep`) on Qwen orch-model with thinking off. It goes through the evqa
  recorded LM cache and holds one of the shared slot files.
- The model sees the study design, population, arms, time points and measures. The made-up drug names and codes
  are replaced by "the study drug".
- It also sees the queries so far, the results so far (id, title, year, venue, licence, the first 300 characters
  of the abstract), the number of searches left, and feedback on a rejected step.
- It answers `search` + a query, or `done` + picks (`style` or `reference`, each with a one-sentence reason).

Code enforces the rules:

- At most 5 searches. When the cap is reached, one final `FinalPicks` call. At most 8 model calls in all.
- Queries: no more than 12 words, no repeats, no drug name or code.
- Picks must be ids that appeared in the results.
- A `style` pick needs CC BY / CC0 and an abstract of at least 120 words. At most 2 style and 4 reference picks.
  A reference needs an author and a year.
- Every step goes to `runs/paperwriter/<paper>/research.jsonl`. The summary goes into the `run` event of
  `writer_log.jsonl`.
- Searches cover all of Semantic Scholar, not only open access, and keep the licence field.

How the picks are used:

- Style picks are added to the stored excerpts.
- References (first author, year, venue, title, and a one-line gist with decimals, percentages and 3+ digit
  numbers removed) go only to the Introduction and Related Work call. It may cite them as "(Surname et al., YEAR)".

Checks after writing:

- Every citation must match a reference by author and year. Others are reported as `citations.unknown`.
- References that are not cited are dropped (`citations.dropped_uncited`).
- `## References` is appended with the cited ones only.
- `citation_map.json` holds the cited references.
- `exemplar_leaks` also covers the reference abstracts.

Tests: `backend/evqa/tests/test_research_tool.py`. It uses a fake LM and fake search and covers the cap, the
drug-name, repeat and length rejections, the pick checks, the citation check and an end-to-end v2r run.
