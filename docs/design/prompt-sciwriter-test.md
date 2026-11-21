# Prompt for a new Claude Code session: 5-paper quality test with claude-scientific-writer (21 Nov 2026)

Paste everything below the line into a fresh `claude` session started in the repo root.

---

You work in /mnt/ceph/storage/data-tmp/current/xepi3167/thesis/thesis-research-agent. Read first: AGENTS.md,
CLAUDE.md (reply rules for Aditya), docs/prompt-writing.md (for every prompt you write),
docs/design/qwen-writer.md, runs/scratch/qwen_quality/REPORT.md (the current numbers you compare against).

## Goal

A test, not a pipeline change: how good can our synthetic papers get? Make 5 papers whose STARTING MATERIAL is
as rich as PaperOrchestra's (its example: a 554-word idea + a 1,414-word experiment log with setup, splits,
baselines, settings, full tables), but produced by us from our RDF seed, with the writing guidance of
claude-scientific-writer (https://github.com/K-Dense-AI/claude-scientific-writer, MIT). Then measure them against
what we have now (Claude frozen papers, Qwen v2, Qwen v2r).

## Constraints

1. No Anthropic API key. claude-scientific-writer's CLI/API needs one, so do NOT run it. Clone it read-only to
   runs/scratch/sciwriter/vendor/ and reuse only its SKILL.md texts (scientific-writing, hypothesis-generation,
   scientific-critical-thinking, citation-management, peer-review if present) as instructions. The "LLM" is a fresh
   Claude subagent (Agent tool, new context each call, model haiku unless noted). Note in the report which skill
   files you used.
2. Literature: its research-lookup uses Parallel (paid) -> replace with Semantic Scholar through our helper
   backend/evqa/research/s2.py (`search`, `paper`; 1 request/s throttle and cache built in). The key is S2_API_KEY in
   .env: never print, log or copy it; subagents never see it (you run the searches and hand them the results).
   No personal data in any web request.
3. Do not commit. Never touch llm-setup/. Write only under runs/scratch/sciwriter/. Do not edit backend/,
   external/, data/, configs/ (another agent and Codex work there). Read-only use of their code is fine.
4. At most 3 subagents / LLM calls at once (Codex and Qwen jobs may run: check `pgrep -af "evqa run|paper_writing_cli"`
   and keep your total small).
5. Generation and verification are separate calls; code checks every LLM output.

## The 5 papers

P-med-01, P-med-10, P-med-11, P-med-17, P-med-18 (same as REPORT.md, so comparisons exist). Source of truth:
data/seed/medical/seed.ttl and data/seed/medical/papers/<id>/{idea_sparse.md, experimental_log.md} (planted rows
R-med-xx-yy with exact values). Existing outputs to compare: data/dataset/medical/papers/<id>/paper.md (Claude),
runs/scratch/qwen_quality/v2/ (Qwen v2), runs/scratch/qwen_quality/v2r/ (Qwen + S2 tool, 17/18 only).

## Steps per paper

A. Background facts (CODE, runs/scratch/sciwriter/facts.py): from the seed make the missing trial facts so they
   are consistent with the planted values: patients randomised per arm, completers/dropouts, age/sex/baseline of
   each measure, SD, 95% CI and P value for every planted mean difference (computed from the difference, SD and n;
   fixed random seed). Write facts.json (planted + background, each with an id). The planted values never change.
B. Rich materials (subagent 1, scientific-writing + hypothesis-generation skills as guidance): from facts.json and
   up to 4 Semantic Scholar results (you search; real trials of the same population/design) write idea.md
   (~500 words: problem, hypothesis, approach, contribution) and experimental_log.md (~1,400 words: setup, patients,
   arms, procedures, endpoints, statistics, all tables, observations), PaperOrchestra format. Rule: no number that
   is not in facts.json (years and citation years of the given S2 papers are allowed).
   Check (code): every number in both files is in facts.json or is an allowed year; every planted value appears
   exactly. One repair call with the failures, else mark failed.
C. Paper (subagent 2, scientific-writing + citation-management): write paper.md (Markdown, IMRaD, 2,500-3,500
   words, tables, cite only the given S2 papers as (Surname et al., YEAR), reference list at the end). Same number
   rule. Checks (code): reuse evqa.eval.dataset.check (L0: planted values found and in place) as measure.py does,
   unsupported numbers vs facts.json, citations all in the given list, no real drug names except in cited
   titles, no 8-word overlap with any S2 abstract.
D. Review (subagent 3, peer-review / critical-thinking skill, blind): score 1-5 on specific / reporting /
   not repetitive / journal-like, list the top 3 problems. Then ONE revise call (subagent 2 fresh) and re-check C.

Optional ceiling: repeat B-D for ONE paper (P-med-17) with model sonnet to show what a stronger writer reaches.

## Measure (same yardstick as REPORT.md)

Run runs/scratch/qwen_quality/measure.py's metrics on your 5 papers (import its functions; do not edit it) plus its
blind verifier tests: real-vs-generated (against data/style/medical excerpts) and head-to-head vs Claude frozen and
vs Qwen v2 on the same brief, both orders. Add: words per section, number of background facts used, citations.

## Report (runs/scratch/sciwriter/REPORT.md, plain words, Aditya reads it)

One table with REPORT.md's rows + new columns "sci-writer (haiku)" and, if done, "sci-writer (sonnet, 1 paper)".
Then: what the richer starting material changed, where the papers still read fake, invented numbers (should be 0),
cost (subagent tokens) and time per paper, and whether this flow (code facts -> LLM rich materials -> writer) is
worth moving into the pipeline (with Qwen as the writer). 5 papers = rough signal; say so.
