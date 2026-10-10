# Milestones 1 and 2: triaged work list

Built from `docs/STATE.md` (10 Oct 2026). Milestone 3 (questions, gold D, Argilla) and 4 (72 runs, scoring)
are planned separately.

**Priorities**
- **P0:** the milestone is not done without it.
- **P1:** do it inside the milestone if time allows, or when a test result asks for it.
- **P2:** after milestone 4, or never.

**Size:** working days. **Cluster** means the item needs the Slurm stack running.

## Milestone 1: the agent answers one question end to end

**Done when:** one hand-written concept runs to a final answer, every claim's quote is found at its position in
the frozen corpus file, the log chain verifies, and the run directory is complete.

| # | Pri | Item | What exactly | Reuses | Depends on | Size | Cluster |
|---|---|---|---|---|---|---|---|
| 1.1 | P0 | F1 acceptance | Run `tests/F1/acceptance.py` once; it proves model → sandbox → broker → corpus as one path | `tests/F1/` | — | 0.5 | yes |
| 1.2 | P0 | Package and run directory | `agent/` Python package. `runs/<run-id>/` holds `config.json`, `concept.json`, `events.jsonl`, `claims.jsonl`, `out/` (full command outputs), `scratch/`, `answer.json` | — | — | 0.5 | no |
| 1.3 | P0 | Anchor library | Hash the **file**, not the quote. Return start and end positions. Match retyped quotes (whitespace, hyphenation, quote marks, ligatures) and map them back to raw offsets. Unit tests on 10 D1 papers, including two-column ones | `tests/D3/anchor.py` | — | 2 | no |
| 1.4 | P0 | Broker | One process per run, outside the sandbox. The single writer of both logs. Writes PROV-AGENT records (`docs/provenance-model.md`) with a hash chain. The harness gives it the step id. Checks each claim's anchor against `corpus/manifest.json` and replies "accepted" with a claim id, or "rejected" with the reason. Chain head printed to the Slurm log | `tests/H1/broker.py`, `tests/C1/verify_chain.py` | 1.3 | 2 | no |
| 1.5 | P0 | `claim` command | Executable in the sandbox. Reads JSON `{s, p, o, file, quote}` on stdin and sends it over `CLAIM_FD`. Prints the broker's reply, so the agent sees a rejection and can retry | `tests/H1/client.py` | 1.4 | 0.5 | no |
| 1.6 | P0 | Harness loop | Subclass mini-swe-agent 2.4.6. Calls `orch-model` (thinking off, `max_tokens` 4096). Parser: strict one-block rule, then the lenient fallback. Each command runs through `run_sandbox.py`. Output capped at 8 KB, with the full output saved to a file. Repeated commands get the B4 notices. Step and token budgets are announced to the agent. HTTP 400 context errors become "context full, conclude now". The run ends with a final answer step | mini-swe-agent, `tests/S5/run_sandbox.py`, `tests/S5/sandbox.py`, `tests/B/B4/loop.py` | 1.4, 1.5 | 4 | no (mock model) |
| 1.7 | P0 | Model-call records | Each call becomes an `ai_model_invocation` record: prompt hash, model name and revision, temperature, seed, token usage. Output that cannot be parsed becomes a `coverage` record; it is never run | — | 1.4, 1.6 | 1 | no |
| 1.8 | P0 | Answer format | The final answer is a list of facts. Each fact lists the claim ids it rests on (or none). Facts are needed for scoring in milestone 4; the claim ids are needed for "facts with no claim" | — | 1.6 | 1 | no |
| 1.9 | P0 | System prompt and one concept | Prompt v1: the tools, the `claim` rules, the budget, the answer format. One concept brief written by hand | `tests/B/system_prompt.txt` | 1.6, 1.8 | 1 | no |
| 1.10 | P0 | `agent verify` | For one run: verify the chain, resolve every anchor, check every answer fact's claim ids exist. Print steps, claims, tokens and time | `tests/C1/verify_chain.py` | 1.3, 1.4 | 1 | no |
| 1.11 | P0 | First real runs | C3: the concept from 1.9, 2–3 times. B5: are real quotes accepted, and what share is rejected? C8: does a run reach the 61k-token limit? | — | 1.1–1.10 | 2 | yes |
| 1.12 | P1 | Trace timeline | Static HTML from `events.jsonl`: steps in order, the command, the first lines of output, claims marked. For debugging, not the final viewer | — | 1.4 | 1.5 | no |
| 1.13 | P1 | Observation masking | Replace old outputs with a one-line stub. **Only if** C8 shows overflow. It costs a re-prefill of ~12 s at 30k tokens | — | 1.11 | 1 | no |

**Total P0:** about 16 days, 2.5 of them on the cluster.

**Critical path:** 1.3 → 1.4 → 1.5 → 1.6 → 1.8 → 1.11.

**Can run in parallel with the critical path:** 1.1, 1.2, 1.7, 1.12.

## Milestone 2: the full system and the baseline

**Done when:** one question goes question → concepts → user's pick → run, in both conditions. Each condition
produces an answer, a knowledge graph and a PROV-O file, and the five provenance queries return results on both.

| # | Pri | Item | What exactly | Depends on | Size | Cluster |
|---|---|---|---|---|---|---|
| 2.1 | P0 | Concept step | Question → 1 to 5 briefs, corpus-blind. Each brief has a title, a one-line definition with its measure, scope, answer shape, and 2–3 competency questions (`docs/plan.md` §5.2, without `subschema`). Validated JSON. The count is the model's call, capped at 5 | — | 2 | for testing |
| 2.2 | P0 | Pick a concept | CLI: show the briefs, the user picks one, `concept.json` is written. Logged as a record with the user as agent | 2.1, 1.4 | 0.5 | no |
| 2.3 | P0 | Baseline switch | `--claim off`: no `claim` command and no claim rules in the prompt. Same model, budget and answer format. Afterwards a separate step attaches sources (RARR style): for each answer fact, search the corpus, pick a quote, check it with the same anchor check. Output has the same format as ours, so scoring treats both the same. Attach-step tokens and time are counted separately | 1.8, 1.3 | 3 | for testing |
| 2.4 | P0 | Knowledge graph | Claims → triples. Paper ids come from the manifest. Predicates stay free text; a fixed list maps to CS-KG/DBLP names, and the rest go to `ours:`. Each edge points to its claim. Output `graph.json` | 1.11 | 2.5 | no |
| 2.5 | P0 | PROV-O export | `events.jsonl`, `claims.jsonl` and `graph.json` → `graph.ttl` with rdflib, using the edge table in `provenance-model.md` | 2.4 | 2 | no |
| 2.6 | P0 | Five provenance queries | The queries from `provenance-model.md`, as Python or SPARQL. Tested on one run of each condition | 2.5 | 1 | no |
| 2.7 | P0 | One full run per condition | Question → concepts → pick → our run, then the baseline run. Then `agent verify`, the graph, the export and the queries | 2.1–2.6 | 1.5 | yes |
| 2.8 | P1 | Claim walk view | Click an answer fact → its claim → the step → the quote, highlighted in the paper (LEDGER's walk). Builds on 1.12 | 2.6 | 2.5 | no |
| 2.9 | P1 | `spawn` subagents | Subagents run on `sub-model-1`/`-2`, with their own claim stream tagged `source_agent_id`. **Only if** M1 runs overflow, or need more than ~60 steps per question | 1.11 | 3 | yes |
| 2.10 | P2 | Concept cards UI | Side-by-side cards instead of the CLI | 2.1 | 2 | no |
| 2.11 | P2 | Full canonicalisation | EDC Define/Canonicalise against CS-KG | 2.4 | 3+ | yes |

**Total P0:** about 12.5 days, 2–3 of them on the cluster.

**Can start before milestone 1 is done:** 2.1 and 2.3 (the attach step is separate).

## Not doing (cut, or later than milestone 4)

- **`save_tool`** and tool reuse across runs (C7).
- **Langfuse copy and Omen tunnels** (T2, T3).
- **Thinking at low effort:** only if the B6 rating favours it.
- **Concept researchability check.**
- **Compaction summaries.**
- **Subagents calling subagents.**

## Risks this order is meant to expose early

| Risk | Shows up in | Fallback |
|---|---|---|
| The model retypes quotes and most claims are rejected | 1.3 unit tests, 1.11 (B5) | Looser matching, plus a prompt rule to copy quotes with `rg -o` |
| One agent cannot cover a corpus-wide question in 61k tokens | 1.11 (C8) | 1.13 masking first, then 2.9 `spawn` |
| The baseline is unfair (more budget, or a different answer format) | 2.3 | One config shared by both conditions. The attach step's cost is reported separately |
| Answer facts are too vague to score | 1.8, 2.7 | Tighten the answer format before milestone 3 fixes the key |
