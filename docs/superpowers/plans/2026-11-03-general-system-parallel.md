# General Evidence System (parallel build) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the evidence system general (any field, any question shape) as agreed in the spec's "Robustness review (3 Nov)": LLM-written words, public ontologies, clean reading of real papers, a records graph answered by SPARQL, open claims and links, decision reruns, a human-confirmed plan, and whole-run scoring on real labelled sets.

**Architecture:** Wave 0 fixes the shared contracts (record types, graph vocabulary, plan file, DSPy step wrapper, engine seams) on one branch. Then seven workstreams build at once, each on its own branch and worktree, each owning its own files and plugging into the engine only through the Wave 0 seams. Wave 2 wires them into one run, adds DSPy tuning and runs the end-to-end check.

**Tech Stack:** Python 3.13, uv, pytest, pydantic, pyoxigraph (SPARQL), rdflib + owlrl (ontology), DSPy (new), pdfplumber (new), Docling (fetch group), httpx (OpenAlex, arXiv, PMC), FastAPI + React (webapp/web).

**Spec:** `docs/superpowers/specs/2026-11-02-question-planning-design.md`, the agreed sections only. Where the spec's earlier drafts conflict with later agreed text, the later text wins (see "Spec reading" below).

## Spec reading (which text wins)

- "Building blocks… typed JSON chain" (2 Nov) is replaced by "the answer is a SPARQL query the plan writes" (3 Nov). The 7 kinds become saved SPARQL templates.
- "Sub-questions tagged with kinds" and "headline" are replaced by evidence lines + main-answer rule on one page with a decisions panel (2 Nov "One page", "Human in the loop").
- "Pilot-run view" (What changes in code) is dropped (2 Nov item 4).
- "Read numbers: the model labels each number" is replaced by "D40 narrowed": the funnel stays, the LLM re-checks regex/code finds one paragraph per call.
- Open question 2 ("build now or after EV4") is taken as: build now (Aditya said "plan it", 3 Nov).

## Decisions before build (Aditya, 3 Nov)

- Plan confirmation in scoring (Tasks 8.1, 8.3): two rows per set: "auto-confirmed" (`confirm_all(plan, who="system")`) for every question, and "hand-confirmed" for 5 questions per set that Aditya confirms in the planning page. `evaluate wholerun` takes `--confirm auto|hand` and the report shows both rows.
- Real-paper sources (Tasks 6.2–6.4): open-access full text only (arXiv, PMC). Papers without open full text are left out and counted; the report states "left out: N of M (no open full text)".
- Run size (Task 8.3): a fixed sample of 10 questions per set first (`--sample 10 --seed 0`, sample list saved with the run); the rest only if time allows.
- DSPy tuning data (Task 8.2): real-paper steps (tables, value check, claims) tune on a held-out slice of each real set, written to `tune_split.json` and excluded from every score; all other steps tune on the Claude-written synthetic corpora. `wholerun.score` refuses a question whose papers appear in `tune_split.json`.
- Ontology files (Tasks 2.1, 8.4): MeSH XML and CS-KG are fetched once on Slurm into a shared folder (`$EV_ONTOLOGY_DIR`), never committed; each file's SHA-256 goes into the run lockfile (`ontology_sha256`); a missing file means "reasoning off: no tree", not a crash. QUDT (small) may stay in the repo.
- If time runs short, cut in this order: first the materials sets (Task 6.4, SOFC-Exp and MeasEval), then links and builds-on (W5, Tasks 5.2 and the link scoring in 8.3). Words, papers, graph, planner, the SciLead / SciREX / CochraneForest scoring, the RAG baseline (6.5) and the off-template check (6.6) are never cut.
- DSPy tuning budget (Task 8.2): every step uses GEPA's light setting, capped at 500 model calls per step (`max_metric_calls=500`), the same for all steps; the call count goes into `tuned/<name>.json`.

## Global Constraints

- No hand-typed topic words for a run: screen, regex and claim cue words come from the locked word list (`WordList`), never from `domains/<name>/words.yaml`. Existing packs keep working for old protocols (replay must stay byte-identical).
- Word list: 20–50 other names, spellings and abbreviations per thing, written from the question alone; the writer never reads the test papers.
- The word list is written by a different model family than the synthetic papers. Papers are Claude-written (`tests/EV2/corpora/rag-claude-*`); the word list uses the pinned `orch-model` (Qwen, `modelcall/pins.py`). Leak scores use only Claude-written corpora.
- No sentence transformers and no embedding retrieval.
- No vision model.
- No pilot run; an empty answer is a valid answer ("No evidence found").
- Every model step is a DSPy signature; no hand-tuned prompt text for new steps. Tuning papers and test papers are disjoint.
- Every LLM call goes through the run's recorder (cached, replayable), as `modelcall.ask` calls do today.
- Ontology per field: computer science → CS-KG (as today); medicine → MeSH; units in every field → QUDT. No hand-written ontology for a new field.
- Exact user-facing strings: "No evidence found", "failed: <reason>", "missing: <line>", "reasoning off: no tree", "made by LLM", "table unsure", "outside the set", "indirect", "conflicting", "on the list", "unseen", labels "solid" / "same direction" / "depends on <field>" / "too few to tell".
- Decision alternatives: must-match drops or adds one field; counts-as removes or adds one value; threshold uses 0, main, 2× main; order strict → main → loose.
- Scoring: rankings by top-1 and Kendall tau; lists by precision and recall; every query also runs on the answer key's records (synthesis vs extraction split).
- The synthetic generator stays RAG comparisons only. No 10k-paper target.
- Every real-set score has a RAG baseline row on the same questions, papers and model (Task 6.5).
- The generality claim is reported as two numbers: share of questions answered with a fresh query, and the off-template match rate (Task 6.6).
- Replies/docs follow CLAUDE.md; prompt and workflow work follows `docs/prompt-writing.md`.

## Review Focus

1. A paper where the word list matches nothing (new field, odd wording): expect screen to keep it for the LLM screen, not drop it silently; the funnel record shows why. Test in Task 1.3.
2. A run with no ontology for its field: expect "reasoning off: no tree" in the answer and the run to finish. Test in Task 2.3.
3. A SPARQL query the plan writes that is syntactically valid but returns nothing: expect "No evidence found" with the reasons of unused records, not an error. Test in Task 4.2.
4. One evidence line crashes (model error, bad query): expect the other lines to finish, that line "failed: <reason>", the answer "missing: <line>". Test in Task 7.3.
5. A PDF with no table text for pdfplumber (scanned page): expect Docling's value kept and marked "table unsure", not dropped. Test in Task 3.2.

---

## Branches, worktrees and file ownership

Each workstream runs in its own worktree (`superpowers:using-git-worktrees`) on branch `gen/<id>` cut from `gen/w0` after Wave 0 merges into `main`. A workstream edits only the files it owns below; anything else goes through a Wave 0 seam or waits for Wave 2.

| Stream | Branch | Owns (create or modify) |
|---|---|---|
| W0 contracts | `gen/w0` | `evidence/records.py`, `evidence/plan.py`, `evidence/stages.py`, `evidence/vocab/ev.ttl`, `modelcall/dspy_lm.py`, `evidence/steps/__init__.py`, small seam edits in `evidence/engine.py`, `evidence/lockfile.py`, `pyproject.toml` |
| W1 words | `gen/w1-words` | `evidence/words/` (new), `evidence/extractors/recheck.py` (new), `evaluation/leak.py` (new) |
| W2 ontology | `gen/w2-onto` | `evidence/ontology/` (new), `evidence/reasoner.py` |
| W3 papers in | `gen/w3-papers` | `evidence/arxiv.py`, `evidence/sources/` (new), `evidence/tables.py` (new), `evidence/experiments.py` (new), `evidence/rules.py` (`duplicates` only), `synth/levels.py`, `synth/render_template.py` |
| W4 graph + answers | `gen/w4-graph` | `evidence/kg/` (new: graph, query, templates/, sensitivity) |
| W5 claims + links | `gen/w5-claims` | `evidence/claims.py` (new), `evidence/openalex.py` (new) |
| W6 real sets | `gen/w6-real` | `evaluation/realpapers/` (new files + `scilead.py`, `scirex.py`), `evaluation/wholerun.py` (new), `evaluation/baselines/real.py` (new), `evaluation/offtemplate/` (new) |
| W7 planner + UI | `gen/w7-plan` | `evidence/planner/` (new), `webapp/evplan.py` (new), `webapp/web/src/routes/plan/` (new) |
| Wave 2 | `gen/integrate` | `evidence/engine.py` wiring, `evidence/cli.py`, `evaluation/cli.py`, `scripts/`, DSPy tuning `evidence/steps/tune.py` |

Order: Wave 0 (Tasks 0.1–0.5, one worker, sequential) → Wave 1 (W1–W7 in parallel; inside a stream, tasks are sequential) → Wave 2 (Tasks 8.1–8.4, sequential). W7 Task 7.2 consumes W1/W4 interfaces by their Wave 0 contracts and tests with fakes, so it does not wait.

Test command everywhere: `uv run pytest <path> -v`. Commit after each task with the attribution line from the session.

---

## Wave 0: shared contracts

### Task 0.1: Record types

**Files:**
- Create: `evidence/records.py`
- Modify: `evidence/contract.py` (register prefixes only)
- Test: `evidence/tests/test_records.py`

**Interfaces:**
- Produces (pydantic, `Frozen` from `evidence/contract.py`):
  - `Experiment(exp_id: str, document: str, label: str, setting: dict[str, str], span: Span)`; `setting` keys are field names such as `dataset`, `model`, `population`.
  - `ClaimRecord(subject: str, relation: str, object: str | None, setting: dict[str, str], strength: Literal["firm", "hedged"], direction: Literal["improves", "worsens", "no_effect"] | None, span: Span, relation_group: str | None = None)`; `relation` keeps the paper's own verb, `relation_group` is filled after the run by W5's grouping (Task 5.1) and is what queries match.
  - `LinkRecord(subject_doc: str, relation: str, object_ref: str, object_doc: str | None, outside_set: bool, span: Span)`; `object_ref` is a DOI, an arXiv id or the cited text.
  - Evidence types registered: `experiment` (prefix `x`), `claim` (prefix `cl`), `link` (prefix `ln`). Existing prefixes `c k m a s d mt tk` stay untouched.

- [ ] **Step 1: Write the failing tests**

```python
def test_prefixes_registered_and_unique():
    from evidence.contract import ITEM_PREFIX
    import evidence.records  # registers
    assert ITEM_PREFIX["experiment"] == "x" and ITEM_PREFIX["claim"] == "cl" and ITEM_PREFIX["link"] == "ln"
    assert len(set(ITEM_PREFIX.values())) == len(ITEM_PREFIX)

def test_claim_strength_is_closed():
    with pytest.raises(ValidationError):
        ClaimRecord(subject="RAG", relation="raises", object="accuracy", setting={}, strength="maybe",
                    direction=None, span=SPAN)

def test_records_hash_stable():
    assert digest(EXP.model_dump(mode="json")) == digest(Experiment(**EXP.model_dump()).model_dump(mode="json"))
```

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError: evidence.records`)
- [ ] **Step 3: Implement the three models and register the types in `evidence/records.py`** (call `evidence_types.register` at import; `item(record) -> Item` converts each record to an `Item` of its type with the record's span).
- [ ] **Step 4: Run, expect PASS**; also `uv run pytest evidence/tests -q` stays green.
- [ ] **Step 5: Commit** `feat(records): experiment, claim and link record types`

### Task 0.2: Graph vocabulary

**Files:**
- Create: `evidence/vocab/ev.ttl`, `evidence/vocab/__init__.py`
- Test: `evidence/tests/test_vocab.py`

**Interfaces:**
- Produces: namespace `EV = "https://w3id.org/thesis-ev#"` (Python constant `evidence.vocab.EV`). Classes `ev:Paper ev:Experiment ev:Thing ev:Metric ev:Value ev:Claim ev:Link ev:Comparison`. Properties: `ev:inPaper ev:inExperiment ev:of (Value→Thing) ev:onMetric ev:number ev:setting_<field> (one per setting key, literal) ev:source (span JSON literal) ev:name ev:a ev:b ev:delta ev:better (Comparison) ev:subject ev:relation ev:object ev:strength ev:direction (Claim) ev:cites ev:outsideSet (Link) ev:madeBy ("code" | "llm" | "human")`. Things and metrics link to ontology classes with `rdf:type`; "kind of" is `rdfs:subClassOf*`.

- [ ] **Step 1: Failing test**: parse `ev.ttl` with pyoxigraph; assert every name above exists as `rdfs:Class` or `rdf:Property`, and `evidence.vocab.EV` equals the ttl's prefix.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Write `ev.ttl`** with an `rdfs:comment` on each term.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(vocab): records graph vocabulary`

### Task 0.3: Plan file and lock

**Files:**
- Create: `evidence/plan.py`
- Modify: `evidence/lockfile.py` (add the plan's sha256 and the word list's sha256 to the lock)
- Test: `evidence/tests/test_plan.py`

**Interfaces:**
- Produces:
  - `WordList(things: dict[str, list[str]], cues: list[str], written_by: str, ontology_names: dict[str, list[str]])`; `things` maps a thing id to its names (20–50 by the LLM, plus ontology names kept apart in `ontology_names`).
  - `Decision(id: str, type: Literal["must_match", "counts_as", "threshold", "include"], value: Any, reason: str, flagged: bool = False, flag_reason: str | None = None, confirmed_by: str | None = None, confirmed_at: str | None = None)`
  - `EvidenceLine(id: str, question: str, query: str, template: str | None, removable: bool = True)`; the oversell line has `removable=False`.
  - `Plan(question: str, field: Literal["cs", "medicine", "materials", "other"], lines: list[EvidenceLine], main_rule: str, words: WordList, decisions: list[Decision], clarifications: list[dict[str, str]])`
  - `Plan.ready() -> bool` (every decision confirmed); `Plan.sha256` (canonical JSON digest); `load_plan(path) -> Plan`; `write_plan(plan, path)`.
  - `lockfile.lock(...)` gains `plan_sha256: str | None` and `words_sha256: str | None`; both `None` for a protocol run without a plan (old runs lock as before).

- [ ] **Step 1: Failing tests**: `test_ready_needs_every_decision_confirmed`, `test_plan_roundtrip_same_sha`, `test_old_protocol_lock_unchanged` (lock an existing RAG protocol; JSON equals the committed fixture byte for byte).
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement** `evidence/plan.py`; extend `lockfile.lock` with keyword-only `plan=None`.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(plan): plan file, decisions, word list, lock fields`

### Task 0.4: DSPy step wrapper on the recorded model gateway

**Files:**
- Modify: `pyproject.toml` (`uv add dspy pdfplumber`; pin the versions uv resolves)
- Create: `modelcall/dspy_lm.py`, `evidence/steps/__init__.py`
- Test: `modelcall/tests/test_dspy_lm.py`, `evidence/tests/test_steps.py`

**Interfaces:**
- Produces:
  - `modelcall.dspy_lm.RecordedLM(alias: str, ask: Callable[[str], str])`: a `dspy.BaseLM` whose every call goes through the run's recorder (`ask`), so DSPy calls are cached and replayed like `modelcall.ask`.
  - `evidence.steps.Step(signature: type[dspy.Signature], name: str)`: `__call__(**inputs) -> dspy.Prediction`; loads tuned instructions from `evidence/steps/tuned/<name>.json` when present (Task 8.2 writes them), else the signature's docstring.
  - `evidence.steps.configure(lm: RecordedLM) -> None`.
- [ ] **Step 1: Failing tests**: a fake `ask` returning a fixed JSON; `Step(EchoSig, "echo")(text="x")` returns it; the fake saw exactly one call; a second identical call is served from the recorder cache (call count stays 1).
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**; DSPy adapter = `dspy.JSONAdapter` (typed outputs).
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(steps): DSPy steps on the recorded gateway`

### Task 0.5: Engine seams

**Files:**
- Create: `evidence/stages.py`
- Modify: `evidence/engine.py` (call the seams; no behaviour change when none is registered)
- Test: `evidence/tests/test_stages.py`

**Interfaces:**
- Produces:
  - `stages.register(name: str, at: Literal["before_extract", "after_type", "after_document", "after_run"], fn) -> None`, ordered by registration.
  - `before_extract(doc: DocState, plan: Plan | None) -> None` (W3 experiment map, W1 word config); `after_type(doc: DocState, etype: str, merged: list[Item]) -> list[Item]` (W1 re-check); `after_document(doc: DocState) -> list[Item]` (W5 claims/links); `after_run(run: RunDir, plan: Plan | None) -> dict[str, Any]` (W4 graph + query, W2 ontology report); each `after_run` result is written as `<name>.json` in the run dir and hashed into `run.json` outputs.
  - `Settings.plan: Path | None = None` in `engine.Settings`.
- [ ] **Step 1: Failing tests**: `test_no_stages_run_is_byte_identical` (replay a committed EV2 run fixture with no stages; every output sha256 equal); `test_after_run_output_is_hashed` (a stage returning `{"x": 1}` gives `demo.json` listed in `run.json` outputs).
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement** the registry and the four calls in `Execution`.
- [ ] **Step 4: Run, expect PASS**, plus `uv run pytest evidence/tests -q` green.
- [ ] **Step 5: Commit** `feat(engine): stage seams`; merge `gen/w0` into `main`; cut the seven stream branches.

---

## Wave 1, W1: LLM-written words, re-check, leak split

### Task 1.1: Word writer step

**Files:** Create `evidence/words/write.py`; Test `evidence/tests/test_words_write.py`

**Interfaces:**
- Consumes: `Step`, `WordList` (W0).
- Produces: `write_words(question: str, things: list[str], *, step: Step | None = None) -> WordList`. DSPy signature `WriteWords(question, thing -> names: list[str])`, called once per thing, plus `WriteCues(question -> cues: list[str])` for claim cue words ("we show", "outperforms", "we conclude"…). `written_by` = the pinned alias.

- [ ] **Step 1: Failing tests** with a fake LM: `test_names_kept_between_20_and_50` (a reply of 60 names is cut to 50, in reply order; a reply of 12 gets one retry asking for more, then kept with `short=True` recorded); `test_names_deduped_case_folded`; `test_writer_never_sees_papers` (the signature has no paper input; assert the inputs are exactly `question`, `thing`).
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(words): LLM word writer`

### Task 1.2: Words to screen and regex config

**Files:** Create `evidence/words/compile.py`; Test `evidence/tests/test_words_compile.py`

**Interfaces:**
- Consumes: `WordList`, `evidence.extractors.screen.term_pattern`, `terms.find_all` input format.
- Produces: `compile_words(words: WordList) -> dict[str, Any]` returning the same config keys `Pack.extractor_config` fills today (`conditions`, `metrics`, `screen_terms`, `claim_subject`, `claims` cue patterns), built from `things` + `ontology_names`. Registered at `before_extract` so a plan run overrides the pack words.

- [ ] **Step 1: Failing tests**: `test_word_boundaries` ("RAG" does not match "fRAGment"); `test_acronym_case` ("NLP" matched in capitals only, as `term_pattern` does); `test_ontology_names_included`; `test_same_config_keys_as_pack` (keys equal `Pack.extractor_config` keys for the rag pack).
- [ ] **Step 2–5:** run FAIL → implement → PASS → commit `feat(words): compile word list to extractor config`

### Task 1.3: Required LLM re-check of regex finds

**Files:** Create `evidence/extractors/recheck.py`; Test `evidence/tests/test_recheck.py`

**Interfaces:**
- Consumes: `after_type` seam, `Step`.
- Produces: `recheck(doc: DocState, etype: str, merged: list[Item]) -> list[Item]`. Groups the items found by `regex`/`model` kinds by paragraph; one DSPy call per paragraph (`Recheck(paragraph, items -> verdicts: list[keep|drop|relabel], new_label)`). Dropped items go to `Rejected` with reason `out_of_scope` and the model's reason; relabelled items keep their spans.
- Review Focus 1: when the compiled screen terms match nothing in a paper, the funnel passes the paper to `llm_screen` instead of skipping it (plan runs set `screen.on_fail` to `next`).

- [ ] **Step 1: Failing tests**: `test_one_call_per_paragraph` (5 items in 2 paragraphs → 2 calls); `test_drop_is_rejected_not_lost`; `test_llm_items_not_rechecked`; `test_no_screen_hit_goes_to_llm_screen`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(funnel): LLM re-check of regex finds, one paragraph per call`

### Task 1.4: Leak split in scoring

**Files:** Create `evaluation/leak.py`; Test `evaluation/tests/test_leak.py`

**Interfaces:**
- Consumes: `WordList` (from the run's locked plan), `evaluation.truth.GroundTruth`.
- Produces: `mark(truth: GroundTruth, words: WordList) -> dict[str, Literal["on the list", "unseen"]]` per fact id (a fact is "on the list" when its name, after `names.clean`, equals a cleaned list name); `split_scores(score_json, marks) -> {"on the list": prf, "unseen": prf}`. Refuses (ValueError) a corpus whose id does not start with `rag-claude-` (the Claude-written corpora).

- [ ] **Step 1–5:** tests `test_mark_uses_clean_names`, `test_split_counts_sum_to_total`, `test_refuses_non_claude_corpus` → implement → commit `feat(eval): on-the-list vs unseen split`

---

## Wave 1, W2: ontology

### Task 2.1: Field ontology loaders

**Files:** Create `evidence/ontology/__init__.py`, `evidence/ontology/sources.py`, `evidence/ontology/mesh.py`, `evidence/ontology/qudt.py`; data cache under `data/ontology/` (gitignored, sha256 pinned in `sources.py`); Test `evidence/tests/test_ontology_sources.py`

**Interfaces:**
- Produces: `load(field: str) -> rdflib.Graph | None` (`cs` → the CS-KG graph `reasoner.load_ontology` reads today; `medicine` → MeSH; every field also gets QUDT units; `other` → QUDT only); `other_names(graph, label) -> list[str]` (MeSH entry terms as `skos:altLabel`, CS-KG `rdfs:label`s); `fetch(name) -> Path` downloads the pinned file (MeSH descriptor XML of the current year from nlm.nih.gov; QUDT units ttl from qudt.org) and checks its sha256.
- [ ] **Step 1: Failing tests** on small committed fixtures (`evidence/tests/fixtures/mesh_mini.xml`, `qudt_mini.ttl`): `test_mesh_entry_terms` ("Myocardial Infarction" → includes "Heart Attack"); `test_qudt_unit_symbol` ("percent" ↔ "%"); `test_cs_field_uses_existing_ttl` (same triples as `reasoner.load_ontology` for the rag pack); `test_fetch_refuses_wrong_sha`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(ontology): MeSH, QUDT and CS-KG loaders`

### Task 2.2: Ontology names into the word list

**Files:** Create `evidence/ontology/names.py`; Test `evidence/tests/test_ontology_names.py`

**Interfaces:**
- Consumes: `load`, `other_names` (2.1), `WordList` (W0).
- Produces: `add_ontology_names(words: WordList, graph) -> WordList` filling `ontology_names` per thing (exact label match after `names.clean`, else none).
- [ ] **Step 1–5:** tests `test_adds_mesh_synonyms`, `test_no_graph_no_change` → implement → commit `feat(ontology): ontology names for the word list`

### Task 2.3: Never silent, LLM parents, LLM mini-tree

**Files:** Modify `evidence/reasoner.py`; Create `evidence/ontology/fill.py`; Test `evidence/tests/test_ontology_fill.py`

**Interfaces:**
- Consumes: `after_run` seam, `Step`.
- Produces: `report(graph, found_names: list[str]) -> {"tree": str | "reasoning off: no tree", "unplaced": int, "names": [...]}`; `propose_parents(unplaced: list[str], graph, question) -> list[tuple[name, parent]]` (DSPy `ProposeParent`; a parent must be an existing class label or another proposed name; triples get `ev:madeBy "llm"`); `mini_tree(found_names, question) -> rdflib.Graph` for a field without a tree, every triple `ev:madeBy "llm"`; `review(run, accepted: list[str], rejected: list[str])` writes `links_review.json`; synthesis rerun is W4's `rerun()`.
- [ ] **Step 1: Failing tests**: `test_no_tree_says_so` (Review Focus 2: field `other`, no QUDT match → `"reasoning off: no tree"`, run completes); `test_unplaced_counted`; `test_parent_must_exist`; `test_llm_links_marked_made_by_llm`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(ontology): report, LLM parents and mini tree`

---

## Wave 1, W3: reading real papers

### Task 3.1: Structured source ladder

**Files:** Modify `evidence/arxiv.py`; Create `evidence/sources/latex.py`, `evidence/sources/pmc.py`; Test `evidence/tests/test_sources.py`

**Interfaces:**
- Produces: `fetch_paper(ref) -> (markdown: str, source: Literal["latex", "pmc_xml", "html", "pdf"], reason: str)` trying arXiv LaTeX source (`https://arxiv.org/e-print/<id>`), PMC XML (`https://www.ncbi.nlm.nih.gov/research/pmc/oai…` or the PMC OA service), arXiv HTML, then Docling on the PDF. Tables become Markdown tables with exact cell text. Manifest keeps `source` and the fallback reason (as today).
- [ ] **Step 1: Failing tests** on committed fixtures (a small `.tex` with `tabular`, a small JATS XML with `<table-wrap>`): `test_latex_table_cells_exact`, `test_pmc_table_cells_exact`, `test_ladder_order_and_reason` (LaTeX fetch fails → HTML used, reason recorded).
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(sources): LaTeX and PMC XML before HTML and PDF`

### Task 3.2: Two table readers for PDFs

**Files:** Create `evidence/tables.py`; Test `evidence/tests/test_tables.py`

**Interfaces:**
- Produces: `read_tables(pdf: Path) -> list[Table]` where `Table(page: int, cells: list[list[str]], unsure: set[tuple[int, int]])`; Docling and pdfplumber both read each table; a cell where they disagree is in `unsure`; the Markdown writer appends `<!-- table unsure: r,c -->` and the value check marks values from those cells "table unsure".
- [ ] **Step 1: Failing tests**: `test_agree_no_unsure`; `test_disagree_marked_unsure`; `test_pdfplumber_empty_keeps_docling_unsure` (Review Focus 5: pdfplumber reads no table → Docling cells kept, all marked "table unsure").
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(tables): two readers, unsure cells`

### Task 3.3: Experiment map per paper

**Files:** Create `evidence/experiments.py`; Modify `evidence/rules.py` (`duplicates`); Test `evidence/tests/test_experiments.py`

**Interfaces:**
- Consumes: `Experiment` (W0), `before_extract` seam, `Step`.
- Produces: `map_experiments(doc_text: str, document: str) -> list[Experiment]` (DSPy `MapExperiments(paper -> experiments: [{label, setting}])`, each anchored to a quote; unanchored ones rejected); `attach(value_item: Item, experiments) -> str | None` (exp_id whose setting matches the value's links, else the nearest preceding experiment span); `rules.duplicates` keys on `(exp_id, canonical, treatment, control)`, falling back to today's key when a run has no experiment map (old runs unchanged).
- [ ] **Step 1: Failing tests**: `test_two_experiments_same_values_not_duplicates`; `test_old_run_duplicates_unchanged`; `test_unanchored_experiment_rejected`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(experiments): experiment map replaces the duplicate guess`

### Task 3.4: Value check against source

**Files:** Modify `evidence/checks.py` (one rule); Test `evidence/tests/test_checks_source.py`

**Interfaces:**
- Produces: rejected reason `not_found` for a value whose number is not in its span text or table cell; values from unsure cells are kept with `fields["table_unsure"] = True`.
- [ ] **Step 1–5:** tests `test_value_not_in_cell_dropped`, `test_unsure_value_kept_and_marked` → implement → commit `feat(checks): every value checked against its source`

### Task 3.5: Two generator difficulty settings

**Files:** Modify `synth/levels.py`, `synth/render_template.py`; Test `synth/tests/test_levels_new.py`

**Interfaces:**
- Produces: `LEVELS` gains `"multi_experiment"` (every experiment shown in prose and tables, like `complex`, at the `paraphrased` wording) and `"messy_tables"` (tables with merged header cells, units in headers, values with footnote marks). The generator stays RAG comparisons only.
- [ ] **Step 1–5:** tests `test_multi_experiment_lists_all_experiments`, `test_messy_table_values_parse_back` (`parse_value` recovers every written value), `test_existing_levels_unchanged` (same plan for a fixed seed) → implement → commit `feat(synth): multi_experiment and messy_tables levels`

---

## Wave 1, W4: records graph and SPARQL answers

### Task 4.1: Records to graph

**Files:** Create `evidence/kg/__init__.py`, `evidence/kg/build.py`; Test `evidence/tests/test_kg_build.py`

**Interfaces:**
- Consumes: `Item`, `Experiment`, `ClaimRecord`, `LinkRecord`, vocabulary (W0), field ontology graph (W2 interface `load(field)`; tests use a fixture graph).
- Produces: `build(papers, items: dict[str, list[Item]], roles: RoleMap, ontology: rdflib.Graph | None) -> pyoxigraph.Store`. Every value becomes an `ev:Value` in its `ev:Experiment` with `ev:setting_<field>` literals; any two values of the same experiment on the same metric become an `ev:Comparison` (`ev:a`, `ev:b`, `ev:delta`, `ev:better` by the metric's direction). Things are typed by ontology class when their cleaned name matches a label. `serialize(store) -> bytes` (sorted N-Quads, so the same records give the same file `records.nq`).
- [ ] **Step 1: Failing tests**: `test_same_records_same_bytes`; `test_comparison_edge_any_two_things` (three methods in one experiment → 3 comparisons); `test_no_comparison_across_experiments`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(kg): records graph with comparison edges`

### Task 4.2: Query runner and saved templates

**Files:** Create `evidence/kg/query.py`, `evidence/kg/templates/*.rq` (`effect`, `consistency`, `best`, `rank`, `inventory`, `list_for`, `count`, `chaining_path`, `builds_on`, `oversell`); Test `evidence/tests/test_kg_query.py`

**Interfaces:**
- Produces: `run_query(store, sparql: str, params: dict[str, Any]) -> Answer` with `Answer(rows: list[dict], empty: bool, reasons: list[dict])`; templates take `$must_match` (fields), `$counts_as` (values), `$threshold`, `$include`. `rank` orders across papers on (dataset X, metric Y) by value with the metric's direction (SciLead); `list_for` lists one type linked to another (SciREX "datasets used for task T"); `chaining_path` keeps steps A–B–C whose settings match on `$must_match`, returns per path the difference of differences, and labels "indirect" (paths agree) or "conflicting" (disagree by more than `$threshold`).
- Code fallback: a step SPARQL cannot express is a Python function in `evidence/kg/after.py` named in the template's header comment, called on the rows.
- [ ] **Step 1: Failing tests**: `test_rank_matches_leaderboard_fixture` (a 4-paper fixture); `test_list_for_task`; `test_chaining_conflicting`; `test_empty_answer_has_reasons` (Review Focus 3: a valid query with no rows → `empty=True`, `reasons` lists the unused records with their reason, no exception); `test_effect_template_equals_old_effect_answer` on a committed EV2 run (same direction counts as `synthesis.answer`).
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(kg): SPARQL runner and saved templates`

### Task 4.3: Decision reruns (sensitivity)

**Files:** Create `evidence/kg/sensitivity.py`; Test `evidence/tests/test_sensitivity.py`

**Interfaces:**
- Consumes: `Decision` (W0), `run_query`.
- Produces: `alternatives(decision: Decision, fields: list[str]) -> list[tuple[Literal["strict", "main", "loose"], Any]]` (must-match ±1 field; counts-as ±1 value; threshold 0, main, 2× main); `rerun(store, line: EvidenceLine, decisions) -> Sensitivity` reruns one decision at a time; `label(results, min_count: int = 3) -> str` → "solid" | "same direction" | `f"depends on {field}"` | "too few to tell" (`min_count` = 3 is our call; the spec says "a minimum count"); only flipping settings are listed; the optional split table by condition field (spec item 6) is left out of this plan (exploratory, unscored); records used only under a loose setting get `indirect on: <field>`.
- [ ] **Step 1: Failing tests**: `test_threshold_alternatives_are_0_main_double`; `test_rag_example_depends_on_model_size` (fixture: 9 of 12 favour RAG; dropping models under 7B gives 5 of 9 → "depends on model size"); `test_best_author_example` (Chen 12 vs Rossi 9 main; counting papers Rossi 7 vs Chen 5 → "depends on what best means" shown as `depends on counts_as`); `test_too_few`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(kg): decision reruns and labels`

### Task 4.4: Query on the answer key (error split)

**Files:** Create `evidence/kg/truthgraph.py`; Test `evaluation/tests/test_truthgraph.py`

**Interfaces:**
- Produces: `truth_store(truth: GroundTruth | RealQuestion) -> pyoxigraph.Store` (a `RealQuestion`'s `gold`, Task 6.1) (answer-key records in the same vocabulary); `split(ours: Answer, gold_on_truth: Answer, expected) -> Literal["right", "synthesis error", "extraction error"]` (wrong on truth = synthesis; right on truth but wrong on ours = extraction).
- [ ] **Step 1–5:** tests `test_wrong_query_is_synthesis_error`, `test_missing_record_is_extraction_error` → implement → commit `feat(kg): answer-key graph and error split`

---

## Wave 1, W5: open claims and links

### Task 5.1: Open claim records

**Files:** Create `evidence/claims.py`; Test `evidence/tests/test_claims_open.py`

**Interfaces:**
- Consumes: compiled `claim_subject` + cue patterns (W1 interface `compile_words`; tests pass a dict), `ClaimRecord`, `after_document` seam, `Step`.
- Produces: `find_claims(doc_text, document, config) -> list[ClaimRecord]`: regex finds candidate sentences (subject word + cue word in one sentence); DSPy `ReadClaim(sentence -> subject, relation, object, setting, strength, direction?)` confirms each; `direction` is set only for comparison claims and is one of improves / worsens / no_effect. `group_relations(verbs: list[str]) -> dict[str, str]`: after all papers are read, one DSPy call `GroupRelations(verbs -> groups)` puts the run's distinct verbs into groups (e.g. raises, boosts, improves → `increases`), recorded like every call; a verb it cannot place gets its own group `other: <verb>` and is shown in the answer, never dropped. The grouping is a counts-as decision: the answer shows "grouped: raises, boosts → increases", and the reruns (Task 4.3) also run with groups off (raw verbs only).
- [ ] **Step 1: Failing tests**: `test_non_comparison_claim_kept` ("our dataset is the largest" → relation `is the largest`, direction None); `test_hedged` ("suggests" → hedged); `test_comparison_maps_direction` ("RAG reduces hallucination" → improves for a lower-is-better metric); `test_old_rag_claims_same_labels` (on a committed EV2 corpus, labels equal the old `claims` patterns' labels for ≥ 95% of old claims; the rest listed); `test_raises_and_boosts_grouped` ("RAG raises accuracy" and "RAG boosts accuracy" → same `relation_group`, the oversell query counts 2); `test_unplaced_verb_shown_as_other`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(claims): open claim records`

### Task 5.2: Builds-on through OpenAlex

**Files:** Create `evidence/openalex.py`; Test `evidence/tests/test_openalex.py`

**Interfaces:**
- Produces: `resolve(cited_text: str, doi: str | None, arxiv_id: str | None, run_docs: dict[str, str]) -> LinkRecord` (OpenAlex `/works/doi:…` or search by title; recorded via the run's recorder like a model call; `outside_set=True` when the work is not a paper of the run); `references(doc_id) -> list[str]` (OpenAlex `referenced_works`, for scoring). Open relation from `ReadLink(sentence -> relation, object)` (DSPy).
- [ ] **Step 1: Failing tests** with recorded HTTP fixtures: `test_doi_resolves_to_run_doc`; `test_outside_set_kept`; `test_offline_replay_uses_record`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(links): builds-on via OpenAlex, outside the set kept`

---

## Wave 1, W6: real labelled sets as whole-run questions

### Task 6.1: Shared whole-run scoring

**Files:** Create `evaluation/wholerun.py`; Test `evaluation/tests/test_wholerun.py`

**Interfaces:**
- Produces: `RealQuestion(id, question, field, corpus_dir, gold: dict, kind: Literal["rank", "list", "compare", "claims"])`; `score(answer: Answer, q: RealQuestion) -> dict` with rank → `top1` (0/1) and `kendall_tau` (`scipy.stats.kendalltau` over the items both orders contain), list → precision/recall/F1 (names compared by `names.clean` + run name groups), compare → direction agreement per comparison and overall.
- [ ] **Step 1–5:** tests `test_rank_top1_and_tau`, `test_list_prf`, `test_compare_direction` → implement → commit `feat(eval): whole-run scoring for real questions`

### Task 6.2: SciLead and SciREX questions

**Files:** Modify `evaluation/realpapers/scilead.py`, `evaluation/realpapers/scirex.py`; Test `evaluation/tests/test_real_questions_cs.py`

**Interfaces:**
- Produces: `scilead.questions(src) -> list[RealQuestion]`: one per leaderboard (27), "Which method is best on <dataset> by <metric>?", gold = the board's order (direction from `domains/ml/metrics.yaml`); `scirex.questions(src) -> list[RealQuestion]`: one per (task) with ≥ 2 linked datasets, "Which datasets are used for <task>?", gold = labelled list. Field `cs`.
- [ ] **Step 1–5:** tests on the committed small fixtures: `test_scilead_27_boards` (count on the real file when present, skip otherwise; fixture count on the fixture), `test_scirex_task_list` → implement → commit `feat(real): SciLead and SciREX whole-run questions`

### Task 6.3: CochraneForest

**Files:** Create `evaluation/realpapers/cochraneforest.py`; Test `evaluation/tests/test_cochraneforest.py`

**Interfaces:**
- Produces: `check_release(src) -> {"licence": str, "released": bool}` (step 1 of the converter; stop with a clear message when not released or not allowed); `to_corpus(src, out) -> Path` (study full texts as papers, manifest as the engine reads); `questions(src) -> list[RealQuestion]` (each forest plot: its research question; gold = per-study direction and the review's conclusion; kind `compare`, plus kind `claims` scoring the run's claim records against the conclusions). Field `medicine`.
- [ ] **Step 1–5:** fixture with 1 plot, 2 studies: `test_question_and_gold`, `test_refuses_unreleased` → implement → commit `feat(real): CochraneForest questions`

### Task 6.4: SOFC-Exp and MeasEval

**Files:** Create `evaluation/realpapers/sofc.py`, `evaluation/realpapers/measeval.py`; Test `evaluation/tests/test_sofc_measeval.py`

**Interfaces:**
- Produces: `sofc.label_check(src) -> {"complete": bool, "why": str}` (step 1: are values linked to a material and a measure for ranking? if not, only the experiment-frame check below); `sofc.questions(src)` ("Which material gives the highest <Z>?", field `materials`) when complete; `sofc.experiment_frames(src)` → gold experiments for scoring W3's experiment map (`evaluation/realpapers/sofc.py score_experiments(run, src)`); `measeval.values_check(run, src)` scores values, units and measured entity (QUDT units); `measeval.fields(src)` reports which fields its papers come from (the spec marks this unverified).
- [ ] **Step 1–5:** tests on fixtures: `test_sofc_label_check`, `test_experiment_frames_score`, `test_measeval_units` → implement → commit `feat(real): SOFC-Exp and MeasEval checks`

### Task 6.5: RAG baseline on the real questions

**Files:** Create `evaluation/baselines/real.py`; Test `evaluation/tests/test_baseline_real.py`

**Interfaces:**
- Consumes: `RealQuestion`, `wholerun.score` (Task 6.1); `passages`, `retrieve`, `CitedAnswer`, `keep_citations` from `evaluation/baselines/rag.py` (unchanged).
- Produces: `rag_real(q: RealQuestion, *, model, mode: Literal["global", "per_paper"] = "global") -> Answer`: the existing BM25 retrieve-then-answer on `q.corpus_dir`, then one mapping call per kind into the shape `wholerun.score` reads (rank → ordered names; list → names; compare → direction per study; claims → claim list). Same pinned model, same papers, same question text as the engine; cached and recorded like `rag_baseline`; an empty answer is a valid answer.
- [ ] **Step 1: Failing tests**: `test_rank_answer_scored_like_engine` (fake model reply → same `score` keys as an engine answer); `test_same_papers_as_engine` (the baseline refuses a corpus dir that differs from the engine run's); `test_empty_answer_valid`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(eval): RAG baseline on real questions`

### Task 6.6: Off-template questions (generality check)

**Files:** Create `evaluation/offtemplate/questions.yaml`, `evaluation/offtemplate/reference/*.rq`, `evaluation/offtemplate/check.py`; Test `evaluation/tests/test_offtemplate.py`

**Interfaces:**
- Consumes: `run_query` (W4 Task 4.2), `truth_store` (Task 4.4), `EvidenceLine.template` (None = fresh query).
- Produces: 12 questions over the Claude-written synthetic corpora whose shape fits none of the saved templates (e.g. "Which papers report a dataset no other paper uses?", "Does the gap between methods shrink on larger datasets?"), each with a hand-written reference query; gold = the reference query run on the answer key's records (`truth_store`). The questions and reference queries are committed before any planner output is seen (commit date checked). `check(run, q) -> {"fresh": bool, "match": bool}`: the plan's answer equals the gold answer.
- [ ] **Step 1: Failing tests**: `test_reference_queries_parse_and_run` (all 12 on a fixture truth store); `test_no_question_fits_a_template` (each reference query differs from every saved template); `test_match_when_rows_equal`.
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(eval): off-template generality check`

---

## Wave 1, W7: planner and one-page UI

### Task 7.1: Planner steps

**Files:** Create `evidence/planner/__init__.py`, `evidence/planner/plan.py`; Test `evidence/tests/test_planner.py`

**Interfaces:**
- Consumes: `Plan`, `Decision`, `EvidenceLine`, `Step` (W0); W1 `write_words` and W4 template names by import of their modules' public names (tests use fakes).
- Produces: `clarify(question) -> list[{question, options}]` (0–2 multiple-choice questions, only when ambiguous); `propose(question, clarifications) -> Plan`: "what would prove it?" evidence lines (each a SPARQL query started from a saved template), default decisions of the four types with reasons, the default main-answer rule, the field (cs/medicine/materials/other), the word list; every plan with an effect or consistency line gets the oversell line (`removable=False`); `critic(plan) -> Plan` flags 1–2 decisions it doubts (`flagged=True`, `flag_reason`), from a separate DSPy step that does not see the planner's reasoning; `confirm_all(plan, who) -> Plan` confirms every decision, flagged ones included.
- [ ] **Step 1: Failing tests**: `test_oversell_line_added_and_not_removable`; `test_critic_flags_one_or_two` (fake replies of 0 and 4 flags → refused and retried once, then clamped to 2 with the rest dropped and recorded); `test_confirm_all_confirms_flagged`; `test_run_disabled_until_ready` (`Plan.ready()` False while one decision is open); `test_query_must_parse` (a reply whose SPARQL does not parse gets one repair call with the parser error; still failing → the line is shown "could not plan").
- [ ] **Step 2–5:** FAIL → implement → PASS → commit `feat(planner): plan, decisions, critic flags`

### Task 7.2: Plan API

**Files:** Create `webapp/evplan.py`; Modify `webapp/app.py` (mount router); Test `webapp/tests/test_evplan.py`

**Interfaces:**
- Produces: `POST /api/ev/plan` {question} → Plan JSON + clarifications; `POST /api/ev/plan/{id}/clarify`; `POST /api/ev/plan/{id}/decision/{did}` {confirm | change: value}; `POST /api/ev/plan/{id}/confirm-all`; `DELETE /api/ev/plan/{id}/line/{lid}` (refused for the oversell line); `POST /api/ev/plan/{id}/run` (409 until `ready()`); after the run `POST /api/ev/run/{rid}/links` {accepted, rejected} → W2 `review` + W4 `rerun`. The protocol record (decisions, who, when, clarifications) is saved with the frozen plan.
- [ ] **Step 1–5:** FastAPI TestClient tests per route, fakes for the planner → implement → commit `feat(webapp): plan API`

### Task 7.3: One-page planner view and independent lines

**Files:** Create `webapp/web/src/routes/plan/PlanPage.tsx`, `DecisionsPanel.tsx`, `LineCard.tsx`; Test `webapp/web/src/routes/plan/*.test.tsx`; Modify `webapp/web/src/app/routes.tsx`

**Interfaces:**
- Consumes: Task 7.2 routes.
- Produces: the page of the "Best Author Run" mockup (https://claude.ai/artifact/2GQWhcw9wFxRboUzbdje2T): question box + Plan; evidence lines with × (none on oversell) and "how?" (steps as sentences, closed by default); decisions panel with Confirm / Change per decision, flagged ones highlighted with their reason, "Confirm all"; Run disabled until all confirmed; results in place ("No evidence found" when empty; "failed: <reason>" for a crashed line); answer with "missing: <line>" when a line failed, the main-answer rule as one line with "change", and the reruns table (only flipping settings).
- Engine side (Review Focus 4): each line's query runs in its own try block in W4's `after_run`; tested in `evidence/tests/test_lines_independent.py` (a line whose query raises → other lines answered, that line `failed`, answer labelled `missing: <line>`).
- [ ] **Step 1–5:** component tests (vitest) for disabled Run, flagged highlight, failed line text; engine test above → implement → commit `feat(webapp): one-page planner`

---

## Wave 2: integration, tuning, end-to-end

### Task 8.1: Wire the stages into a plan run

**Files:** Modify `evidence/engine.py`, `evidence/cli.py`; Test `evidence/tests/test_plan_run.py`

**Interfaces:**
- Produces: `evidence run --plan plan.json --corpus <dir> --out <dir>`: registers W1 (`compile_words` at `before_extract`, `recheck` at `after_type`), W3 (`map_experiments` at `before_extract`), W5 (`find_claims`, links at `after_document`), W2 (`report`, parents at `after_run`), W4 (`build`, every line's `run_query`, `rerun` at `after_run`); writes `records.nq`, `answer.json` (lines, main answer, labels, reruns), `ontology.json`; seals as today; replay is byte-identical.
- [ ] **Step 1–5:** tests `test_plan_run_end_to_end_fake_lm` (EV2 small corpus, recorded fake LM), `test_plan_run_replay_identical`, `test_protocol_run_unchanged` → implement → commit `feat(engine): plan runs`

### Task 8.2: DSPy tuning

**Files:** Create `evidence/steps/tune.py`; Test `evidence/tests/test_tune.py`

**Interfaces:**
- Produces: `evidence tune <step> --train <corpora> --test <corpora> --optimizer gepa|miprov2` writes `evidence/steps/tuned/<step>.json` and a report with train and test scores. Refuses overlapping train and test corpus ids. Metric per step: words → recall of answer-key names (unseen names only from the test side); recheck → item precision; experiments → SOFC-Exp frames + synthetic `multi_experiment` truth; claims → synthetic claim labels; planner query → whole-run score on synthetic questions.
- [ ] **Step 1–5:** tests `test_refuses_overlap`, `test_writes_tuned_file` (tiny fake optimizer) → implement → commit `feat(steps): DSPy tuning command`

### Task 8.3: Evaluation commands

**Files:** Modify `evaluation/cli.py`; Test `evaluation/tests/test_cli_wholerun.py`

**Interfaces:**
- Produces: `evaluate wholerun --set scilead|scirex|cochraneforest|sofc --src <dir> --runs <dir>` (W6 questions → plan runs → `wholerun.score` + `truthgraph.split` per question) and `evaluate leak --run <dir> --corpus <dir>` (W1 split). Links: chaining answers scored against the synthetic truth network (as `evaluation/score.py` does for `chaining` today); builds-on scored by recall of OpenAlex `references` (W5). Reasoning on/off: every whole-run question is scored twice (`--reasoning on|off`), both rows in the report. Baseline: `--system engine|rag|both` (default both); the report puts the engine and RAG (Task 6.5, global and per_paper) side by side per question with wins, losses and ties, and the paired test from `evaluation/stats.py`; no row assumes the engine wins. Generality: `evaluate offtemplate --runs <dir>` (Task 6.6) reports fresh-query match rate, and `evaluate wholerun` reports how many real questions the planner answered with a saved template vs a fresh query.
- [ ] **Step 1–5:** tests on fixtures → implement → commit `feat(eval): wholerun and leak commands`

### Task 8.4: Runbook for the cluster run

**Files:** Create `docs/runbook-general-system.md`

- [ ] **Step 1:** Write the hand-off for Codex on Slurm (memory rule: Claude builds, Codex tests): fetch sources (MeSH, QUDT, the four real sets after their licence checks), tune each step on synthetic train corpora, run every real set and the Claude-written synthetic corpora at every level including `multi_experiment` and `messy_tables`, copy every run folder back.
- [ ] **Step 2:** Dry-run every command in it locally on the fixtures; each exits 0.
- [ ] **Step 3: Commit** `docs: general-system runbook`
