# Prompt for a new session: four-domain benchmark (22 Nov 2026)

Paste everything below the line into a new Claude Code session started in `thesis-research-agent/`.

Decided 22 Nov 2026: one set per domain, no v1/v2. Each set is built by joining and improving all existing data for that domain; nothing is deleted.

---

You are continuing Aditya's thesis work in this repo. Read `CLAUDE.md`, `AGENTS.md`, `docs/prompt-writing.md`,
`docs/architecture.md`, `services/paper-factory/AGENTS.md` and `services/paper-factory/src/paperfactory/README.md`
before doing anything. Follow CLAUDE.md's reply rules: short replies, plain words, one next action, stop on bugs.

## Goal

One benchmark with **four domains: law, llm, materials, medicine**. For each domain:
1. a corpus of good papers (every paper that passes, from about 60 generated), made by joining that domain's existing data and improving it with the improved paper generator;
2. **40 test questions of mixed types**, with gold answers computed by code from the truth files (never by a model);
3. runs of **ours** (evqa) and **every baseline** on the same questions and papers, scored the same way;
4. one comparison report across the four domains.

**One dataset per domain, no version layers.** All existing data for a domain is input to that domain's one set. Nothing is deleted, and no old set becomes an extra benchmark set.

## What exists (checked 22 Nov 2026)

| Dataset | Where | State |
|---|---|---|
| `medical` | `data/seed/medical`, `data/dataset/medical` | evqa seed pipeline, invented diabetes drugs, numbers. 40 papers, 196 gold questions (types below), FROZEN. `configs/evqa/bench-*.yaml` say "78 test questions" but `questions/test.jsonl` has 174: resolve. |
| `materials` | `data/seed/materials` | seed pipeline draft: blueprint + seed.ttl, no papers, no gold |
| `pf_{law,llm,materials,medicine}` | `data/seed|dataset/pf_*`; runs in `runs/paperfactory/qwen40-<field>/` | paperfactory v1 (links only, no numbers). 30/31/30/25 passed of 40. Gold only in `runs/paperfactory/qwen40-<field>/gold.json` (~72–83 each; types pair, subject_relation, conflict). Not in evqa format. |
| `v2_{law,llm,materials,medicine}` | `data/*/v2_*`; runs `runs/paperfactory/v2p3-<field>/` | paperfactory v2 pilot (links + numbers made by code, 2+ tables, style cards, topic clusters). 2/3/3/3 papers. Best quality so far. |
| 500 donor papers | `data/cache/donors/` (not in git) | real open-licence papers, 125 per field; for form only (outlines, table shapes, lengths), never shown to writers, never benchmark items. Unused so far. |

- Question types, evqa seed pipeline (`backend/evqa/seed/questions.py`, `bench.py`; `evqa seed bench <d>`):
  - In-corpus: lookup, effect, best, trend, list, conflict.
  - Not reported: absent, near_miss, out_of_scope.
- Ours: `evqa run --config configs/evqa/bench-qwen.yaml --text`.
- Baselines: paperqa2-rag, paperqa2-agent, paperqa2-agent-fixed, long-context, run through `configs/evqa/bench-{pqa-rag,pqa-agent,pqa-agent-fixed,long-context}.yaml`. Code is in the `baselines/` submodule. Also run the closed-book sanity config.
- Scoring:
  - `evqa eval <run> --text` gives L0–L3. L3-text is the score every system has.
  - `evqa compare <runs...> --out ...` gives per-type totals, 95% intervals and a paired bootstrap.
  - Every config today says `domain: medical`.
- Models: Qwen `orch-model` behind the LiteLLM gateway on a Slurm GPU job. Run with `srun --jobid <job> --overlap ops/injob.sh uv run ...`. Check `squeue -u $USER` first, because the job may have ended; start it per `llm-setup/README.md`. Claude Haiku is approved for small jobs.

## Known weaknesses to fix while improving

1. **Old link-only papers:** no numbers, one voice, and 25–37% fail the world check. Keep their worlds as input; add numbers and rewrite the papers with the improved generator.
2. **Style leak in the improved generator:** writers copy the brief's relation words. LAW thesis can contradict the world. Only a 3-paper pilot so far. Agreed scale-up: 4 topic clusters × 10 papers, generate about 60 per domain, keep all that pass.
3. **paperfactory gold:** not in evqa's question format, and covers only 3 types. It has no effect/best/trend/absent/near_miss/out_of_scope questions yet, even though the improved generator makes numbers that can support them.
4. **Two medicine worlds:** evqa `medical` and paperfactory `medicine` are two different invented worlds. Decided: join both into one medicine world and improve it. Phase 0 must propose how (shared entity names, clashing facts, how the existing 196 `medical` gold questions carry over).
5. **Possible "primary report" variant:** the paper's own study is a named world study flagged `self`. Estimated at 2–3 days. Only build it if Aditya says so.

## How to work

- **Phase 0, plan (stop after it):** inventory and propose for each domain:
  - which sources go in and what gets regenerated;
  - the 40-question type mix, roughly even across in-corpus and not-reported types, with at least 3 per type;
  - how paperfactory gold becomes evqa gold;
  - the run matrix, and a time and GPU estimate.
  Ask Aditya the open questions below, one decision at a time, each with a recommendation.
- **Phase 1, papers:** change paperfactory in `services/paper-factory`. Commit there first, then bump the submodule. Keep its tests green.
  - Run the improved generator per domain (about 60 papers, keep all that pass).
  - Export the passed papers with `paperfactory export-workbench --data-dir ../../data`.
  - Have Aditya spot-check 3 papers per domain in the Workbench (`http://127.0.0.1:25173/workbench`).
- **Phase 2, questions:** build a code bridge from the paperfactory world to evqa gold and questions, with all question types computed from world.json and numbers. Write the results to `data/seed/<d>/gold` and `data/dataset/<d>/questions/test.jsonl`.
  - Reuse `evqa seed bench` logic where you can.
  - The model may only reword a question, and a verifier checks the reworded version.
  - Show Aditya 10 questions per domain before freezing.
- **Phase 3, runs:** make configs per domain and system, then run ours, the 4 baselines and closed-book on all 4 domains. Runs are resumable; run them detached and log progress.
- **Phase 4, report:** run `evqa compare` per domain and overall, by question type, with cost per question. Write it up in `docs/design/` and log decisions in `docs/design/codex-log.md`.

## Rules

- Never print, log or commit `LITELLM_MASTER_KEY`, `OPENROUTER_API_KEY`, `OPENALEX_API_KEY` or anything from `llm-setup/.env`. `llm-setup/` is read-only.
- Gold answers and all numbers come from code. Prompt changes follow `docs/prompt-writing.md`; version prompts and keep the old ones.
- No preserving old pipelines for their own sake (synth2/synth3 are gone); choose the ideal design.
- Commit or push only when Aditya asks. Run all tests in both repos before any commit (`uv run pytest -q` in each). One test, `test_slots.py::test_cap_across_two_processes`, is flaky under load.
- Show results with real numbers. If something fails, say so plainly.

## Decisions already made by Aditya (do not ask again)

1. **Joining medicine:** decided, nothing wins. When the two worlds disagree, keep both as claims from different studies and record each clash in the truth files, so it feeds `conflict` questions (this is an evidence system; disagreement is wanted). Phase 0 must list the clashes found and say how each is recorded, and must tell real disagreements apart from accidents (same name for two different things).
2. **Materials:** decided, join the seed-pipeline draft in `data/seed/materials` into the materials world as input, same rule as medicine (clashes kept and recorded).
3. **Corpus size:** decided, keep every paper that passes the checks (from about 60 generated); sizes may differ by domain, so report paper counts next to every score.
4. **Question split:** decided, no practice split. All questions of a domain stay together in one test set.
5. **Primary-report variant:** decided, later (after the first full benchmark runs). Do not build it in this work.

All five questions above are decided. In Phase 0, only ask Aditya about new questions the plan raises.
