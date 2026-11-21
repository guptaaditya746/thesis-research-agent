# paperfactory

A field-general benchmark builder for research assistants. One pipeline for every field; only the packs and the
settings change.

```
field pack + genre pack + settings
  -> world      invented entities and, per paper, planted facts (claims + near-miss decoys + planted conflicts)
                (world agent, or a hand-written file; always checked in code: world.check)
  -> seed       RDF graph, SHACL check, questions from the field pack's templates, gold answers by SPARQL
  -> materials  PaperOrchestra inputs per paper; holdings go in as DATA, never as finished sentences
  -> write      PaperOrchestra (external/paperorchestra) writes each paper (genre template, length = pages)
  -> check      every paper must agree with the WORLD: pack patterns + verifier (SUPPORTS / CONTRADICTS /
                ABSENCE_CLAIM / NEUTRAL); a flagged paragraph is rewritten once, then the whole paper once, then the
                paper is marked failed (paper.raw.md, paper.md, paper.repairs.json)
  -> eval       tagging (where each fact sits) + verifier, verifier test, judge validation, QA scoring with
                provenance by code, style-leak test
```

## Run

```bash
uv run paperfactory run --config backend/paperfactory/configs/law-pilot.json    # 3 papers, hand-written world
uv run paperfactory run --config backend/paperfactory/configs/law.json          # 20 papers, world agent
uv run paperfactory run --config ... --steps seed,materials                     # some steps only
uv run paperfactory check-world --config ... --world my-world.json
uv run paperfactory export-labels --config ... --out labels.csv --per-field 200   # hand labels for the verifier
uv run paperfactory label-metrics --labels a.csv --labels b.csv --answers verifier.json [--run-verifier --config ...]
```

Heavy runs go through Slurm (`srun --jobid=<job> --overlap ...`). Output goes to the run folder (`out`, under
`runs/`, not committed): world.json, seed.ttl, gold.json, papers/, work/<paper>/paper.md, tagged.json,
report.json, calls.jsonl (every model call with its cost). Steps reuse what exists, so a stopped run restarts.

## Settings (configs/*.json)

| Key | Meaning |
|---|---|
| field, genre | pack names (packs/fields/*.json, packs/genres/*/) |
| papers | papers per run (default 20) |
| pages | paper length; words = pages x the genre's words per page |
| models | model per job: world, writer, tagger, verifier, judge, rewriter, repair, qa, leak; `default` for the rest. A name (`claude-haiku-5-5` = `claude -p`; `qwen:<alias>` = that alias on the LiteLLM gateway) or the fields of `config.RoleModel`: backend (`claude_cli` / `openai`), model, base_url, context_window, timeout, max_parallel, max_tokens, price_in_per_mtok, price_out_per_mtok, local. Unknown cost is reported as unknown, never 0 |
| world_file | hand-written world instead of the world agent |
| qa_papers_per_question | papers each question is asked over (its own + ones sharing an entity) |
| leak_trials | tries in the style-leak test (0 = skip) |

## Packs

- Field pack: kinds of things (with attributes), relations (words + meaning + allowed object kinds), conflict
  pairs, question templates, the field's words for prompts and section names, notes for the world agent.
  law is tested (law pilot, 21 Nov 2026); medicine and materials are DRAFTS for review.
- Genre pack: template.md and guidelines.md with {PLACEHOLDERS} filled from the field and the settings, and
  genre.json (facts per paper, mention budget; `numeric_facts: false` tells PaperOrchestra to skip its
  number-fact gate). Built: argument. Not built yet: experiment (number facts; PaperOrchestra's original path).

## Known limits (first version)

- Style-leak test on the law pilot: 10-11% with fair decoys (chance 5%, bar 10%): borderline.
- The verifier, judge and QA default to the same model as the writer; set a different model family per job in
  `models` for final numbers (a model can favour its own writing).
- Facts are flat (subject, relation, source). Who holds a view and the author's stance are not modelled yet.
- 3 papers is a smoke test only; comparisons between systems need tens of papers per field.

## Law pilot on this system (21 Nov 2026, Haiku for every job, $0.42)

3 papers (2,700-3,200 words), 18 planted facts, all found in the papers (49 spans). The verifier has no
precision estimate yet: the old verifier test only reuses sentences the verifier itself accepted (circular); the
hand-labeled test is `export-labels` / `label-metrics` (labels.py).
Meaning judge 89.8% on paper wording and on answer wording (bar 90%: just under). QA over 7 questions: right
answer 100%, right answer with right evidence 93%, precision 57% (extra items: repeats and neighbouring facts).
Style leak 4.7% (7/150, 95% range 2-9%; chance 5%): passes, down from 19% when holdings were given as sentences.
