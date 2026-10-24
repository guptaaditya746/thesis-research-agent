# Question-first redesign, build steps 2–5: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The system answers 10 research questions of four kinds (effect, inventory, consistency, best) on the synthetic RAG corpora, scores every system on A/B/C per kind, shows a live run trace, offers per-kind cards drafted by the agent with a checker, and finds evidence with three new extractors.

**Architecture:** A protocol gains a `kind`; each kind is one small rules module (`evidence/kinds/`) that turns merged items into a per-document entry, a gap code and an answer. The same kind modules compute the expected answer from `ground_truth.json`, so engine and truth share rules exactly as `evidence/rules.py` does today. The trace reads `events.jsonl` plus a new run-local `calls.jsonl`; the proposal flow picks its template protocol and card set by kind.

**Tech Stack:** Python 3.13, pydantic, FastAPI, pytest; React + TanStack Query + vitest (node via `uv run --group frontend`); GLiNER served from llm-setup over HTTP.

**Spec:** The agreed decisions below (grill of 23–25 Oct 2026; also in `GLOSSARY.md`). There is no separate spec file; this section is the authority.

## Agreed decisions (the spec)

1. Ten questions, hand-written protocols (Tim §8: manual protocol first):
   - **effect:** accuracy (the existing `rag-factuality`, unchanged), hallucination, latency;
   - **inventory:** metrics, methods (conditions), datasets;
   - **consistency (direction):** accuracy, hallucination;
   - **best:** accuracy, hallucination.
2. True answers come from the existing `ground_truth.json` files. No corpus is rebuilt. The truth parameters (metric, `min_effect`, target) are fixed in `evidence/questions.yaml`, never taken from a user's protocol.
3. `dataset` becomes an evidence type. A dataset item is right when its name matches; no span is checked, because truth has no dataset placements.
4. "Best": conditions are grouped into method kinds. Inside each paper, the kind with the top value wins, and the answer is the kind with the most wins.
5. A (were the facts found) is the same for every kind. B: synonym merging (inventory), kind assignment (best), claim-to-result (consistency), pairing (effect, as today). C: the answer against the expected answer, with precision/recall for lists.
6. Baselines answer all 10 questions, with one answer form per kind.
7. One run per question. Corpora: `rag-claude-s1-mixed` (main) and `rag-tpl-hard-complex` (scale).
8. Trace: a new tab on the run page with one row per step, polling every 2 s. Clicking a row opens the full prompt and reply. Each run keeps its own copy of the prompts.
9. Cards: each kind has its own card set. The agent drafts every card with a reason; the user edits. Only run-breaking ("serious") problems block a freeze, and a waiver needs a written reason. Live checker plus paper preview. The Scores page leaves the flow (it stays as a CLI report).
10. Extractors and funnel order: regex → self-defined names (abbreviations) → GLiNER → number-first → LLM, with the gaps strategy. Each extractor is scored alone on A.
11. GLiNER runs as a small HTTP service inside llm-setup, on one of the three A100s, next to a model replica. On this PC a stand-in replaces it. The user allowed this one change to llm-setup.

## Global Constraints

- llm-setup: only Task C4 may change it, in a separate worktree of the llm-setup repo. Never touch the user's uncommitted changes in `llm-setup/`, and nothing is committed there without the user's sign-off.
- The hash of `evidence/protocols/rag-factuality.yaml` and of every existing protocol must not change (`Protocol.sha256`). Use `DIGEST_OMIT_AT_DEFAULT` for every new field.
- Existing EV2 run dirs and corpora must still load and score as before. Effect answers keep today's `answer.json` shape.
- Prompt changes follow `docs/prompt-writing.md`. Every new or changed prompt is a new versioned file (e.g. `frame-v3.md`); the old one stays.
- Python tests: `uv run pytest -q`. Frontend: `uv run --group frontend npm --prefix webapp/web ci`, then `npm test`, `npm run typecheck`, `npm run lint`. After backend model changes: `uv run webapp openapi -o webapp/web/openapi.json` and `npm run gen:api`, and commit `webapp/web/dist` after `npm run build`.
- Known failures that are not ours: `test_propose_flow::test_freeze_refuses_a_stale_draft_and_a_second_freeze`, `test_evidence_api::test_record_cache_scans_only_what_was_appended`, and the SIGKILL collection errors on Windows.
- Use the CLI entry points (`evidence`, `evaluate`, `synth`), not `python -m evidence`.
- Branches: `step2/questions` (Part A), then `step3/trace` (Part B) and `step5/extractors` (Part C) in parallel worktrees, then `step4/proposal` (Part D). Each branch is merged to local main after its review. Part E (the runbook) goes on main last.

## Review Focus

1. A paper that has no value for the question metric (for example, latency is missing in most papers). The effect, consistency and best answers mark it undetermined with a reason; they never crash and never count it. Test: A2 `test_best_paper_without_metric_is_undetermined`.
2. Two conditions tie for the top value in a "best" paper. There is no win for either, and the paper is listed as tied. Test: A2 `test_best_tie_gives_no_win`.
3. An inventory answer from a baseline names something that maps to no known vocabulary entry. It counts as a false positive, not an error. Test: A6 `test_inventory_unknown_name_is_false_positive`.
4. The trace is opened while the run is still going (only the warm pass has written anything). It shows the warm-pass rows and no error. Test: B2 `test_trace_during_warm_pass`.
5. The GLiNER service is down or slow. The GLiNER extractors return an extraction error, the funnel goes on to the next extractor, and the run finishes. Test: C3 `test_gliner_down_falls_through`.

---

## Part A — Step 2: questions, true answers, A/B/C per kind (branch `step2/questions`)

### Task A1: Protocol kinds and the dataset evidence type

**Files:**
- Modify: `evidence/contract.py:20-26` (EvidenceType gains `"dataset"`; `ITEM_PREFIX["dataset"] = "d"`)
- Modify: `evidence/protocol.py` (kind, kind blocks, optional synthesis, digest omits)
- Test: `evidence/tests/test_protocol_kinds.py`

**Interfaces:**
- Produces:
  - `Kind = Literal["effect", "inventory", "consistency", "best"]` in `evidence/protocol.py`.
  - `Protocol.kind: Kind = "effect"` and `Protocol.synthesis: Synthesis | None = None`.
  - `Protocol.inventory: Inventory | None = None`, where `Inventory(target: Literal["metric", "condition", "dataset"], same: dict[str, tuple[str, ...]] = {})` maps a canonical name to its other names.
  - `Protocol.best: Best | None = None`, where `Best(metric: QuestionMetric, kinds: dict[str, tuple[str, ...]], pairing: Pairing = Pairing())` maps a kind to the condition names that belong to it.
  - `Protocol.consistency: Consistency | None = None`, where `Consistency(by: Literal["direction"] = "direction")`.
  - `DIGEST_OMIT_AT_DEFAULT` gains `"kind": "effect"`, `"inventory": None`, `"best": None` and `"consistency": None`. The `synthesis: None` case is dropped from the digest the same way.

- [ ] **Step 1: Write the failing tests**

```python
def test_existing_protocol_hash_unchanged():
    p = protocol.load(REPO / "evidence/protocols/rag-factuality.yaml")
    assert p.kind == "effect"
    assert p.sha256 == RAG_FACTUALITY_SHA  # constant read from tests/EV2/corpora/rag-claude-s1-mixed/ground_truth.json protocol.sha256

def test_kind_needs_its_block():
    for kind, block in [("effect", "synthesis"), ("consistency", "synthesis"), ("inventory", "inventory"), ("best", "best")]:
        with pytest.raises(ValidationError, match=block):
            protocol.parse(minimal_yaml(kind=kind, omit=block))

def test_inventory_target_must_be_a_declared_type():
    with pytest.raises(ValidationError, match="inventory.target"):
        protocol.parse(minimal_yaml(kind="inventory", target="dataset", types=["metric"]))

def test_best_kinds_must_match_condition_kind_enum():
    with pytest.raises(ValidationError, match="best.kinds"):
        protocol.parse(minimal_yaml(kind="best", kinds={"rag": ["RAG"]}, condition_kind_enum=["rag", "baseline"]))

def test_dataset_item_prefix():
    assert Item.build("dataset", {"name": "TriviaCheck"}, [span]).item_id.startswith("d")
```

- [ ] **Step 2: Run them and see them fail.** `uv run pytest evidence/tests/test_protocol_kinds.py -q` → FAIL (unknown field `kind`).
- [ ] **Step 3: Implement.**
  - `_consistent` requires the block that belongs to the kind; `consistency` also requires `synthesis` and an `author_claim` type.
  - `_synthesis_matches_types` runs only when `synthesis` is set.
  - For kind `best`, the keys of `best.kinds` must equal `evidence_types.condition.fields.kind.enum`.
- [ ] **Step 4: Run** `uv run pytest -q` → the new tests PASS and nothing else breaks. Any existing caller of `protocol.synthesis` that assumes it is set gets `assert protocol.synthesis is not None` only where the kind guarantees it; Task A2 handles the engine.
- [ ] **Step 5: Commit** `evidence: protocol kinds (effect, inventory, consistency, best) and the dataset evidence type`.

### Task A2: Kind rules (engine side)

**Files:**
- Create: `evidence/kinds/__init__.py`, `evidence/kinds/effect.py`, `evidence/kinds/consistency.py`, `evidence/kinds/inventory.py`, `evidence/kinds/best.py`
- Modify: `evidence/engine.py:98-123` (build_extractors config, focus_for), `:191-200` (screened-out reason), `:309-321` (complete), `:360-376` (finish)
- Test: `evidence/tests/test_kinds.py`

**Interfaces:**
- Consumes: A1's `Protocol.kind` and the kind blocks; the existing `synthesis.study`, `synthesis.flag` and `synthesis.answer`.
- Produces (each kind module exposes the same three functions; `evidence.kinds.of(protocol)` returns the module):
  - `study(protocol, document: str, items: list[Item], preset: dict | None = None) -> tuple[dict, list[str]]` returns the per-document entry, which always has `entry["reason"]` (None or `{code, text}`), plus the item ids it used.
  - `gap_types(protocol, code: str) -> tuple[EvidenceType, ...]`.
  - `answer(protocol, documents, items, reasons, funnel) -> tuple[dict, list[str]]`.
  - `extractor_config(protocol) -> dict` holds the extra config that `build_extractors` passes today. For effect and consistency it is `question_metrics` and `compare`. For best it is `question_metrics=[best.metric.canonical]` and `kinds`. For inventory it is `target` and `same`.
- Answer shapes. Every non-effect answer has `"kind"` and `"system": "evidence-engine"`. Effect stays exactly today's `synthesis.answer`.
  - **consistency:**
    - `{"kind": "consistency", "metric": str, "studies": [{"document", "claim": str|None, "direction": str, "agrees": bool|None, "reason"}]}`;
    - plus `"agreeing": [doc]`, `"disagreeing": [doc]` and `"undetermined": [doc]`.
  - **inventory:**
    - `{"kind": "inventory", "target": str, "entries": [{"name": str, "aliases": [str], "papers": [doc], "items": [item_id]}]}`.
    - Entries are grouped by fold-case name plus `inventory.same`, and sorted by name.
  - **best:**
    - `{"kind": "best", "metric": str, "studies": [{"document", "winner": str|None, "tied": [str], "values": {kind: float}, "reason"}]}`;
    - plus `"wins": {kind: int}`, `"winner": str|None` and `"tied": [str]`.
    - When the most wins are shared, `winner` is None and `tied` lists the kinds.
- Gap codes, added to the existing `synthesis.GAP_TYPES` codes:
  - `no_target_items` → `(inventory.target,)`;
  - `too_few_kinds` → `("condition",)`;
  - `no_comparison` → `("measurement",)`;
  - `no_claim` → `("author_claim",)`.

- [ ] **Step 1: Write the failing tests.** Items are built with `Item.build` and a fixed span, using the helpers in `evidence/tests/conftest.py` when they exist.

```python
def test_effect_kind_is_todays_synthesis():          # same entry and answer as synthesis.study/answer on rag-factuality items
def test_consistency_agrees_and_disagrees():         # claim improves + direction supports -> agrees True; claim improves + contradicts -> False
def test_consistency_no_claim_gap():                 # no author_claim item -> reason code no_claim, gap_types == ("author_claim",)
def test_inventory_groups_same_names():              # items "Answer Accuracy", "answer accuracy", "AA" with same={"answer accuracy": ["AA"]} -> one entry, aliases ["AA", "Answer Accuracy"]
def test_inventory_no_items_gap():                   # target dataset, no dataset items -> no_target_items, gap_types == ("dataset",)
def test_best_counts_wins():                         # 3 docs: rag top, rag top, fine-tuned top -> wins {"rag": 2, "fine-tuned": 1}, winner "rag"
def test_best_tie_gives_no_win():                    # two kinds with equal top value -> study winner None, tied == sorted both, no win counted
def test_best_paper_without_metric_is_undetermined():# no measurement on best.metric -> winner None, reason code no_comparison
def test_best_lower_is_better():                     # latency-like metric higher_is_better False -> lowest value wins
def test_engine_runs_each_kind(tmp_path):            # evidence.engine.run on a 2-paper toy corpus with regex-only protocols of each kind -> answer.json has the kind's shape
```

- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement the kind modules and the engine wiring.**
  - `effect.py` wraps `synthesis.study`, `synthesis.answer` and `GAP_TYPES` unchanged.
  - `consistency.py` reuses `synthesis.study` per document. The `agrees` value is its `author_claim.agrees_with_data`; the reason is `no_claim` when the claim is missing and the direction is determined.
  - `best.py` picks the dataset in the same way as `Pairing` (the first dataset in document order that has values for at least two kinds; among several values of one kind, a table cell first, then the earlier value). It compares one value per kind.
  - The engine calls `kinds.of(protocol).study/gap_types/answer/extractor_config` wherever it calls `synthesis.*` today.
  - `focus_for` keeps today's behaviour for effect and consistency, and returns an empty `Focus()` for the other kinds.
- [ ] **Step 4: Run** `uv run pytest -q` → PASS. In particular, `evidence/tests/test_parallel.py` and every existing engine test still pass unchanged.
- [ ] **Step 5: Commit** `evidence: one rules module per question kind; engine dispatches on protocol.kind`.

### Task A3: Dataset extractors

**Files:**
- Modify: `evidence/extractors/regex.py` (add `DatasetRegex`, registered as `regex_dataset`), `evidence/extractors/llm.py:200` (`_factory("dataset")` registered as `llm_dataset`), `evidence/extractors/__init__.py`
- Modify: `evidence/extractors/prompts/` only if the LLM extractor needs a per-type line; if so, use a new prompt version
- Test: `evidence/tests/test_dataset_extractors.py`

**Interfaces:**
- Produces:
  - `regex_dataset`, with config `{"names": [str] | None, "pattern": str | None}`. By default it finds tokens matching `\b[A-Z][A-Za-z]+(QA|Bench|Set|Facts|Check|Quest)\b` and any configured names.
  - Each match becomes one item `{"name": str}` with span role `dataset_label`. Only the first span per name per paper is kept.
  - `llm_dataset` uses the generic LLM extractor with the protocol's dataset schema.

- [ ] **Step 1: Write the tests.** `test_regex_dataset_finds_names` uses text containing "TriviaCheck" and "LawFactQA" twice and expects 2 items. `test_regex_dataset_ignores_plain_words` expects "Question" and "Results" to produce no items. `test_llm_dataset_registered` expects `"llm_dataset" in extractors.names()`.
- [ ] **Step 2: See them fail.** **Step 3: Implement.** **Step 4: PASS.** **Step 5: Commit** `evidence: regex and LLM dataset extractors`.

### Task A4: The ten protocols and the question list

**Files:**
- Create in `evidence/protocols/`:
  - `rag-hallucination.yaml`, `rag-latency.yaml` (effect);
  - `inv-metrics.yaml`, `inv-methods.yaml`, `inv-datasets.yaml` (inventory);
  - `cons-accuracy.yaml`, `cons-hallucination.yaml` (consistency);
  - `best-accuracy.yaml`, `best-hallucination.yaml` (best).
- Create: `evidence/questions.py` (`QuestionTruth`, `QuestionEntry`, `load() -> list[QuestionEntry]` over `evidence/questions.yaml`; shared by webapp and evaluation)
- Modify: `evidence/questions.yaml` (10 entries), `webapp/evquestions.py:32-48` (its Entry gains `kind` and `truth` of these types), `webapp/evmodels.py` (`Question.kind`)
- Test: `evidence/tests/test_ten_protocols.py`, `webapp/tests/test_evquestions.py`

**Interfaces:**
- Produces:
  - In `evidence/questions.py`: `QuestionEntry.kind: Kind`.
  - `QuestionEntry.truth: QuestionTruth`, where `QuestionTruth(metric: str | None = None, min_effect: float | None = None, target: Literal["metric","condition","dataset"] | None = None)`.
  - The question ids are `rag-factuality`, `rag-hallucination`, `rag-latency`, `inv-metrics`, `inv-methods`, `inv-datasets`, `cons-accuracy`, `cons-hallucination`, `best-accuracy` and `best-hallucination`.
- Fixed values:
  - `rag-hallucination`: metrics `[hallucination_rate (lower is better)]`, `min_effect` 0.01.
  - `rag-latency`:
    - metric canonical enum `[latency, other]`; the synthesis metric is `latency`, lower is better;
    - `min_effect` 0.05 (seconds);
    - no `[0,1]` bound on latency values.
  - The consistency protocols use the effect blocks with a single metric each, plus `consistency: {by: direction}`.
  - The best protocols:
    - give conditions the fields `label` and `kind`;
    - use the kind enum `[no-retrieval, rag, rag-no-rerank, rag-random, fine-tuned, chain-of-thought, self-consistency, query-rewriting]`;
    - fill `best.kinds` with each kind's names from `synth/vocab.py` (BASELINES → no-retrieval, RAGS → rag, and each OTHERS entry → its own kind, label plus synonym).
  - Each inventory protocol declares only the types it needs: metrics needs `metric`; methods needs `condition` with `role` dropped; datasets needs `dataset`.
- Questions (exact text):
  - `rag-hallucination`: "Does retrieval-augmented generation reduce the hallucination rate of LLM-generated answers?"
  - `rag-latency`: "Does retrieval-augmented generation change the latency of LLM-generated answers?"
  - `inv-metrics`: "Which evaluation metrics do the papers report?"
  - `inv-methods`: "Which methods or system variants do the papers compare?"
  - `inv-datasets`: "Which datasets do the papers evaluate on?"
  - `cons-accuracy`: "Do the authors' conclusions about factual accuracy agree with their reported results?"
  - `cons-hallucination`: "Do the authors' conclusions about hallucination agree with their reported results?"
  - `best-accuracy`: "Which method achieves the highest factual accuracy within each paper?"
  - `best-hallucination`: "Which method achieves the lowest hallucination rate within each paper?"

- [ ] **Step 1: Tests.**
  - `test_all_ten_parse_and_match_questions_yaml` checks that every protocol parses and that its `question` and `kind` equal the questions.yaml entry.
  - `test_rag_factuality_untouched` checks that the hash is unchanged.
  - `test_best_kinds_cover_vocab` checks that every condition label in `synth.vocab` falls under exactly one kind.
  - `test_questions_api_lists_ten_with_kind` checks that `GET /api/ev/questions` returns 10 entries, each with a kind.
- [ ] **Steps 2–4:** fail, write the files, pass.
- [ ] **Step 5: Commit** `evidence: ten hand-written protocols over four kinds; questions.yaml carries kind and truth parameters`.

### Task A5: Expected answers from ground truth

**Files:**
- Create: `evaluation/canon.py`, `evaluation/expected.py`
- Modify: `evaluation/truth.py:27-70` (dataset facts: one per (paper, dataset name), id `"{paper}.d:{name}"`, data `{"name": name}`, no placements)
- Test: `evaluation/tests/test_expected.py`

**Interfaces:**
- Produces:
  - `canon.key(target: Literal["metric","condition","dataset"], name: str) -> str | None`. It maps any name, abbreviation or synonym in `synth/vocab.py` (case-folded, whitespace collapsed) to a stable key. Metric keys are vocab names, condition keys are labels, and dataset keys are names. Anything unknown gives None.
  - `canon.KIND_OF: dict[str, str]` maps a condition label to its best kind, with the same table as A4.
  - `expected.expected(truth: GroundTruth, kind: Kind, params: QuestionTruth, protocol: Protocol | None = None) -> dict` returns the kind's answer shape from A2, using study ids as documents. For the `rag-factuality` question it returns `truth.answer` unchanged.
- Rules:
  - **Counted studies:** relevant, not `duplicate_of`, and not `missing` the needed side.
  - **Main experiment:** the experiment of the study's `effect.treatment` measurement, or of the first measurement when the study has no effect.
  - **Metric:** factual_accuracy and hallucination_rate are found by `canonical`; latency is found by `name == "latency"`.
  - **Dataset:** the first dataset in measurement order within the main experiment that has the values needed.
  - **effect:** `rules.effect` with `params.min_effect`, then `rules.label` over the counts, using the label table of `rag-factuality.yaml`.
  - **consistency:** only studies whose claim metric (the study's primary metric) equals `params.metric`. `agrees` comes from `rules.claim_agrees`.
  - **inventory:** the set of keys over relevant papers, with the papers for each key.
  - **best:** the winning kind per study, using `KIND_OF`. Ties give no winner.

- [ ] **Step 1: Tests.** They read `tests/EV2/corpora/rag-claude-s1-mixed/ground_truth.json`.
  - `test_effect_matches_saved_answer` checks that `expected(... "effect", QuestionTruth(metric="factual_accuracy", min_effect=0.01), rag_factuality)` gives the same `label`, `supporting`, `contradicting` and `neutral` as `truth.answer`.
  - `test_inventory_datasets_are_vocab_names` checks that every entry name is in `synth.vocab.DATASETS` and that the paper lists are not empty.
  - `test_inventory_metrics_merge_synonyms` checks that "answer accuracy" and "AA" give the same key.
  - `test_best_uses_main_experiment_only` uses a hand-made study with an ablation experiment where `other` wins; the result counts the main experiment only.
  - `test_latency_effect_lower_is_better` uses a hand-made study with rag 1.21 s against baseline 1.25 s and min 0.05, and expects neutral.
  - `test_dataset_facts_loaded` checks that `truth.of("S001", "dataset")` names the paper's datasets.
- [ ] **Steps 2–4:** fail, implement, pass.
- [ ] **Step 5: Commit** `evaluation: expected answers per question kind from ground truth; dataset facts`.

### Task A6: A/B/C per kind

**Files:**
- Modify: `evaluation/score.py`:
  - `:185-235`: `compatible` and `cost` gain dataset matching by `canon.key` and metric matching through canon when the item canonical is a question-specific name like `latency`;
  - `:264`: span accuracy only over facts with placements;
  - `:281`, `:365`, `:871-905`.
- Modify: `evaluation/report.py:112` (one C section per kind), `evaluation/cli.py` (`score --question-id ID`, read via `evidence.questions.load()`)
- Test: `evaluation/tests/test_score_kinds.py`

**Interfaces:**
- Consumes: A5's `expected` and `canon.key`.
- Produces:
  - `score_kind(truth, kind, params, protocol, answer) -> dict` returns the C block. Its keys by kind:
    - effect: today's `score_synthesis` output;
    - consistency: `per_study_accuracy`, `disagreeing_precision`, `disagreeing_recall`;
    - inventory: `precision`, `recall`, `f1` over keys, plus `paper_precision`, `paper_recall` over (key, paper) pairs;
    - best: `winner_correct` (bool) and `per_study_accuracy`.
  - `integration_kind(m: Matching, kind, answer) -> dict` returns the B block. Its keys by kind:
    - effect: today's output;
    - inventory: `split` (count of truth keys spread over more than one entry), `merged` (entries holding more than one key) and `clean_share`;
    - best: `kind_accuracy` (matched condition items whose `kind` equals `KIND_OF[label]`);
    - consistency: `claim_accuracy` (matched claims with the right direction) plus today's pair check.
  - `score(run_dir, corpus, baselines, reexec, question_id: str = "rag-factuality")` dispatches by the question's kind. Baseline answers are scored on C only, as today.

- [ ] **Step 1: Tests.**
  - `test_inventory_unknown_name_is_false_positive`: an answer with an entry "MagicScore" gives precision below 1, and nothing raises.
  - `test_inventory_perfect_answer`: `expected()` scored against itself gives precision, recall and f1 of 1.0.
  - `test_best_winner_correct`.
  - `test_consistency_scores_disagreements`.
  - `test_dataset_items_match_by_name`: a dataset item without a usable span still matches.
  - `test_effect_scores_unchanged`: scoring a saved EV2 run equals the stored report numbers (use `tests/EV2/runs/...` as today's tests do).
- [ ] **Steps 2–4:** fail, implement, pass.
- [ ] **Step 5: Commit** `evaluation: A/B/C per question kind; score --question-id`.

### Task A7: Baselines answer every kind

**Files:**
- Modify: `evaluation/baselines/common.py:66-153` (one reply model per kind; `map_answer(..., kind, params)`), `evaluation/baselines/rag.py:181`, `evaluation/baselines/agent.py:67`, `evaluation/cli.py:93-133` (`--question-id`)
- Create: `evaluation/baselines/prompts/map-<kind>-v1.md` if the map instructions move to files (follow `docs/prompt-writing.md`)
- Test: `evaluation/tests/test_baseline_kinds.py`

**Interfaces:**
- Produces:
  - `InventoryReply(entries: list[{name: str, papers: list[str]}])`;
  - `BestReply(studies: list[{paper: str, winner: str | None}])`. The winner is one of the protocol's kinds, given in the instructions;
  - `ConsistencyReply(studies: list[{paper: str, claim: Literal["improves","no_effect","worsens"] | None, agrees: bool | None}])`;
  - effect keeps `AnswerReply`.
  - `answer_json` writes the A2 shape for the kind, with `system` set to the baseline's name. For best, `wins` and `winner` are computed by code from the reply's per-paper winners, never asked of the model.
- [ ] **Step 1: Tests** use a scripted model (as the existing baseline tests do).
  - `test_rag_baseline_inventory_shape` checks that the answer has kind inventory and entries.
  - `test_best_wins_computed_not_asked` checks that the reply's per-paper winners give the counts.
  - `test_unknown_kind_name_rejected` checks that a winner outside the kinds list fails validation and goes through the existing retry path.
  - `test_cli_question_id_sets_question_text`.
- [ ] **Steps 2–4:** fail, implement, pass.
- [ ] **Step 5: Commit** `evaluation: baselines answer all four question kinds`.

### Task A8: Web app shows the ten questions and per-kind answers

**Files:**
- Modify: `webapp/evmodels.py` (Answer union by kind), `webapp/evapi.py`, `webapp/web/src/components/ev/AnswerPanel.tsx`, `webapp/web/src/components/flow/ProtocolStep.tsx` (kind chip next to each question), `webapp/web/src/components/flow/ResultSteps.tsx` (drop the Scores step), `webapp/web/src/pages/flow/flow.test.tsx`, `webapp/web/src/pages/ev/ev-pages.test.tsx`
- Regenerate: `webapp/web/openapi.json`, `webapp/web/src/api/schema.d.ts`, `webapp/web/dist`

**Interfaces:**
- Consumes: the A2 answer shapes and the A4 `Question.kind`.
- Produces: `AnswerPanel` renders:
  - effect as today;
  - inventory as a table of name, other names and papers;
  - consistency as an agree/disagree table;
  - best as the wins per kind plus a per-paper winner table.
- [ ] **Step 1: Tests (vitest).**
  - `renders inventory answer` shows the name and the paper chips.
  - `renders best winner and tie`.
  - `question list shows kind chips`.
  - `flow has no scores step`.
- [ ] **Steps 2–4:** fail, implement, pass, plus typecheck and lint.
- [ ] **Step 5: Commit** `webapp: ten questions with kinds; per-kind answer panels; scores out of the flow`.

---

## Part B — Step 3: live run trace (branch `step3/trace`, from main after Part A)

### Task B1: Each run keeps its own copy of every call

**Files:**
- Modify: `evidence/rundir.py` (add `RunCalls`), `evidence/engine.py:332-358` (`_call`) and `:379-395` (`_warm`)
- Test: `evidence/tests/test_run_calls.py`

**Interfaces:**
- Produces:
  - `RunCalls(path: Path)`, which holds a `threading.Lock`.
  - `RunCalls.add(row: dict) -> None` appends one JSON line. A row whose `key` was already written is skipped.
  - The file is `<run>/calls.jsonl`. Its rows are `{"key", "phase": "warm"|"run", "document", "evidence_type", "extractor_id", "attempt", "status", "source": "fresh"|"cache", "started_at", "ended_at", "task", "result", "model_calls": [full records as in evidence/recording.py]}`.
  - The warm pass writes each call as it completes (`phase` warm). The main loop writes calls the warm pass did not write (`phase` run).
  - `calls.jsonl` is not in the hash chain, and its row order may vary with workers. `answer.json`, `events.jsonl` and the items stay byte-identical, as the test_parallel tests already check.
- [ ] **Step 1: Tests.**
  - `test_calls_jsonl_has_every_call_once` checks, for workers 1 and 3, that the set of keys equals the model-backed extractor calls named in events.
  - `test_calls_jsonl_holds_prompts` checks that `model_calls[0]["request"]["user_prompt"]` is not empty.
  - `test_outputs_still_identical_with_calls_jsonl` reuses the test_parallel comparison and ignores `calls.jsonl`.
- [ ] **Steps 2–4:** fail, implement, pass. **Step 5: Commit** `evidence: runs keep their own calls.jsonl with full prompts and replies`.

### Task B2: Trace API

**Files:**
- Create: `webapp/evtrace.py`
- Modify: `webapp/evapi.py:76-105` (routes), `webapp/evmodels.py` (`TraceRow`, `TracePage`), and the call-detail lookup at `webapp/evmodels.py:399-418` (try `calls.jsonl` first, then the cache)
- Test: `webapp/tests/test_evtrace.py`

**Interfaces:**
- Produces:
  - `GET /api/ev/runs/{run}/trace?after={n:int=0}` returns `TracePage{rows: list[TraceRow], next: int, done: bool}`.
  - `TraceRow{n, phase: "warm"|"run", step: "screen"|"locate"|"extractor_call"|"merge"|"completeness"|"synthesis"|"call", document: str|None, evidence_type: str|None, extractor: str|None, status: str, source: str|None, seconds: float|None, input_tokens: int|None, output_tokens: int|None, call: str|None}`.
  - Rows come from `calls.jsonl` (phase warm, step call) and `events.jsonl` (phase run), in file order: first the warm rows, then the events.
  - `done` is true when `answer.json` exists.
  - `call` is the key used by `GET /api/ev/runs/{run}/calls/{call}`, which now also accepts a calls.jsonl key.
- [ ] **Step 1: Tests.**
  - `test_trace_pages_with_after`.
  - `test_trace_during_warm_pass`: a run dir with only `calls.jsonl` gives warm rows, `done` false, and no error.
  - `test_trace_done_after_answer`.
  - `test_call_detail_from_run_copy_when_cache_gone`.
- [ ] **Steps 2–4:** fail, implement, pass. **Step 5: Commit** `webapp: run trace API over events.jsonl and calls.jsonl`.

### Task B3: Developer tools tab

**Files:**
- Create: `webapp/web/src/components/ev/TraceTab.tsx`
- Modify: `webapp/web/src/api/ev.ts` (`useTrace(run)`, which polls every 2000 ms while the run's job is active and stops when `done`), `webapp/web/src/pages/ev/RunPage.tsx` (tab "Developer tools"), `webapp/web/src/pages/ev/ev-pages.test.tsx`
- Regenerate: openapi, schema.d.ts, dist

**Interfaces:**
- Consumes: B2's `TracePage`.
- Produces:
  - A table with one row per step: time, phase, step, paper, type, extractor, status, seconds, tokens. Filters by paper and by status.
  - Clicking a row with a `call` opens the existing `CallSheet`, which shows the full prompt and reply.
- [ ] **Step 1: Tests (vitest).**
  - `trace tab lists rows and opens call sheet`.
  - `trace polls while running and stops when done`.
  - `filter by status shows errors only`.
- [ ] **Steps 2–4:** fail, implement, pass, plus typecheck and lint. **Step 5: Commit** `webapp: Developer tools tab with the live run trace`.

---

## Part C — Step 5: extractors (branch `step5/extractors`, from main after Part A, in parallel with Part B)

### Task C1: Self-defined names (abbreviations)

**Files:**
- Create: `evidence/extractors/abbrev.py`
- Modify: `evidence/extractors/__init__.py` (register `abbrev_condition`, `abbrev_metric`)
- Test: `evidence/tests/test_abbrev.py`

**Interfaces:**
- Produces:
  - `definitions(text: str) -> list[Definition]`, where `Definition(long: str, short: str, start: int, end: int)`. It finds "Long Form (LF)" and "LF (Long Form)" when the short form's letters are, in order, the initials of the long form's words (or the first letters of hyphen parts).
  - `abbrev_condition` and `abbrev_metric` (kind `regex`) find each use of a short form whose long form matches a protocol term (the same terms config as the regex extractors). Each emits an item with the long form as `label`/`name`, the role or canonical from the long form's term, and a span on the short form.
- [ ] **Step 1: Tests.**
  - `test_definition_found`: "fact-level accuracy (FLA)" gives long "fact-level accuracy" and short "FLA".
  - `test_not_a_definition`: "accuracy (see Table 2)" gives nothing.
  - `test_short_form_in_table_becomes_metric_item`: a table header "FLA" after the definition gives one metric item, canonical factual_accuracy.
- [ ] **Steps 2–4**, then **Step 5: Commit** `evidence: abbreviation extractors for self-defined names`.

### Task C2: Number-first search

**Files:**
- Create: `evidence/extractors/numbers.py` (register `number_measurement`)
- Test: `evidence/tests/test_numbers.py`

**Interfaces:**
- Consumes: the measurement task context items (condition, metric, and dataset when the protocol declares it) and `base.numbers`/`base.tables`.
- Produces: `number_measurement` (kind `regex`). For every number in the located scope:
  - **Table cell:** the condition comes from the row label, the metric from the column header, and the dataset from a header or caption that names a dataset item.
  - **Sentence:** the nearest condition label and metric label in the same sentence.
  - Emit a measurement only when both a condition and a metric resolve. Normalise percent values to fractions, but only for metrics bounded in [0,1].
- [ ] **Step 1: Tests.**
  - `test_table_cell_number`.
  - `test_sentence_number`.
  - `test_number_without_condition_skipped`.
  - `test_seconds_not_normalised`: latency 1.21 stays 1.21.
- [ ] **Steps 2–4**, then **Step 5: Commit** `evidence: number-first measurement extractor`.

### Task C3: GLiNER client extractors

**Files:**
- Create: `evidence/extractors/gliner.py` (register `gliner_condition`, `gliner_metric`, `gliner_dataset`), `evidence/tests/fake_gliner.py` (a stand-in HTTP server for tests)
- Modify: `evidence/engine.py` settings (`GLINER_URL` from the environment; None disables), `.env.example` if present
- Test: `evidence/tests/test_gliner.py`

**Interfaces:**
- Produces:
  - Kind `model`. Each extractor sends `POST {GLINER_URL}/predict` with `{"text": chunk, "labels": [str], "threshold": float}` and receives `{"entities": [{"start": int, "end": int, "text": str, "label": str, "score": float}]}`.
  - The labels are, by type: condition `["method", "system variant", "baseline model"]`, metric `["evaluation metric"]` and dataset `["dataset"]`. They can be overridden in the protocol config.
  - The threshold defaults to 0.5. Chunks are at most 1500 chars, with offsets mapped back to the document.
  - The role or canonical comes from the regex term lists (`terms.py`); when nothing matches, it is `other`.
  - The calls are recorded and cached like model calls: the task hash includes `GLINER_URL`'s model name from `GET {GLINER_URL}/info`.
  - A timeout (10 s) or connection error returns an `ExtractionError`, so the cascade goes on.
- [ ] **Step 1: Tests.**
  - `test_gliner_items_from_fake_server`.
  - `test_gliner_offsets_mapped_across_chunks`.
  - `test_gliner_down_falls_through`: with no server, a gaps run with cascade `[gliner_metric, llm_metric]` still reaches the LLM extractor and finishes.
  - `test_gliner_disabled_without_url`.
- [ ] **Steps 2–4**, then **Step 5: Commit** `evidence: GLiNER client extractors over HTTP`.

### Task C4: GLiNER service in llm-setup (separate repo; needs the user's sign-off)

**Files (in a new worktree of the llm-setup repo, `git -C llm-setup worktree add ../llm-setup-gliner -b gliner`, from its HEAD; the user's uncommitted edits in `llm-setup/` stay untouched):**
- Read first: `llm-setup/AGENTS.md`, `slurm/llm-stack.sbatch`, `profiles/orch-3x40.yaml`, `docs/OPERATIONS.md`
- Create: `src/llm_setup/gliner_server.py` (FastAPI: `POST /predict` and `GET /info` with the contract of C3; loads `urchade/gliner_medium-v2.1` on `cuda:0` at start)
- Modify: `pyproject.toml` (deps `gliner` and `torch`; torch from the PyTorch CUDA index, defaulting to `cu124` until Codex reports `nvidia-smi`), the profile YAML (`gliner: {enabled: bool, gpu: 0, port: 8090, model: str}`), `slurm/llm-stack.sbatch` (start the server when enabled, next to the replica on that GPU)
- Test: llm-setup's own test layout, with a test for `/predict` that uses a fake model object

- [ ] **Step 1:** Write the tests the llm-setup way. **Step 2:** fail. **Step 3:** implement. **Step 4:** pass.
- [ ] **Step 5:** Commit on branch `gliner` in llm-setup, but do NOT merge or push. Show the user the diff and ask before anything else.

### Task C5: Funnel order in the protocols

**Files:**
- Modify: the cascades of the 10 protocols in `evidence/protocols/` (but NOT `rag-factuality.yaml`, whose hash is fixed; give it a sibling `rag-factuality-funnel.yaml` with the new cascade)
- Test: `evidence/tests/test_funnel_order.py`

**Interfaces:**
- Produces: the cascade order per type.
  - **condition and metric:** regex → abbrev → gliner → llm;
  - **measurement:** regex → number → llm;
  - **dataset:** regex → gliner → llm;
  - **author_claim:** regex → llm.
  - The GLiNER steps are left out automatically when `GLINER_URL` is unset (engine: skip an extractor whose `available()` is False, recorded as a `skipped` status).
- [ ] **Step 1: Tests.**
  - `test_cascade_order` covers every protocol.
  - `test_unavailable_extractor_skipped_and_recorded`.
  - `test_per_extractor_A_reports_new_extractors`: `score_extractors` lists `number_measurement`, `abbrev_metric` and `gliner_metric`.
- [ ] **Steps 2–4**, then **Step 5: Commit** `evidence: funnel order regex → abbrev → GLiNER → number → LLM`.

---

## Part D — Step 4: per-kind cards, agent draft, checker (branch `step4/proposal`, from main after Parts B and C)

### Task D1: Frame guesses the kind; the draft starts from the kind's template

**Files:**
- Create: `evidence/propose/prompts/frame-v3.md` (adds `kind` with one example per kind; follow `docs/prompt-writing.md`)
- Modify: `evidence/propose/frame.py`, `evidence/propose/common.py:19` (`KIND_TEMPLATES`: effect → rag-factuality.yaml, consistency → cons-accuracy.yaml, inventory → inv-metrics.yaml, best → best-accuracy.yaml), `evidence/propose/draft.py:183`, `evidence/cli.py:90-150` (`propose frame --kind K` overrides the guess), `webapp/evjobs.py:275-297` (`PUT /api/ev/proposals/{name}/kind`, which re-runs the draft, critic and cards)
- Test: `evidence/tests/test_propose_kinds.py`

**Interfaces:**
- Produces:
  - `frame.json` gains `kind` and `kind_reason`.
  - `draft.build(frame, kind)` starts from `KIND_TEMPLATES[kind]` and copies only the fields that kind's cards set.
  - `proposal.json` records `kind` and `kind_by: "model"|user`.
- [ ] **Step 1: Tests.**
  - `test_frame_reply_has_kind` uses a scripted model.
  - `test_draft_uses_kind_template` checks each kind against its template's `kind` and blocks.
  - `test_kind_override_redrafts`.
- [ ] **Steps 2–4**, then **Step 5: Commit** `propose: frame guesses the question kind; draft starts from that kind's template`.

### Task D2: Card sets per kind, drafted by the agent

**Files:**
- Modify: `evidence/propose/cards.yaml` (each card gains `kinds: [...]` and `advanced: bool`), `evidence/propose/cards.py:217-522` (handlers for the new cards)
- Create: `evidence/propose/prompts/cards-v2.md`
- Test: `evidence/tests/test_cards_kinds.py`

**Interfaces:**
- Produces: the card sets.
  - **effect:** screen, roles, metrics, min_effect, pairing, label.
  - **consistency:** the effect set plus `claim_check` (sets `consistency.by`, with only `direction` offered).
  - **inventory:** screen, `list_target` (sets `inventory.target`), `same_names` (sets `inventory.same`).
  - **best:** screen, `best_metric` (sets `best.metric`), `method_kinds` (sets `best.kinds` and the condition kind enum), `win_rule` (sets `best.pairing`).
  - `cascade` and `locate` appear for every kind with `advanced: true` (collapsed in the UI).
  - `cards.for_kind(kind) -> list[CardSpec]`.
  - The agent drafts every card of the kind in one `cards` step, with a value and a one-sentence reason, as today.
- [ ] **Step 1: Tests.**
  - `test_card_set_per_kind` checks the exact id lists above.
  - `test_method_kinds_card_writes_enum_and_kinds`.
  - `test_validate_rejects_card_of_other_kind`.
- [ ] **Steps 2–4**, then **Step 5: Commit** `propose: card sets per question kind, drafted by the agent`.

### Task D3: Checker, live check and paper preview

**Files:**
- Modify: `evidence/propose/critic.py:56-85` (severity names `serious`/`advisory`; new deterministic checks), `webapp/evjobs.py` / `webapp/evapi.py`
- Create: `webapp/evcheck.py`
- Test: `evidence/tests/test_critic_kinds.py`, `webapp/tests/test_evcheck.py`

**Interfaces:**
- Produces:
  - **Serious checks:**
    - today's blocking set;
    - `inventory_target_declared`;
    - `best_kinds_nonempty` (every kind has at least one name);
    - `best_kinds_disjoint` (no name in two kinds);
    - `claim_type_present` (consistency).
    - Everything else is advisory.
  - `POST /api/ev/proposals/{name}/check {decisions}` returns `{problems: [{check, severity, message, card}]}`. It runs the deterministic checks only, in under 1 s and without a model call.
  - `GET /api/ev/proposals/{name}/preview?corpus=C&paper=P` returns `{text, hits: [{start, end, card, what}]}`, showing where the current screen terms, synonyms and kind names hit in that paper.
  - Freeze refuses an unwaived serious problem, and a waiver reason must be at least 10 characters (extend `cards.waivers()` validation).
- [ ] **Step 1: Tests.**
  - `test_best_kinds_disjoint_serious`.
  - `test_check_endpoint_fast_and_modelless` asserts that no provider is called.
  - `test_preview_hits_terms`.
  - `test_waiver_needs_reason`.
- [ ] **Steps 2–4**, then **Step 5: Commit** `propose: serious/advisory checker per kind, live check and paper preview endpoints`.

### Task D4: The question-first flow in the web app

**Files:**
- Modify: `webapp/web/src/pages/flow/FlowPage.tsx`, `webapp/web/src/components/flow/{ProtocolStep,CardsForm,cards.ts,flow.ts}.tsx|ts`, `webapp/web/src/api/ev.ts`, `webapp/web/src/pages/flow/flow.test.tsx`
- Create: `webapp/web/src/components/flow/{QuestionStep,KindConfirm,CheckerPanel,PaperPreview,WaiverDialog}.tsx`
- Regenerate: openapi, schema.d.ts, dist

**Interfaces:**
- Consumes: A4's questions, D1's kind endpoint, D2's card sets, and D3's check and preview endpoints.
- Produces the flow:
  1. Pick one of the 10 questions, or type your own.
  2. Confirm or change the kind. A typed question starts a propose job.
  3. Edit the cards of that kind. The advanced cards are collapsed. The checker panel calls `/check`, debounced by 400 ms. A preview panel next to the cards shows `/preview` for a chosen paper.
  4. Freeze. A serious problem opens the WaiverDialog, which requires a reason.
  5. Corpus, then run, then the results, with no Scores step.
- [ ] **Step 1: Tests (vitest).**
  - `typed question starts propose job`.
  - `kind change reloads cards`.
  - `serious problem blocks freeze until waiver reason`.
  - `preview highlights hits`.
- [ ] **Steps 2–4:** fail, implement, pass, plus typecheck and lint. **Step 5: Commit** `webapp: question-first flow with per-kind cards, checker and waiver`.

---

## Part E — Codex runbook (on main, after Part D)

### Task E1: Runbook for the Slurm runs

**Files:**
- Create: `docs/runbook-question-first.md`

It holds the steps Codex follows, each with the exact command and what a good result looks like:

1. On a GPU node, run `nvidia-smi` and report the driver and CUDA version. Pin the matching torch index in the llm-setup `gliner` branch, if the user has merged it.
2. Start the stack with the profile that has `gliner.enabled: true`. Check `GET :8090/info` and one `/predict` call.
3. For each of the 10 question ids, on `rag-claude-s1-mixed` and `rag-tpl-hard-complex`, run:
   - `evidence run` (strategy gaps, `--workers 3`, `GLINER_URL` set);
   - `evaluate rag-baseline --question-id`;
   - `evaluate agent-baseline --question-id`;
   - `evaluate score --question-id`.
4. Collect the reports into one table: question × system × A/B/C. Report the per-extractor A for the new extractors.
5. Hand back a branch holding the report files only.

Never put `synth build` in this runbook; corpora are built locally.

- [ ] **Step 1:** Write the runbook. **Step 2:** Run every command that works offline (the regex-only selection, the scripted model) to check that it is spelled right. **Step 3: Commit** `docs: runbook for the question-first runs on Slurm`.
