# Milestones 1 and 2: triaged work list

Built from `docs/STATE.md` (10 Oct 2026) and revised after a review the same day. Milestone 3 (gold D,
Argilla, answer key) and milestone 4 (72 runs, scoring) were built in the e2e build (`docs/milestones-3-4.md`); what they need from 1 and 2 is
listed at the end.

**Priorities**
- **P0:** the milestone is not done without it.
- **P1:** do it inside the milestone if time allows, or when a test result asks for it.
- **P2:** after milestone 4, or never.

**Size:** working days. **Cluster** means the item needs the Slurm stack running.

## Fixed run settings (recorded in every run's `config.json`)

| Setting | Value | Source |
|---|---|---|
| Models | `orch-model` = Qwen3.8-27B-FP8 @ `017b9c7`, thinking off, `max_tokens` 4096; `sub-model-1`/`-2` = Qwen3-30B-A3B-Instruct-2507-FP8 @ `5a5a776` | STATE Decided |
| Budget | 150 steps / 400k tokens to start, announced to the agent; adjusted once after 1.13, then frozen for both conditions | decisions §6 |
| Sampling | Temperature and one seed per run, written to the config. L7 showed the seed reaches vLLM through the proxy | L7 |
| Command limits | `timeout 120`, `ulimit -v 2G`, output capped at 8 KB in context | STATE Sandbox, Output cap |
| Also recorded | Prompt version and hash, the concept file's hash, the `corpus/manifest.json` hash, the agent-root manifest hash, the git commit, the condition (`claim` on or off) | — |

## Milestone 1: the agent answers one question end to end

**Done when:** one frozen concept runs to a structured final answer, every claim's quote is found at its
position in the frozen corpus file, the log chain verifies, and the run directory with its `config.json` is
complete.

| # | Pri | Item | What exactly | Starts from (gap) | Depends on | Size | Cluster |
|---|---|---|---|---|---|---|---|
| 1.1 | P0 | F1 acceptance | Run `tests/F1/acceptance.py` once; it proves model → sandbox → broker → corpus as one path | `tests/F1/` | — | 0.5 | yes |
| 1.2 | P0 | Package and run directory | An `agent/` package. Each run gets `runs/<run-id>/` with `config.json` (settings above), `concept.json`, `events.jsonl`, `claims.jsonl`, `out/` (full command outputs), `scratch/` and `answer.json`. One canonical-JSON function (sorted keys, `ensure_ascii=False`) shared by every writer and checker | — | — | 0.5 | no |
| 1.3 | P0 | Concept and answer schema | Concept brief: title, definition with its measure, scope, answer shape, 2–3 competency questions (`docs/plan.md` §5.2, without `subschema`). Answer: rows that fit the concept's answer shape. Each row's facts are s/p/o triples, and each fact lists its claim ids (or none). This is what the milestone 3 answer key is built to match, so it is frozen here | `docs/plan.md` §5.2 | — | 1.5 | no |
| 1.4 | P0 | Column-order check (D1) | Look at 3 two-column papers in the frozen corpus. If the text is interleaved, note which papers before the anchor tests are written | D1 | — | 0.5 | no |
| 1.5 | P0 | Anchor library | Hash the **file**, not the quote. Return start and end positions. Match retyped quotes (whitespace, hyphenation, quote marks, ligatures, non-ASCII) and map them back to raw offsets. Unit tests on 10 corpus papers | `tests/D3/anchor.py` (hashes the quote, returns the quote, exact match only) | 1.4 | 2 | no |
| 1.6 | P0 | Broker (rewrite) | One process per run, outside the sandbox. The single writer of `events.jsonl` and `claims.jsonl`. Writes PROV-AGENT records (`docs/provenance-model.md`) with one hash chain. Two inputs: the main loop's channel (model calls, commands, step ids) and a new `CLAIM_FD` socketpair for each command, tagged with its step id. Checks each claim's anchor against `corpus/manifest.json` and replies "accepted" with a claim id, or "rejected" with the reason. Chain head printed to the Slurm log | `tests/H1/broker.py` (starts once per command, truncates its log, acks every claim, `ensure_ascii=True`, claims only) | 1.2, 1.5 | 3 | no |
| 1.7 | P0 | `claim` command | Executable in the sandbox. Reads JSON `{s, p, o, file, quote}` on stdin and sends it over `CLAIM_FD`. Prints the broker's reply, so the agent sees a rejection and can retry | `tests/H1/client.py` | 1.6 | 0.5 | no |
| 1.8 | P0 | Main loop | Subclass mini-swe-agent 2.4.6 (pin it in a lock file). Calls `orch-model` with the settings above. Parser: strict one-block rule, then the lenient fallback. Runs each command through the sandbox with the command limits above (set them in the wrapper). Adds an 8 KB cap with a link to the full output, warnings on repeated commands (the B4 rule, new code), announced budgets, and "context full, conclude now" on HTTP 400. Ends with a final answer step in the 1.3 format. Built first against a stub broker | mini-swe-agent; `tests/S5/run_sandbox.py` (180 s timeout, no `ulimit`); `tests/S5/sandbox.py`; `tests/B/B4/loop.py` (measures repeats only) | 1.2, 1.3 | 4 | no (mock model) |
| 1.9 | P0 | Model-call and command records | Each model call becomes an `ai_model_invocation` record (prompt hash, model and revision, temperature, seed, token usage). Each command becomes an `agent_tool` record. Output that cannot be parsed becomes a `coverage` record and is never run. A step spent on `claim` is marked, so cost can be compared with and without it | — | 1.6, 1.8 | 1 | no |
| 1.10 | P0 | Prompt v1 and one concept | Start from `tests/B/system_prompt.txt`. Remove `spawn`, `save_tool` and the `/corpus` and `/work` paths; use `$CORPUS` and scratch. Add the `claim` rules, the budget and the answer format. The baseline prompt (2.3) is this prompt minus the `claim` part, kept as a diff. One concept brief written by hand | `tests/B/system_prompt.txt` | 1.3, 1.8 | 1 | no |
| 1.11 | P0 | `agent verify` | For one run: verify the chain, resolve every anchor, check that every answer fact's claim ids exist. Print steps, claims, claim steps, tokens and time | `tests/C1/verify_chain.py` | 1.5, 1.6 | 1 | no |
| 1.12 | P0 | Fact–quote export | `pairs.jsonl` per run: each answer fact with its claim's quote and file. This is the input for the quote-supports-fact judge in milestone 3/4 | — | 1.3, 1.11 | 0.5 | no |
| 1.13 | P0 | First real runs | C3: the concept from 1.10, 2–3 times. B5: are real quotes accepted, and what share is rejected? C8: does a run reach the 61,440-token limit? Fix the budget after this | 1.1–1.12 | — | 2 | yes |
| 1.14 | P1 | Trace timeline | Static HTML from `events.jsonl`: steps in order, the command, the first lines of output, claims marked. For debugging, not the final viewer | — | 1.6 | 1.5 | no |
| 1.15 | P1 | Observation masking | Replace old outputs with a one-line stub. **Only if** C8 shows overflow. It costs a re-prefill of ~12 s at 30k tokens | — | 1.13 | 1 | no |

**Total P0:** about 18 days, 2.5 of them on the cluster.

**Critical path:** 1.4 → 1.5 → 1.6 → 1.9 → 1.13, about 9 days. The 1.6 broker comes from 1.5 because it
checks anchors.

**Runs alongside the critical path:** the main loop 1.8 is built against a stub broker, and with 1.10 (about
5 days in all) it must be ready by 1.13. Also in parallel: 1.1, 1.2, 1.3, then 1.14.

### Progress (branch `m1-core`, merged into `main`)

| # | Status | Commits | Tests |
|---|---|---|---|
| 1.2 | done | `6eba4ad` | `test_rundir` (6) |
| 1.3 | done | `1d23fd1` | `test_concept` (35) |
| 1.4 | done: 0/10 papers interleaved, nothing excluded | `cb54b53` | D1-col |
| 1.5 | done; minus signs and number cuts fixed after review | `dd73ebb`, `5c91f85` | `test_anchor` (82) |
| 1.6 | done | `cc22632` | `test_broker` (30; 2 POSIX-only, skipped on Windows) |
| 1.8 | done against a scripted model; mini-swe-agent 2.4.6 pinned | `d08c70c` | `test_loop` |
| 1.9 | done (records, `files_read`, claim steps, `final_answer` marker) | `6bde1bd` | `test_loop` |
| 1.10 | done: `agent/prompts/system-v1.txt`, baseline = v1 minus the claim block (`system-v1.diff`, tested), concept `agent/concepts/rag-eval-datasets.json` | `06d790d` | `test_prompts` |
| 1.11, 1.12 | done: `agent verify`, `agent pairs` | `bda4412` | `test_loop` |
| 1.14 | done: `agent timeline` → `timeline.html` | `b7c98aa` | — |
| 1.1 | passed on Slurm 7288 (RESULTS `F1`) | — | — |
| 1.13 | first real runs done (RESULTS `M1-real`: verified, no answers, 400k spent in ~26 steps, conclude replies were commands); fix built against a scripted model on `e2e/agent-fix`: prompt v2 (real file names, claim where found, `answer-draft.json`), conclude replies decoded under the reply schema (`structured_outputs`; a refused schema falls back to free decoding; up to 16,384 reply tokens within the context), draft answer taken when a run ends without one (copy kept as `answer.draft.json`), notices at 50/75/90 %, six identical commands end research, provisional budget 60 steps / 2M tokens; the attach step the same way (attach prompt v2, result decoded under its schema, a matching claim taken when no result comes); rerun on Slurm and freeze the budget | `fa77e4a`, `1e09eee`, `952c5be`, `991f1d4`; after review `a8ab206`, `d50d84a`, `d84e2fe`, `1c4b60f` | `test_loop_v2`, `test_prompts`, `test_attach` |
| 1.15 | done against a scripted model, before C8 overflowed (2M-token runs would): outputs older than the last 8 commands become stubs naming `out/step-NNNN.txt` (last 4 after a prompt over 45k tokens), claim replies kept; masked count in each model call record; `trajectory.json` keeps each masked output's text, so every prompt hash can be rebuilt | `1e09eee`, `d50d84a` | `test_loop_v2` |

Unit suite: 151 passed + 2 skipped on Windows, 153 passed on WSL Linux (2026-10-10, RESULTS `M1-unit`).
After `m1-loop` and `m2-graph`: 232 passed + 1 skipped on WSL Linux (2026-10-11, RESULTS `M1-loop`).
`.gitattributes` (`07af190`) keeps every hashed file LF, so the manifest hash matches the Ceph copy.

Small decisions made while building:
- Claim ids are `claim-NNNNNN`, numbered per run by the broker; a claim's id fields sent by the sandbox are ignored and logged.
- Claims are records in `events.jsonl`'s single hash chain; `claims.jsonl` is a copy of those records that `verify-chain` checks against it.
- A claim's `file` may be `p12.md`, `p12` or an absolute path inside the corpus directory; anything else is `file_outside_corpus` or `unknown_file`.
- Each answer fact has `origin` `research` (claimed during the run) or `attach` (baseline attach step, 2.5).
- Answer cells (row values) may be `null`: the agent could not establish the value; `measure.operation` in the concept is a free word (count, list, rank, …), not an enum.
- Anchor matching: case-sensitive; dashes and whitespace dropped, except a minus sign (a dash touching a digit, or between digits) is kept as U+2212 and whitespace between digits stays one space; a match that cuts a number or leaves out its sign is refused (`partial_number`).
- Open for B5 (1.13): whether to relax case sensitivity, and whether to require a minimum quote length (today a quote of one word is accepted if it is unique in the file).

## Milestone 2: the full system and the baseline

**Done when:** the 12 questions have frozen concepts, and one question runs in both conditions. Each condition
produces an answer, a knowledge graph and a PROV-O file, and the five provenance queries run on both. In the
baseline, queries 1–3 end at the attach step, not at the research step where the fact was found. That
difference is what RQ1 measures, and it is expected.

| # | Pri | Item | What exactly | Depends on | Size | Cluster |
|---|---|---|---|---|---|---|
| 2.1 | P0 | Concept step | Question → 1 to 5 briefs in the 1.3 schema, corpus-blind, validated. The count is the model's call, capped at 5 | 1.3 | 2 | for testing |
| 2.2 | P0 | Pick a concept | CLI: show the briefs, the user picks one, `concept.json` is written. Logged as a record with the user as agent | 2.1, 1.6 | 0.5 | no |
| 2.3 | P0 | Concepts for all 12 questions | Run 2.1 and 2.2 on the 12 questions and freeze the 12 `concept.json` files with their hashes. Every run of both conditions uses the frozen file. **Gates milestone 3:** gold D is built for the picked concept | 2.2, questions written (M3) | 1 | yes |
| 2.4 | P0 | Baseline switch | `--claim off`: no `claim` command, prompt from the 1.10 diff, same model, budget, seed scheme and answer format | 1.8, 1.10 | 1 | no |
| 2.5 | P0 | Attach step | Runs after the baseline answer. Fixed setup:<br>• model `orch-model`, the same sandbox and tools (`rg`, reading files)<br>• its own declared budget per fact, written to `config.json` with its prompt hash<br>• for each answer fact, either one quote or **"no source found"**<br>Each attached quote passes the same anchor check and is written as a `claim` record with `custom_metadata.origin = "attach"`, linked to an attach-step activity in the same chain. Its cost is logged on its own, and the total is reported both with and without it | 2.4, 1.6 | 2.5 | for testing |
| 2.6 | P0 | Knowledge graph | Claims (both origins) → triples. Paper ids come from the manifest. Predicates stay free text; a fixed list maps to CS-KG/DBLP names, and the rest go to `ours:`. Each edge points to its claim. Output `graph.json` | 1.13 | 2.5 | no |
| 2.7 | P0 | PROV-O export | `events.jsonl`, `claims.jsonl` and `graph.json` → `graph.ttl` with rdflib, using the edge table in `provenance-model.md`. Attach claims are derived from the attach activity | 2.6 | 2 | no |
| 2.8 | P0 | Five provenance queries | The queries from `provenance-model.md`, as Python or SPARQL, tested on one run of each condition | 2.7 | 1 | no |
| 2.9 | P0 | Batch runner | Reads a run manifest (question × condition × repeat, seed). Starts each run inside the job time limit, skips finished runs, and marks a run cut by the job limit with a `coverage` record so it is rerun. Needed for 72 runs of 30–45 min each, more than one 48-hour job | 1.8, 2.4 | 1.5 | for testing |
| 2.10 | P0 | One full run per condition | One question, our run then the baseline run plus its attach step, both through the batch runner. Then `agent verify`, the graph, the export and the queries | 2.3–2.9 | 1.5 | yes |
| 2.11 | P1 | Claim walk view | Click an answer fact → its claim → the step → the quote, highlighted in the paper (LEDGER's walk). Builds on 1.14 | 2.8 | 2.5 | no |
| 2.12 | P1 | `spawn` subagents | Subagents run on `sub-model-1`/`-2`, with their own claim stream tagged `source_agent_id`. **Only if** M1 runs overflow, or need more than about 60 steps per question | 1.13 | 3 | yes |
| 2.13 | P1 | Re-execution and replay (C5, C6) | Re-execution reruns a run's commands on the frozen corpus and compares outputs; replay re-renders a run from its log. Needed if the trace-verifiability measures in RQ1 report them | 1.11 | 2 | yes |
| 2.14 | P2 | Concept cards UI | Side-by-side cards instead of the CLI | 2.1 | 2 | no |
| 2.15 | P2 | Full canonicalisation | EDC Define/Canonicalise against CS-KG | 2.6 | 3+ | yes |

**Total P0:** about 15.5 days, 3–4 of them on the cluster.

**Can start before milestone 1 is done:** 2.1 and 2.5 (the attach step needs only the anchor check and the
model). 2.3 waits only for the 12 questions.

### Progress (milestone 2; all branches of the e2e build merged on `e2e-build`, 14 Oct)

| # | Status | Commits | Tests |
|---|---|---|---|
| 2.6 | done: `agent graph` → `graph.json`; predicate table `kg.PREDICATES` (CS-KG `uses`/`solves` seen only as inverses, to confirm) | `811cbe8` | `test_kg` (9) |
| 2.7 | done: `agent export-prov` → `graph.ttl`, rdflib 7.6.0, deterministic | `e34e6ca` | `test_prov` (8) |
| 2.8 | done: `agent query 1–5`; tested on a research-style and an attach-style run built through the real broker | `1ea345b` | `test_queries` (7) |
| 2.1, 2.2 | done: `agent concepts propose\|pick\|check`, prompt `concept-v1.txt`, corpus-blind, capped at 5, one repair round; pick is a `concept_pick` record by agent `user` | `18d5202` | `test_concept_step` |
| 2.4 | done: the loop already had `claim_off`; tests pin no `claim`/`CLAIM_FD`, same config except condition and prompt | `259a4de` | `test_loop` |
| 2.5 | done: `agent attach <run>`; per fact a fresh conversation using `claim` with `origin="attach"`, or `no_source`; 6 steps / 60k tokens per fact to start; appends to the run's chain; `answer.research.json` kept | `bb6b631` | `test_attach` |
| 2.9 | done: `agent batch <manifest>`; `agent/manifests/m4-72.json` on the 12 questions (2.3), provisional budget and prompt v2 (1.13), spawn off; cut runs rerun fresh as `<key>-a<N>` (max 3); exit 0 done / 2 out of time / 1 gave up | `8f17bd7`, `051f64b` | `test_batch` |
| 2.12 | built against scripted models on `e2e/spawn`, off by default (`agent run --spawn on`, manifest `spawn`; `m4-72.json` keeps it off): `spawn --task ... [--files a.md,b.md] [--steps N]` in the sandbox over a SPAWN_FD channel; at most 2 subagents at once (one per sub-model replica), the rest queued; a subagent is the research loop on the sub model (32,768 context, 15 steps / 300k tokens, `sub-v1.txt`, no nested spawn, claim iff claim_on; budget settable with `--spawn-steps/--spawn-tokens`, manifest `spawn_budget`) whose records and claims carry `agent_id` sub-NN and `spawned_by_step`; a command that starts a subagent gets 1,800 s; `agent verify` reports the run's total and each agent's cost. Review fixes: masking treats spawn results alike in both conditions, `ok` means a subagent ran, a subagent's failure is `subagent_error` (never fails the run), `spawn` in its own PATH directory, time limit from the spawn channel, one stop deadline inside the batch grace. Not yet run on the real model (C4) | `7e698cb`, `d50cd55`, `0c2c63f`, `fab16c7`, review fixes | `test_spawn` (25) |
| 2.3 | built: the 12 questions in `questions/questions.json` (6 corpus-wide, 6 ambiguous, from the labelling repo; `questions/README.md`); `agent concepts propose-all\|pick-all\|status`, `pick --picked-by --reason --replace`, `$CONCEPTS/picks.json`; manifests `m4-72` and `e2e-smoke` on them. Open: proposing and picking the 12 on Slurm (`scripts/e2e-concepts.sh`) | `da7b45f`, `a1be5cd`, `59e981d`, `045424c` | `test_questions`, `test_concept_step` |
| 2.10 | open: needs the cluster (`scripts/e2e-batch.sh agent/manifests/e2e-smoke.json`) | — | — |
| 2.13 | done: `agent reexec <run> [--steps]` (C5; a subagent's commands in a scratch of their own, since the merge with 2.12) and `agent replay <run>` (C6); first real use on Slurm (`scripts/e2e-replay.sh --reexec`) | `0085b29`, `f389ea6`, `46d911b`, `91dccf3` | `test_reexec`, `test_replay` |
| Slurm scripts | `scripts/e2e-env.sh`, `e2e-concepts.sh`, `e2e-batch.sh`, `e2e-replay.sh` | `aebdadc`, `6b7c5f6` | `test_e2e_scripts` |
| 2.11 | done in the web app (`webapp/web`, run page): an answer fact's badge, a graph edge or a claim opens the claim walk: fact, claim(s), the step (model call numbers, command, output head) and the passage with the quote highlighted (`GET /api/runs/{id}/facts/{fact}/walk`, the verdict scoring counted) | e2e build (WP E, F) | `webapp/tests/test_api.py`, `ClaimWalkSheet.test.tsx` |
| 2.14 | done in the web app (question page): concept briefs as cards side by side with the answer shape, pick (who and why) and propose | e2e build (WP E, F) | `webapp/tests/test_pick.py`, Vitest |

Small decisions made while building:
- Attach-step records are ordinary records with `custom_metadata.origin = "attach"` (loop records carry `research`); the export groups them into one attach activity. Attach claims are `wasGeneratedBy` their attach command and `wasInfluencedBy` the attach activity.
- A claim's step is the `agent_tool` record with the same agent and step id that follows it in the chain; the `checked_by` activity is the claim record itself (`ours:ClaimCheck`); rejected claims stay check activities with a reason.
- One KG edge per accepted claim (`edge-NNNNNN` = claim number). Manifest ids become paper nodes, other strings `entity:<slug>`.
- IRIs: run-scoped `urn:thesis-agent:run:<run_id>/…`, shared `urn:thesis-agent:{corpus,paper,entity}/…`.
- Concept sessions live in `concepts/<qid>/` (`session.json`, `events.jsonl`, `proposal.json`, `concept.json`, `concept.sha256`).
- The attach step's claim must carry the fact's own s/p/o; its budget (6 steps / 60k per fact) is frozen with the run budget after 1.13.
- Seeds: `seed_base + 100 × question + repeat`, the same in both conditions. Deadline = earliest of `--deadline`, `--time-limit`, `$SLURM_JOB_END_TIME`; use `#SBATCH --signal=B:TERM@<s>`.
- Fixed while building: command cleanup now signals the wrapper's whole session (background children escaped before; `setsid` still escapes); SIGTERM is no longer retried as a model error (`agent/stopping.py`).
- Subagents (2.12): one hash chain for the run, not a nested run directory per subagent (plan §5.3): records and claims of a subagent carry `agent_id` sub-NN, `source_agent_id` main and `custom_metadata.spawned_by_step`; the parent's `spawn` records mark the start (task, files, steps, sub-model, seed = run seed + N) and the return (exit status, sha256 of `sub/<id>/result.json`), or a refusal (`unknown_file`, `spawn_limit`, `bad_request`, ...). Step ids come from one counter per run, so a step id stays unique (and `out/step-NNNN.txt` with it) while subagents run. A subagent's result is `{summary}` plus the claims the broker logged for it (id, s, p, o, file), so the parent can cite them. Each request carries its own reply pipe over a SEQPACKET channel (the sandbox may not create sockets), which is how several spawns share one command. A subagent gets its own scratch outside the parent's (its commands record it as `custom_metadata.workdir`, `sub/<id>/scratch`, for re-execution); at most 20 per run (their tokens are outside the parent's budget). Subagents still running when their command ends are cancelled (their running command killed). `spawn` lives in `agent/spawn-bin/` (claim stays in `agent/bin/`): the PATH has `agent/bin` iff claim_on and `agent/spawn-bin` iff spawn is on, so with spawn off the conditions differ only in claim, and subagents (no nested spawn) never have it.
- Subagents, after review: when old outputs are masked, a spawn result line becomes `{agent_id, status}` plus (claim_on) its claim ids, in both conditions, so the summary never stays in claim_on's context only. `ok` is true for every subagent that started, whatever its status (its claims are accepted either way); `{ok: false, reason}` only when none started. A subagent's exception is a `subagent_error` coverage record, never the run's `run_error` (which the batch runner, scoring and the web app read as a failed run). A command gets the 1,800 s limit when its spawn channel accepts a request (the wrapper gets 1,800 s, the harness cuts the command at 120 s otherwise), so spawn from a script works and a mere `rg spawn` keeps 120 s. On SIGTERM the harness waits for subagents at most 15 s in all (`spawn.STOP_WAIT_S`, inside `batch.GRACE_S`); a subagent left in a model call then has no return record, which verify reports. A subagent's accepted summary is marked `custom_metadata.result`; `final_answer` stays the main agent's. verify's `agents` is the research's cost per agent (attach apart) over every subagent that started; PROV links a subagent only to its start record.
- 2.3: a pick records who picked (`picked_by`: user, claude, provisional-first, also the record's agent) and why; a pick is frozen unless replaced on purpose (`--replace`), and the new pick names the concept it replaces. A replace is refused once `$GOLD/<qid>/` holds anything (the web app's rule); `--force` goes past it and records the gold files. `picks.json` is rebuilt from the sessions' chains after every pick. A session whose question text has changed is `stale` and is never reused.
- 2.3 retries: a session without a proposal is continued by the next `propose`, as long as the question, model, prompt and limits are the same; sampling, commit and proxy are per attempt (`session.json` `attempts`), so a failed question can be retried after a fix commit and with another seed (a seeded model repeats its invalid briefs).
- 2.3 locks: `propose`, `pick` and the `picks.json` rebuild are also the web app's (thread pool), so they hold a filelock on the session (on the concepts root for `picks.json`); two writers on a session would fork its chain.
- 2.13 re-execution: every `agent_tool` record in chain order, one fresh scratch for the sequence, the run's sandbox mode, agent root, limits and claim setting (attach commands always claim); claims go to a dry broker that numbers claim ids on from the run's count, so a claiming command reprints its output byte for byte; nothing is appended to the run's chain. A claim verdict, id or reason other than the run's, or a claim not sent again, is a difference even when the output does not show it. Every manifest paper is hashed and extra Markdown files are reported (corpus-wide commands read them all). The agent root hash and commit are recorded for the run and now. Exit 0 identical, 1 differing outputs or claims, 2 errors.
- 2.13 replay: a call's prompt is the first `used.messages` messages of trajectory.json, hashed as `OrchestratorModel.query` hashes them. Messages the loop changed after a call (masking 1.15, context-full stubs, shortened replies) are rebuilt from what WP A's loop keeps: `extra.original_content`, the call record's `masked_observations` (stubs are the oldest outputs and never change back) and the second context-full 400 (replies shortened after it). Scope is the research loop: a claim_off run's attach calls are counted as unchecked, and the result is PARTIAL rather than PASS.
- Slurm: `scripts/e2e-batch.sh` writes runs to `$RUNS/<manifest name>/` through an effective manifest (runs_root, concepts from `$CONCEPTS`, `base_url` from `$LITELLM_BASE_URL`) and refuses a root whose manifest or concepts changed since its runs started. That directory is the manifest's runs root for scoring and the web app (its last line, `RUNS_ROOT=...`), so the M4 report never mixes in smoke runs.

## What milestones 3 and 4 get from 1 and 2

| Milestone 3/4 needs | Comes from |
|---|---|
| The picked concept per question, to build gold D on | 2.3 |
| A fixed answer format to build the key against | 1.3 |
| Answer facts with claim ids, in both conditions | 1.3, 2.5 |
| Fact–quote pairs for the quote-supports-fact judge. The judge itself and its check on 200–300 claims are milestone 3/4 work | 1.12 |
| Cost per run: tokens and time, claim steps, attach step | 1.9, 2.5 |
| 72 runs that restart cleanly across jobs | 2.9 |

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
| The model retypes quotes and most claims are rejected | 1.5 unit tests, 1.13 (B5) | Looser matching, plus a prompt rule to copy quotes with `rg -o` |
| One agent cannot cover a corpus-wide question in 61k tokens | 1.13 (C8) | 1.15 masking first, then 2.12 `spawn` |
| The baseline is unfair: more budget, a different answer format, or forced sources | 2.4, 2.5 | One config shared by both conditions. The attach step may answer "no source found". Cost is reported with and without it |
| Answer facts are too vague to score | 1.3, 2.10 | Tighten the schema before milestone 3 fixes the key |
| 72 runs do not fit in the job time limit | 2.9 | Resume across jobs; the cut runs are marked and rerun |
| Two-column papers have interleaved text, so quotes span columns | 1.4 | Exclude or flag the affected papers in the manifest |
