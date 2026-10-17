# State of the thesis (16 Oct 2026)

The one page to plan from: the design, what is ours, what was decided, the order of work, what exists and
what is open. File formats and the extractor interface: [`evidence-system.md`](evidence-system.md). The
system built before 14 Oct and its measured numbers: [`earlier-work.md`](earlier-work.md). Every test
result: [`../tests/RESULTS.md`](../tests/RESULTS.md).

## 1. The design (the supervisor's, 14 Oct)

Tim's two messages of 14 Oct set the thesis. What he wrote, by his section numbers (second message unless
noted):

- **Evidence-level, not answer-level** (first message, §1). Answer-level: find statements in the literature
  that already answer the question and aggregate them. Evidence-level: decide which evidence would answer the
  question, extract it from the papers, and synthesise the answer from it, even when no paper states the
  answer. Existing assessments in papers are one more kind of evidence. Questions are operationalised into
  explicit evidence requirements.
- **Executable research protocol** (§2) as the intermediate representation: which evidence, how it is
  extracted, how it is represented and connected, how it is synthesised (supporting and contradicting);
  YAML/JSON run by a Python engine. Generating the protocol with an LLM (with user dialogue) comes later.
- **A library of reusable, interchangeable extractors** (§3) behind a common interface (regular
  expressions, specialised models, LLMs or other methods), benchmarked; a small library is enough.
- **First use case** (§4): "Does retrieval-augmented generation improve the factual accuracy of
  LLM-generated answers?" Conditions, baseline, metrics, results; improves / no effect / worse;
  deterministic synthesis at first.
- **Synthetic corpus from structured ground truth** (§5): ground truth first, papers written from it;
  evaluate separately **A extraction** (precision/recall/F1, condition association, provenance accuracy),
  **B integration** and **C synthesis**, so extraction errors and synthesis errors are told apart.
- **Difficulty levels and variants** (§6): explicit, paraphrased, distributed, complex, contradictory;
  duplicates, missing information, limitations, unusually large effects; **controlled variants** (change one
  study and the answer should shift predictably); a fidelity check of the final documents.
- **Baseline** (§7): a conventional retrieve-then-answer system; compare correctness, completeness and
  traceability, including over-optimistic author conclusions; "should not assume the evidence-level approach
  will necessarily perform better".
- **Order** (§8): manual protocol, synthetic generator, extractors, representation, rules, separate
  evaluation, baseline. Optional: an LLM protocol generator, real papers.
- **Contribution** (§9): feasibility and a controlled evaluation on synthetic literature with known ground
  truth; diagnose why the system fails; a reusable benchmark; a vertical slice first.

He did not mention agents, for or against.

## 2. Our additions

Everything below is ours, not the supervisor's; the thesis must say so.

Built (14–15 Oct):

- **Agentic extractor**: the earlier research agent wrapped, unchanged, as one extractor behind the contract
  (`evidence/agentic/`, protocol `rag-factuality-agentic.yaml` puts it last in every cascade).
- **Agent baseline**: the research agent with the question only, no protocol (`evaluation/baselines/agent.py`).
- **Locate step**: before extraction the engine narrows each document to the parts the extractors see
  (`evidence/locate.py`, `locate.json`), and **locate recall** scores it.
- **Cascade**: several extractors per evidence type in order, items merged with `found_by`, each
  extractor's marginal contribution reported (B10).
- **Provenance and replay lane**: one hash-chained event per locate step, extractor call, merge and
  synthesis (B7); the **record cache** (B8); exact **replay** from records (a miss is an error, every output
  hash must match); **re-execution** as a stability measurement; **PROV-O** export.
- The details of the extractor contract (spans checked in the document, recorded coverage, extractor ids from
  code and config hashes; Part B) and the hard rule that no system under test reads the ground truth.

Built 17 Oct (decided 16 Oct, §4): the funnel engine (Part D), the proposal flow with the optional
vocabulary snapshot (Part E). Planned: none beyond the order of work (§5).

## 3. Research questions (implicit in the supervisor's text)

He wrote no numbered research questions. Read from his text:

1. **Feasibility** (§9): can a question be answered evidence-level through an executable protocol, an
   extractor library and deterministic synthesis?
2. **Extraction** (first message; §3, §5): how reliably and how completely can the relevant evidence be
   extracted from a scientific corpus, per extractor and per difficulty level?
3. **Evidence-level vs answer-level** (§7): how does the approach compare with retrieve-then-answer on
   correctness, completeness and traceability, and when is it better or worse?
4. **Where failures come from** (§9, §5): extraction, integration or synthesis.
5. Also: how the system responds to **controlled variants** (§6): does a changed study shift the answer as
   predicted?

## 4. Decisions of 16 Oct

| Topic | Decision |
|---|---|
| The earlier agent | A component only: the agentic extractor and the agent baseline. The claim on/off study (old RQ1) is dropped. The old parts (12 questions, concept pick, claim on/off batch, its scoring, gold review) stay in the repository, out of the main flow, documented as earlier work. |
| Web app | Rebuilt for the supervisor's flow: question → protocol → run → evidence graph → answer → scores A/B/C per level, the baseline beside it; agent traces as a drill-down. |
| Protocol | Hand-written now; an LLM protocol generator later (optional, as the supervisor says). |
| Evaluation | The synthetic benchmark is the main evaluation. A check on the RAG papers among the 337 real papers, with gold built by the `gold/` method (labelling repo) and reviewed by the user. |
| Models | The same model for all extractors and both baselines, so a comparison isolates the method. |
| Fixes for conflicts with the supervisor | (1) The RAG baseline becomes a plain retrieve-then-answer: top passages over the whole corpus, a neutral prompt (built 17 Oct, Part G.1; before: top 2 BM25 passages of every paper and a prompt with the label rules). (2) The fidelity check fails a paper that adds numbers or claims the ground truth does not have (built 17 Oct, Part G.2: `added_numbers`, `added_claims`, `blind_extra`). (3) README and this page keep his design and our additions apart. |
| Second build (ev2) | **Built 17 Oct** (Part F): the synthesis flags (duplicates, large effects, disagreeing claims) in `answer.json`; the generator's knobs `--duplicates/--missing/--outliers` (his §6) and `--irrelevant` (ours, for the screen); his controlled variant as `synth variant`; bootstrap intervals, flag scoring, `evaluate shift`, `evaluate benchmark`. The 15 Oct work in progress was restored from the bundle `../thesis-ev2-wip.bundle`, ported by hand onto protocol version 2, reviewed and merged. |
| Funnel engine (ours) | Per paper: screen (is there a RAG-vs-baseline experiment? else skip with a reason) → regex → completeness check against a rule the protocol declares (a RAG and a baseline condition, a shared metric, values for both on the same dataset) → escalate only the gaps (LLM, then the agent with a targeted task) → stop when complete or exhausted; gaps recorded. Modes `all` (every extractor on everything, for benchmarking) and `gaps` (answering, the 337-paper check). |
| Proposal flow (ours) | PICO-style frame → draft (EDC-style definitions; each field's source: ontology, protocol or invented) → critic checklist → fixed choice-point cards with LLM defaults, the user decides with a reason (`decisions:` log) → freeze with a hash and a pinned vocabulary snapshot → PROSPERO/OSF-style amendments (version, amended hash, reason, impact, before the main run or not). |
| Ontology | Optional offline vocabulary snapshot (CS-KG 2.0 terms and synonyms, Papers with Code metric names, ML-Schema measurement shape, EXPO roles; DBLP only for metadata), used **only in the proposal flow**. The evidence graph stays plain JSON with the PROV-O / Web Annotation export; no OWL. |
| Synthesis | The rules move from Python (`evidence/rules.py`, `evidence/synthesis.py`) into the protocol YAML; incomplete studies are reported with their reason. **Built 17 Oct** (protocol version 2, Part C): `synthesis` holds roles, metrics with direction, `min_effect`, pairing, claim map, label decision table and flag thresholds; `rules.py` knows nothing of the question; `synth` reads the same block (`--protocol`). |

## 5. Order of work

1. Contract: funnel engine, declarative synthesis, proposal flow (written before any code). **Done 17 Oct**: Parts C–G of `evidence-system.md`; the declarative synthesis is built (protocol version 2).
2. The conflict fixes (RAG baseline, fidelity check, attribution). **Done 17 Oct** (Part G).
3. Finish ev2. **Done 17 Oct** (Part F).
4. Funnel engine. **Done 17 Oct** (Part D).
5. Proposal flow. **Done 17 Oct** (Part E).
6. Codex runbook and the live Slurm run.
7. Web app rebuild.
8. The 337-paper check.
9. Documentation.

## 6. What exists

The evidence-level system, built 14–15 Oct on `main`: tested offline with scripted models only
(1220 passed, 1 skipped in WSL, 17 Oct, with the proposal flow and its review fixes), **not yet run against live models**. The runbook for the first live run is
[`slurm-evidence-runbook.md`](slurm-evidence-runbook.md) (not run; written before the 16 Oct decisions,
see §7).

| Step (supervisor's order) | State | Where |
|---|---|---|
| Protocol by hand | built, version 2 | `evidence/protocols/rag-factuality.yaml` (four evidence types: condition, metric, measurement, author claim; field schemas, value bounds, cascade per type, locate strategy, a screening question, every synthesis parameter), `evidence/protocol.py` |
| Synthetic corpus generator | built; knobs, variants and the stricter fidelity checks added 17 Oct | `synth/`: seeded ground truth from the protocol's synthesis block, five levels plus `mixed`, template and LLM renderers, fidelity checks with retries (including added numbers, added claims, blind extras), one corpus per level from one study set, the knobs of Part F2, `synth variant` (Part F3), a review sheet, six example corpora ([`synth/README.md`](../synth/README.md)) |
| Extractor library | built | `evidence/extractors/` (regex and single-call LLM per evidence type), `evidence/agentic/`; contract `evidence/contract.py` (Part B) |
| Provenance and replay (ours) | built | `evidence/engine.py`, `replay.py`, `prov.py` |
| Funnel engine (ours) | built 17 Oct (Part D) | `evidence run --strategy all\|gaps`: the protocol's `screen` cascade (`extractors/screen.py`: `regex_screen` on the terms, `llm_screen` on the first 12k characters) decides per paper; in `gaps` the cheap position of every type runs first, the completeness check is `synthesis.study()`, and only the gap's types escalate per round to the next position with a targeted `focus` on the task; `funnel.json`, `screen`/`completeness` events, `answer.json` `funnel` per study; `evaluate` reports calls per document, stop positions and screen precision/recall |
| Proposal flow (ours) | built 17 Oct (Part E); tested with scripted models only | `evidence propose frame/draft/critic/cards/freeze/amend` (`evidence/propose/`): question → `frame.json` (one model call; each entry's source looked up in the vocabulary: ontology or invented) → `draft.yaml` from the example protocol with `draft.sources.json` (ontology, protocol, invented) → `critic.json` (deterministic checks and an LLM checklist) → `cards.json` with the eight fixed choice points and `decisions.yaml` prefilled with the model's defaults (`by: model`), which the person edits (choice, reason, by; no reason is refused) → `protocol.yaml` (`revision: 1`) and `proposal.json` → `amend` (revision + 1, `amendments.jsonl` with the amended sha256, reason and changed keys). Every model call cached in the proposal directory; nothing runs a proposed protocol. The scripted RAG flow freezes to the hand-written protocol up to free text. `evidence vocab build` and a hand-written 15-term snapshot `evidence/vocab/rag-factuality.json` (not built from CS-KG/PwC downloads) |
| Evidence representation | built | `evidence/merge.py`, `graph.py`: merged items with every span and `found_by`; `graph.json` |
| Synthesis rules | built, in the protocol (17 Oct) | parameters in the protocol's `synthesis` block (Part C); machinery `evidence/rules.py`, `synthesis.py`: same-dataset pairing, table before prose; undetermined studies with a reason code |
| Evaluation A, B, C | built; intervals, flags, shift and benchmark records added 17 Oct | `evaluation/score.py`, `report.py`: extraction P/R/F1 per type and level with span accuracy, integration, synthesis (direction accuracy, completeness, traceability, expected-undetermined rule, flag precision/recall), locate recall, cascade contribution, cost, stability, 95 % BCa bootstrap intervals (`stats.py`); `evaluate shift` (`shift.py`), `evaluate benchmark` (`benchmark.py`, B11 records per extractor) |
| Baselines | built; the RAG baseline rebuilt 17 Oct as the plain retrieve-then-answer system (§4, Part G.1) | `evaluation/baselines/rag.py` (global top 8, neutral prompt with citations, the mapping call shared with the agent baseline in `common.py`), `agent.py`; score C adds completeness and traceability |
| Serving stack and cluster | works | measured 8–13 Oct ([`earlier-work.md`](earlier-work.md) §2) |
| Viewer | earlier design | `webapp/`, to be rebuilt |

Not built: the 337-paper check (§5 step 8, §7), the web app rebuild (§5 step 7).

## 7. Open

| Item | State |
|---|---|
| Agentic extractor | Open question for the supervisor (B14): is an agentic extractor acceptable as one implementation, with its runs replayed from records and its re-execution stability reported? |
| Model choice in the runbook | Done 17 Oct (Part G.3): `orch-model` is the default of every extractor and both baselines (`AgentSettings.model`, `evidence run --model`, `evaluate … --model`); `sub-model-1` writes the synthetic papers, `sub-model-2` is the blind check; the runbook's model table, rules and steps 1, 3–6 follow. |
| 337-paper check | Which of the 337 papers are RAG papers, and their gold (the `gold/` method; never run on the real model, [`earlier-work.md`](earlier-work.md) §6). |
| Structured outputs on the server | pydantic-ai's `response_format` calls (LLM extractors, gold, judge) cannot ask for `disable_any_whitespace` per request; proposed: `--structured-outputs-config '{"disable_any_whitespace": true}'` in the `llm-setup` profile (a submodule, not changed here); count `finish_reason` length on guided calls on Slurm either way. |
| Statistics | 95 % BCa bootstrap intervals (2,000 resamples, papers resampled; paired engine-minus-baseline difference) are built (Part F4); whether to report a test besides the intervals is open. |
| Runbook | `slurm-evidence-runbook.md` predates Parts F and G in its step list: the knob corpora, `synth variant`, `evaluate shift`/`benchmark` and the new baseline outputs are not in it yet (plan step 6); step 3 already runs `all` and `gaps`. |
| Funnel knobs | After an escalation adds context the funnel does not re-run the dependent type's cheap position with it; `llm_screen` reads the first 12k characters (`head_chars`). Both to be judged on the first live numbers (Part D as built). |

## 8. Documents

| Path | What |
|---|---|
| [`../README.md`](../README.md) | Entry point: packages, commands |
| `docs/STATE.md` | This page |
| [`evidence-system.md`](evidence-system.md) | Part A: packages and the files between them; Part B: the extractor contract |
| [`slurm-evidence-runbook.md`](slurm-evidence-runbook.md) | The first live run on Slurm (for Codex) |
| [`../synth/README.md`](../synth/README.md) | The synthetic benchmark generator |
| [`../tests/RESULTS.md`](../tests/RESULTS.md) | Every infrastructure and behaviour test, with the test notes as appendices |
| [`earlier-work.md`](earlier-work.md) | The system before 14 Oct: what it was, decisions and numbers, package essentials, where the removed documents live in git |
