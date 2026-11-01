# EV4 Plan 2: Drug trials (generator, network, comparisons, chaining, new shapes, pack builder) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a second topic, drug trials, without touching extractor, engine or synthesis code for topic reasons. This plan covers:
- the generator reads a per-topic `generator.yaml`;
- the truth holds a network of comparisons, builds-on links, planted limitations and name variants;
- the engine builds comparisons from pairs inside a study, chains them, and answers two new shapes (limitations, builds-on);
- the evaluation scores all of it, baselines included;
- `domains/drugtrials` is proposed by a pack builder agent that reads through a corpus tool server, or by the D34 fallback helper, then frozen.

**Architecture:**
- **Generator recipe.** `synth/recipe.py` loads `domains/<name>/generator.yaml` into a frozen `Recipe`. Everything `synth/vocab.py` held now comes from it.
- **Truth.** `synth/network.py` draws a latent ranking of things per population. Studies sample edges of the recipe's network from that ranking, so every direct comparison and every allowed chain has a known answer.
- **Engine.** Answering becomes three steps, each with its own file (D26): `evidence/comparisons.py` writes `comparisons.json`, the kind writes `answer.json`, and `evidence/kinds/chaining.py` follows comparisons through `NameGroups`.
- **New kinds.** `limitations` and `builds_on` are registered like the four existing kinds and address the new pack roles `limitation` and `dependency`.
- **Pack builder.** It lives in its own folder `packbuilder/` with its own command (D29): an MCP corpus server (`mcp` SDK, FastMCP, stdio), a pydantic-ai agent that uses it, the D34 helper, and `freeze`.

**Tech Stack:** Python 3.13, pydantic, pyyaml, pydantic-ai 2.55.0 (`[mcp]` extra adds the `mcp` SDK, as the old harness used `mcp>=1.0,<2.0`), `rank_bm25` 0.2.2 (already a dependency), pytest via `uv run pytest`. Model calls go through `modelcall.ask` and exchange models (`modelcall/exchange.py`).

**Spec:** `docs/superpowers/specs/2026-11-01-ev4-general-evidence-system-design.md` (§6.2 "Comparisons are built, not extracted", §6.4, §6.5, §6.9 incl. D39, §6.10, §6.11 incl. "Who drafts what", §6.18, §7 steps 4-7; decisions D5, D6, D7, D11, D12, D14, D29, D34, D37, D39, D43). This is plan 2 of 3. It builds on plan 1 (`docs/superpowers/plans/2026-11-01-ev4-plan1-foundation.md`) and uses its Shared interfaces under their exact names: `load_pack`, `Pack`, `Role`, `RoleMap`, `protocol_path`, `questions_path`, `read_numbers`, `NameGroups.group_of`, `CHECKED_DIRS`.

## Global Constraints

- **Branch and approval:** `ev4/drug-trials` from `ev4/foundation`. Nothing is merged, tagged or pushed without Aditya's go. `packbuilder freeze` prints the tag command and never runs it.
- **Drug-trial outcome (spec §6.9):** "Outcome: response rate reported as counts per arm ("41 of 120 patients") and as percentages; units are fraction and percent only. Population is a context type."
- **D39, who writes `generator.yaml`:**
  - "drafted by the topic builder from 5-10 real papers of the topic (RAGEval's idea), not written by hand. Generated things get invented names, so no model answers from memory."
  - "The helper that writes `words.yaml` never sees `generator.yaml`, and each draft is logged separately in `provenance.json`."
  - "Before a full corpus: a 5-paper trial must pass the fidelity check, and a blind reader must find the planted values. Aditya looks over the draft once (about 10 minutes); then it is frozen under a tag."
- **Three paper sets stay apart (spec §6.11):**
  1. `generator.yaml` is drafted from 5-10 real papers fetched for that purpose.
  2. `words.yaml` comes from the synthetic scored corpus only.
  3. The real-paper test sets (Yun et al., SciLead, SciREX) are read by neither helper.
- **Chaining (spec §6.10):** "Allowed only when both use the same metric, and the same dataset or population when the papers name it (D6). The answer marks it "inferred through B, not tested directly", lists the studies it rests on, and never presents it as a direct result."
- **Builds-on (spec §6.11):** "A copied result counts once, at its original study." "Old presets and corpora unchanged."
- **Corpus tool server (spec §6.5):** it "reads only `manifest.json` and listed paper files, never `ground_truth.json` (a test)."
- **Pack builder (spec §6.4):** "**never** `ground_truth.json` or any gold."
- **Where things are scored (D43):** chaining, limitations and builds-on are scored on drug trials only. No new RAG corpus.
- **Models:**
  - Synthetic papers: Claude Haiku writes (`exchange:claude-haiku-5-5`) and Claude Sonnet verifies (`exchange:claude-sonnet-5-5`), as in `docs/claude-writer.md:20-38`.
  - Drafting helper, pack builder and D34 helper: Claude through exchange models. Each call is cached and its log committed.
  - "Same model for all systems"; no change to `llm-setup`; "No embeddings" (BM25 and regex only).
- **D36:** RAG numbers, extractor ids and the `synth/examples` rebuild may change. The committed `synth/examples/rag-demo-*` and `tests/EV2/corpora/*` stay on disk unchanged, checked by sha256.
- **Prompts** follow `docs/prompt-writing.md`: atomic tasks, explicit input and output, deterministic validation, generation separate from verification.
- **Every task ends with** `uv run pytest synth evaluation evidence packbuilder -q` passing, apart from the known failures in docs/STATE.md:186.
- **Test style:** copy synth/tests/test_truth.py:1-40 (docstring, `from __future__ import annotations`, `test_<plain_sentence>()`). Scripted models use `evaluation/tests/helpers.py:16` `Scripted`. Corpus guards use `guard_corpus` (:37).

## Review Focus

1. **A chain across contexts must be refused, and a chain through a renamed B must not.** If study 1 compares A and B in adults and study 2 compares B and C in children, the answer is refused with reason `context_differs`. If study 2 calls B "drug-B" or by its code name, the chain is still found. → Task 9 tests `test_chain_refused_across_populations`, `test_chain_through_name_variant`.
2. **A copied result is not counted twice.** A study that reports "as reported by Halvorsen et al." reuses an earlier study's placebo value. That value must not count again in effect, best, chaining or inventory. → Task 8 test `test_copied_control_counts_once_at_origin`.
3. **The corpus server must refuse every path out of `papers/`.** This includes `read_paper("../ground_truth.json")`, a manifest that lists `ground_truth.json`, and a `grep` whose pattern matches gold text. All are refused before any file is opened. → Task 15 test `test_server_never_opens_gold`.
4. **The drafting helper must not see held-out papers or keep real names.** Given a held-out paper (Yun et al. list) it refuses. A drafted recipe whose thing names occur in a source paper is refused (invented names, D39). → Task 3 tests `test_heldout_paper_refused`, `test_real_drug_name_refused`.
5. **Count values are exact.** A truth value is exactly k/n with integer k and arm size n. Two arms of different sizes still render and parse back within 0.005. "0 of 120" and a k above n are never drawn. → Task 4 test `test_values_are_exact_counts_over_arm_size`.

## Shared interfaces (plan 3 relies on these)

```python
# synth/recipe.py
class NameForms(Strict): label: str; synonym: str; description: str; code: str | None = None
class SideSpec(Strict): role: str; names: list[NameForms]
class MetricSpec(Strict): canonical: str; forms: list[tuple[str, str, str]]; higher_is_better: bool
    unit: Literal["fraction", "seconds"]; range: tuple[float, float]; pair_range: tuple[float, float] | None = None
class Reporting(Strict): formats: list[Literal["pct","frac","count","k_of_n","cell_pct","cell_raw","relative"]]
    count_base: int | None; arm_size: tuple[int, int] | None; allowed_numbers: list[str]
class Network(Strict): things: list[str]; reference: str; edges: list[tuple[str, str]]; contexts: list[str]
class BuildsOn(Strict): share: float; reuses: dict[Literal["method","dataset","result"], float]; phrases: list[str]
class Limitations(Strict): categories: dict[str, list[str]]; per_study: tuple[int, int]
class NameVariants(Strict): share: float; kinds: list[Literal["spelling","code_name","hereafter"]]
class Recipe(Strict): domain: str; question: str; context: Literal["dataset","population"]; sides: dict[str, SideSpec]
    others: list[NameForms]; question_metrics: list[MetricSpec]; other_metrics: list[MetricSpec]; contexts: list[str]
    effects: dict[str, tuple[float, float]]; reporting: Reporting; text: Text; network: Network | None
    builds_on: BuildsOn | None; limitations: Limitations | None; name_variants: NameVariants | None; sha256: str
def load_recipe(domain: str, root: Path = DOMAINS) -> Recipe
# synth CLI
#   synth draft  --domain D --papers DIR --model M [--exchange DIR]   -> domains/D/generator.yaml (+ provenance.json "generator")
#   synth trial  --domain D --model M --verify-model V                -> domains/D/trial.json
#   synth build  --domain D [--preset plain|builds_on] ...             (refuses without a passing trial.json for llm renderer)
# evidence/pack.py (additions)
class Role(StrEnum): ...; LIMITATION="limitation"; DEPENDENCY="dependency"; STUDY_LABEL="study_label"
class TypeDecl(Strict): ...; context_field: str | None = None
# evidence/comparisons.py
@dataclass(frozen=True) class Comparison: id: str; document: str; a: str; b: str; metric: str; context: str | None
    a_value: float; b_value: float; direction: Direction; delta: float; items: tuple[str, ...]; copied_from: str | None
def build_comparisons(document: str, items: list[Item], roles: RoleMap, groups: NameGroups, *,
                      higher_is_better: Callable[[str], bool], min_effect: float, prefer: Sequence[str]) -> list[Comparison]
# run file: comparisons.json  {"comparisons": [Comparison...], "copied": [...]}
# evidence/protocol.py
Kind = Literal["effect", "inventory", "consistency", "best", "chaining", "limitations", "builds_on"]
class Chaining(Strict): source: str; target: str; metric: QuestionMetric; min_effect: float; max_hops: int = 2
class LimitationsQ(Strict): thing: str | None = None
class BuildsOnQ(Strict): thing: str | None = None
# evidence/kinds/{chaining,limitations,builds_on}.py  (same four functions as every kind)
CHAIN_REASONS = ("direct_comparison", "no_path", "metric_differs", "context_differs", "mixed_directions", "paths_disagree")
# evaluation/baselines/prompts/map-{effect-v2,chaining-v1,limitations-v1,builds-on-v1}.md
# packbuilder/ (command `packbuilder`)
def create_server(corpus: Path) -> FastMCP          # tools: list_papers, read_paper, read_section, search, grep, tables
#   packbuilder serve   --corpus DIR                  (stdio)
#   packbuilder propose --corpus DIR --name N --model M      -> domains/N/{pack.yaml,words.yaml,provenance.json}
#   packbuilder helper  --corpus DIR --name N --model M      (D34 fallback)
#   packbuilder freeze  domains/N                            -> domains/N/FROZEN.json, prints the git tag command
# no-topic-words test
CHECKED_DIRS = ["evidence", "agent", "synth", "evaluation", "packbuilder"]
```

`ground_truth.json` gains these keys. All are optional, so old corpora load unchanged:
- top level: `types` (evidence type → `{list: <study key>, main_role: <placement role>}`) and `network` (`{things, comparisons, chains}`);
- per study: `population`, `limitations`, `dependencies` and `label` (author-year);
- per condition: `kind` and `variants`.

---

### Task 1: Generator recipe format and `domains/rag/generator.yaml`

**Files:**
- Create: `synth/recipe.py`, `domains/rag/generator.yaml`, `synth/tests/test_recipe.py`.
- Modify: `domains/rag/provenance.json` (add `"generator": {"source": "hand-moved from synth/vocab.py and synth/truth.py at tag ev3b-code"}`).

**Interfaces:**
- Consumes: `evidence.pack.DOMAINS`, `protocol.Strict`.
- Produces: the `Recipe` family and `load_recipe` (Shared interfaces). `Recipe.sha256` is the sha256 of the LF-normalised `generator.yaml`.

What `domains/rag/generator.yaml` holds, copied verbatim:

| Recipe key | Source |
|---|---|
| `question` | vocab.py:10 |
| `sides.baseline` | `BASELINES` :13 |
| `sides.rag` | `RAGS` :23 |
| codes | `CODES` :48 → `NameForms.code` per side |
| `others` | `OTHERS` :33 (codes from `OTHER_CODES` :49) |
| `question_metrics` | `QUESTION_METRICS` :53 with `pair_range` (0.35, 0.80) or (0.10, 0.45) from truth.py:256, `range` (0.30, 0.80) or (0.08, 0.50) from :276 |
| `other_metrics` | `OTHER_METRICS` :66; fraction range (0.10, 0.55) :274; latency range (0.40, 3.50) :269-272 |
| `contexts` | `DATASETS` :72 |
| `context` | `dataset` |
| `effects` | `{supports: [0.03, 0.15], contradicts: [0.03, 0.10], large: [0.30, 0.45]}` (truth.py:56, :240-242) |
| `reporting` | `{formats: [pct, frac, count, cell_pct, cell_raw, relative], count_base: 1000, arm_size: null, allowed_numbers: ['\b1,000 questions\b']}` (fidelity.py:28, levels.py:103) |
| `text` | `CLAIMS` :76, `TITLES`…`CONCLUSION` :97-145, `IRRELEVANT` :154, the hard-mode words :248-253, `prompt_words` (the RAG wording of render-v2.txt rules 7-8 and statements-v1.txt rule 7), `blind_examples` (blind-v2.txt examples) |
| `network`, `builds_on`, `limitations`, `name_variants` | `null` |

- [ ] **Step 1: Write the failing tests**

```python
def test_rag_recipe_holds_the_old_vocabulary():
    r = load_recipe("rag")
    assert r.sides["baseline"].names[0].label == "closed-book model"
    assert r.sides["rag"].names[0].code == "R" and r.contexts[0] == "OpenFactQA"
    assert r.question_metrics[0].pair_range == (0.35, 0.80) and r.effects["large"] == (0.30, 0.45)
    assert r.reporting.count_base == 1000 and r.network is None

def test_recipe_digit_rule_is_checked(tmp_path):
    bad = rag_recipe_copy(tmp_path, intro_extra="We used 3 runs.")
    with pytest.raises(ValueError, match="digit"):
        load_recipe("rag", root=tmp_path)

def test_recipe_names_must_not_clash(tmp_path):
    rag_recipe_copy(tmp_path, other_label="closed-book model plus")
    with pytest.raises(ValueError, match="clash"):
        load_recipe("rag", root=tmp_path)
```

The validators enforce the rules of vocab.py:3-6: no digits in filler or claim text, and no name contained in another (truth.py:281).

- [ ] **Step 2:** Run `uv run pytest synth/tests/test_recipe.py -q`. Expected: FAIL (`No module named synth.recipe`).
- [ ] **Step 3:** Implement `synth/recipe.py` (pydantic `Strict` models, `yaml.safe_load`) and the yaml file.
- [ ] **Step 4:** Run `uv run pytest synth/tests/test_recipe.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git add synth/recipe.py synth/tests/test_recipe.py domains/rag && git commit -m "synth: generator recipe format; domains/rag/generator.yaml from vocab.py"`

### Task 2: The generator reads the recipe; `synth/vocab.py` removed

**Files:**
- Modify `synth/truth.py`:
  - `make_study` :287-340: `names_of` from `recipe.sides[spec.compare.<side>]`; the `QUESTION_METRICS` check :291 becomes "metric not in recipe"; the unit comes from `MetricSpec.unit`, no longer fixed to "fraction" at :308.
  - `_pair` :252 and `_value` :266 read `pair_range`/`range`; `_improvement` :238 reads `recipe.effects`.
  - `generate` gains `recipe: Recipe | None = None` (default `load_recipe(protocol.domain)`).
- Modify `synth/levels.py:182` (claims from `recipe.text.claims`) and `synth/render_template.py`:
  - :30-31 and :50 move to `recipe.text.templates`;
  - `vocab.*` call sites :46, 89, 93, 172, 181, 207, 212, 217.
- Modify `synth/render_llm.py`: :81 uses `Study.treatment_role`; :97 dataset size comes from `recipe.reporting.allowed_numbers`.
- Modify `synth/fidelity.py`: `ALLOWED_NUMBERS` :28 from the recipe; `stray_numbers` :138 bases from `count_base`; `added_numbers` :162 codes from `plan.cond_aliases`; `added_claims` :181 uses the recipe's claim cues `recipe.text.claim_cues`, generator-side and never `words.yaml`.
- Modify `synth/corpus.py` (`write_corpus` records `recipe: {domain, sha256}` in corpus.json; `GENERATOR_VERSION = "3"`) and `synth/cli.py` (`--domain`, default `rag`).
- Modify `synth/tests/*` (replace `vocab.` imports with recipe values).
- Prompts become templates: `synth/prompts/render-v3.txt`, `statements-v2.txt` and `blind-v3.txt` are created with `<<NAME>>` placeholders filled from `recipe.text.prompt_words` and `blind_examples`, filled like `evaluation/baselines/common.py:319-321`, with the same "no placeholder left" assert. The v2/v1 files stay for replay.
- Delete: `synth/vocab.py`.
- Replace: `synth/tests/test_example.py:25` `test_example_corpus_is_up_to_date` becomes `test_example_corpora_unchanged_on_disk`, pinned by `synth/tests/data/example_sha256.json`. Reason in the docstring: D36, spec §5 "sha256 test on the files".
- Modify: `evidence/tests/test_no_topic_words.py` (`CHECKED_DIRS += ["synth"]`).

**Interfaces:**
- Consumes: `load_recipe`, `Protocol.domain` (plan 1 Task 2).
- Produces: `truth.generate(seed, n, mix=None, spec=None, *, recipe=None, ...)`; `Plan.recipe: Recipe`; `PROMPT_VERSION = "v3"` recorded in `LlmRenderer.models()["paper_prompt"]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_rag_build_from_recipe_passes_fidelity(tmp_path):
    out = corpus.build(name="r", seed=1, studies=6, renderer=TemplateRenderer(), out=tmp_path)
    assert out["excluded"] == {}

def test_example_corpora_unchanged_on_disk():
    assert tree_sha256(EXAMPLES) == json.loads(PINS.read_text())

def test_no_vocab_module():
    assert importlib.util.find_spec("synth.vocab") is None

def test_filled_prompts_have_no_placeholder():
    assert "<<" not in render_llm.instructions(load_recipe("rag"))
```

- [ ] **Step 2:** Run `uv run pytest synth -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. Generate `PINS` once from the files on disk before changing any code.
- [ ] **Step 4:** Run `uv run pytest synth evidence/tests/test_no_topic_words.py -q`. Expected: PASS. Fix any remaining hits by moving the words into `domains/rag/generator.yaml`.
- [ ] **Step 5: Commit** `git commit -am "synth: generator reads domains/<name>/generator.yaml; vocab.py removed; examples pinned by sha256 (D36)"`

### Task 3: Drafting helper for `generator.yaml` (D39)

**Files:**
- Create:
  - `synth/draft.py`;
  - `synth/prompts/draft-generator-v1.txt`: one atomic task, "from these papers, propose the recipe fields; invent new names"; input = paper texts, output = `Recipe` JSON minus `sha256`;
  - `synth/prompts/draft-check-v1.txt`: a separate verifier that quotes the source sentence for each value range, sample size, reporting style, limitation category and builds-on pattern;
  - `domains/heldout.yaml`: `{yun2024: [<PMCIDs of the 120 reports in evaluation/data/annotated_rct_dataset.csv of github.com/hyesunyun/llm-meta-analysis>], scilead: [...], scirex: [...]}`, filled from those repos' id lists;
  - `synth/tests/test_draft.py`.
- Modify: `synth/cli.py` (subcommand `draft`).

**Interfaces:**
- Consumes: `modelcall.ask`, `modelcall.exchange.model_for`, `JsonlCache`, `load_recipe` for validation.
- Produces:
  - `draft(domain: str, papers: Path, *, model, verify_model, cache: Path) -> Path` writes `domains/<domain>/generator.yaml` and adds `provenance.json["generator"] = {"papers": [{file, sha256, id}], "model", "verify_model", "prompt_sha256", "calls": "<cache path>", "quotes": [...]}`.
  - Rules pinned:
    - 5 ≤ papers ≤ 10;
    - a paper whose id, or whose text containing a PMCID, is in `domains/heldout.yaml` is refused;
    - every `label`, `synonym` and `code` of `sides`/`others`/`network.things` must not occur (after `names.clean`) in any source paper;
    - every verifier quote must be a verbatim substring of a source paper.

- [ ] **Step 1: Write the failing tests**

```python
def test_draft_needs_five_to_ten_papers(tmp_path):
    with pytest.raises(ValueError, match="5-10"):
        draft("toy", papers_dir(tmp_path, n=4), model=SCRIPTED, verify_model=SCRIPTED, cache=tmp_path / "c.jsonl")

def test_heldout_paper_refused(tmp_path):
    with pytest.raises(ValueError, match="held out"):
        draft("toy", papers_dir(tmp_path, n=5, first_text="PMCID: PMC1234567"), model=SCRIPTED, verify_model=SCRIPTED, cache=tmp_path / "c.jsonl")

def test_real_drug_name_refused(tmp_path):
    with pytest.raises(ValueError, match="invented"):
        draft("toy", papers_dir(tmp_path, n=5, first_text="Metformin was given."), model=scripted_recipe(thing="metformin"), verify_model=SCRIPTED, cache=tmp_path / "c.jsonl")

def test_draft_is_logged_in_provenance(tmp_path):
    draft("toy", papers_dir(tmp_path, n=5), model=scripted_recipe(), verify_model=scripted_quotes(), cache=tmp_path / "c.jsonl", root=tmp_path)
    prov = json.loads((tmp_path / "toy/provenance.json").read_text())
    assert len(prov["generator"]["papers"]) == 5 and prov["generator"]["prompt_sha256"]
```

The tests use a held-out fixture `PMC1234567` through a `heldout=` argument.

- [ ] **Step 2:** Run `uv run pytest synth/tests/test_draft.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. The draft reply is validated with `Recipe.model_validate`. A failure goes back once with the validation error (`ask` retries=1), then fails.
- [ ] **Step 4:** Run `uv run pytest synth/tests/test_draft.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git add synth/draft.py synth/prompts/draft-*.txt domains/heldout.yaml synth/tests/test_draft.py && git commit -am "synth: generator.yaml drafting helper with held-out and invented-name checks (D39)"`

### Task 4: Multi-arm studies, count values, and the truth network

**Files:**
- Create: `synth/network.py`, `synth/tests/test_network.py`, `synth/tests/fixtures/drugtoy/generator.yaml`.
- Modify:
  - `synth/truth.py`: `Study` gains `population: str | None`, `arm_sizes: dict[str, int]` and `label: str` (author-year, invented from `recipe.text.authors`); `Measurement` gains `k: int | None`.
  - `synth/levels.py`: `write_value`/`parse_value` gain fmt `k_of_n`: `"{k} of {n} patients"`, with the noun from `recipe.text.unit_noun`.
  - `synth/corpus.py:93-113`: write `population`, `label`, `arm_sizes`, the top-level `types` and `network`.

The drugtoy fixture recipe: things `Zelvora, Quintapride, Morvectin` + reference `placebo`; edges `[[Zelvora, placebo], [Zelvora, Quintapride], [Quintapride, Morvectin]]`; contexts `[adults, older adults]`; arm_size (60, 240); formats `[k_of_n, pct, cell_pct]`.

**Interfaces:**
- Produces:
  - `network.latent(seed: int, recipe: Recipe) -> dict[tuple[str, str], float]`: (thing, context) → true response rate. Draw from `MetricSpec.pair_range`. Adjacent things in the drawn order differ by at least `2 * min_effect + effects["supports"][0]`, so every edge has a determined direction.
  - `network.plan_studies(seed, n, recipe, spec) -> list[tuple[edge, context]]`: round robin over edges × contexts, then shuffled from `random.Random(f"synth:{seed}:network")`.
  - `make_study` with a recipe network: two arms (edge) plus 0-1 distractor thing. Arm values: `k = round(rate * n)` with n drawn in `arm_size`, redrawn until `1 <= k < n` and `rules.effect(k_a/n_a, k_b/n_b, ...)` matches the latent direction.
  - `network.chains(studies, recipe, spec) -> list[dict]`: for every ordered pair (X, Z) without a direct study, every path X-Y-Z of length 2. Each record: `{source, target, via, studies, metric, context, verdict, reason}`, with verdict/reason following the Task 9 rules applied to truth.
  - Without a recipe network, `generate` is byte for byte the Task 2 output.

- [ ] **Step 1: Write the failing tests**

```python
def test_values_are_exact_counts_over_arm_size():
    for s in generate(3, 12, recipe=DRUGTOY):
        for m in s.measurements:
            n = s.arm_sizes[m.condition]
            assert m.k is not None and 1 <= m.k < n and m.value == m.k / n

def test_network_edges_all_appear_in_each_context():
    seen = {(edge(s), s.population) for s in generate(3, 12, recipe=DRUGTOY)}
    assert len(seen) == 6

def test_chain_truth_follows_latent_order():
    studies = generate(3, 12, recipe=DRUGTOY)
    c = [c for c in chains(studies, DRUGTOY, SPEC) if c["source"] == "Zelvora" and c["target"] == "Morvectin"]
    assert c and all(c_["via"] == ["Quintapride"] for c_ in c)
    assert {c_["verdict"] for c_ in c} <= {"better", "worse", "refused"}

def test_rag_set_unchanged_without_network():
    assert generate(1, 6) == generate(1, 6, recipe=load_recipe("rag"))
```

- [ ] **Step 2:** Run `uv run pytest synth/tests/test_network.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest synth -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "synth: multi-arm studies with counts per arm and a truth network for chaining"`

### Task 5: `builds_on` preset, planted limitations, name variants

**Files:**
- Modify: `synth/truth.py` (new stream `synth:{seed}:builds_on`; `Study.dependencies: tuple[Dependency, ...]`, `Study.limitations: tuple[Limitation, ...]`, `Condition.variants: tuple[tuple[str, str], ...]` as (kind, form)), `synth/corpus.py` (`settings.preset`; truth records `dependencies`, `limitations`, `variants`), `synth/cli.py` (`--preset plain|builds_on`, default `plain`).
- Test: `synth/tests/test_builds_on.py`.

**Interfaces:**
- Produces:
  - `Dependency(id: str, cites: str, reuses: Literal["method","dataset","result"], thing: str | None, measurement: str | None)`. `cites` is the cited study's id; its rendering uses that study's `label`.
  - `reuses == "result"`: the citing study's reference-arm measurement equals the cited study's value on the same thing, metric and context. Its `measurement` names the copied fact and the truth marks it `copied_from: <study id>`.
  - Only earlier study ids may be cited. `share` and `reuses` weights come from `recipe.builds_on`.
  - `Limitation(id: str, thing: str, category: str, sentence: str)`: `per_study` drawn in `recipe.limitations.per_study`, the sentence from the category's templates with `{thing}` filled.
  - Name variants: with probability `recipe.name_variants.share`, a thing's mention in a paper uses a variant:
    - `spelling` (hyphen/case changes, e.g. "Zelvora" → "ZELVORA", "zel-vora");
    - `code_name` (an invented code such as "ZV-217", introduced as "Zelvora (ZV-217)");
    - `hereafter` ("… (hereafter ZV)").
    - Each variant is recorded in `Condition.variants`, and the variant form never contains another thing's name.
  - `--preset plain` with the RAG recipe gives the Task 2 set byte for byte.

- [ ] **Step 1: Write the failing tests**

```python
def test_dependencies_only_cite_earlier_studies():
    for s in generate(4, 16, recipe=DRUGTOY, preset="builds_on"):
        assert all(d.cites < s.study_id for d in s.dependencies)

def test_copied_result_equals_the_original_value():
    studies = {s.study_id: s for s in generate(4, 16, recipe=DRUGTOY, preset="builds_on")}
    for s in studies.values():
        for d in (d for d in s.dependencies if d.reuses == "result"):
            assert s.value_of(d.measurement) == original_value(studies[d.cites], s, d)

def test_limitations_use_recipe_categories():
    cats = set(DRUGTOY.limitations.categories)
    assert {l.category for s in generate(4, 16, recipe=DRUGTOY) for l in s.limitations} <= cats

def test_plain_preset_has_no_dependencies():
    assert all(not s.dependencies for s in generate(4, 16, recipe=DRUGTOY, preset="plain"))
```

- [ ] **Step 2:** Run `uv run pytest synth/tests/test_builds_on.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest synth -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "synth: builds_on preset, planted limitations and name variants"`

### Task 6: Rendering the new facts; schema-driven fidelity and blind reader

**Files:**
- Modify:
  - `synth/text.py:11`: `ROLES` += `"limitation"`, `"dependency"`, `"study_label"`, `"context_label"`.
  - `synth/levels.py`: `Plan` gains `limitations`, `dependencies`, `label`, `variants`. Each level places them in fixed sections: limitations in Discussion, dependencies in Method ("as reported by {label}" for result, "we reuse the protocol of {label}" for method, "the cohort of {label}" for dataset), the label in the byline under the title.
  - `synth/render_template.py`.
  - `synth/render_llm.py` `plan_json` :77 (adds `limitation_sentences`, `dependency_sentences`, `byline`, each with `write_exactly`) and `locate` :128.
  - `synth/fidelity.py`:
    - `facts_rendered` :63 reads the fact roles from `ground_truth.types` and the plan, no longer the fixed list at :66-69;
    - new checks `limitations_placed` and `dependencies_placed` (each sentence exactly once, in its section);
    - `BlindExtraction` :211 is built per recipe by `blind_model(recipe) -> type[BaseModel]`, with fields `measurements[{thing, metric, <recipe.context>, value}]`, `limitations[{thing, category}]` and `cites[{label, reuses}]`;
    - `blind_check` :257 checks every planned limitation (thing by `names_condition`, category exact) and dependency (label exact) besides the values.
  - `synth/prompts/blind-v3.txt`: per-field instructions filled from the recipe; `limitation categories` given as an enum.
- Test: `synth/tests/test_fidelity_schema.py`.

**Interfaces:**
- Produces: `blind_model(recipe) -> type[BaseModel]`; check names `limitations_placed`, `dependencies_placed`, `blind_limitations`, `blind_dependencies`.

- [ ] **Step 1: Write the failing tests**

```python
def test_template_drug_papers_pass_every_check(tmp_path):
    out = corpus.build(name="d", seed=2, studies=6, renderer=TemplateRenderer(), out=tmp_path, domain="drugtoy",
                       preset="builds_on", domains=FIXTURES)
    assert out["excluded"] == {}

def test_missing_limitation_sentence_fails(tmp_path):
    r = render_study(DRUG_STUDY, "explicit", 1)
    text = r.text.replace(r.plan.limitations[0].sentence, "")
    assert not ok(check_paper(text, r.plan, relocate(text, r.plan), []), "limitations_placed")

def test_blind_reader_must_return_count_values_and_limitations():
    r = render_study(DRUG_STUDY, "explicit", 1)
    checks = run(blind_check(r.text, r.plan, scripted_blind(drop="limitations")))
    assert not ok(checks, "blind_limitations") and ok(checks, "blind_reextraction")

def test_blind_schema_uses_recipe_context_name():
    assert "population" in blind_model(DRUGTOY).model_json_schema()["$defs"]["BlindMeasurement"]["properties"]
```

- [ ] **Step 2:** Run `uv run pytest synth/tests/test_fidelity_schema.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. The RAG recipe has no limitations or dependencies, so its checks list grows only by checks that pass trivially. Make sure `synth/examples` stay untouched (Task 2 pin).
- [ ] **Step 4:** Run `uv run pytest synth -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "synth: render limitations, dependencies and bylines; fidelity and blind reader read the schema"`

### Task 7: The 5-paper trial gate

**Files:**
- Modify: `synth/cli.py` (subcommand `trial`; `build` gate), `synth/corpus.py` (`trial(domain, *, renderer, seed=0, studies=5) -> dict`).
- Test: `synth/tests/test_trial.py`.

**Interfaces:**
- Produces: `domains/<domain>/trial.json` `{"recipe_sha256", "renderer", "models", "studies": 5, "levels": ["mixed"], "passed": bool, "fidelity": [...], "blind": [...]}`.
  - The trial passes when all 5 papers pass every check on the first `--attempts`, and `blind_reextraction`, `blind_limitations` and `blind_dependencies` all pass. A verify model is required.
  - The `--preset builds_on` set is used.
  - `synth build --domain D --renderer llm` exits 2 with `ERROR: no passing 5-paper trial for this generator.yaml (run synth trial)` unless `trial.json` passed and its `recipe_sha256` equals `load_recipe(D).sha256`.
  - The template renderer is not gated.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_refused_without_trial(tmp_path):
    assert cli.main(["build", "--domain", "drugtoy", "--name", "x", "--seed", "1", "--renderer", "llm",
                     "--model", "exchange:w", "--out", str(tmp_path)]) == 2

def test_trial_needs_a_verify_model(tmp_path):
    with pytest.raises(SystemExit, match="verify"):
        trial("drugtoy", renderer=llm_renderer(verify=None), root=FIXTURES)

def test_trial_records_recipe_hash_and_stale_trial_refused(tmp_path):
    t = trial("drugtoy", renderer=scripted_llm_renderer(), root=copy_fixture(tmp_path))
    assert t["passed"] and t["recipe_sha256"] == load_recipe("drugtoy", root=tmp_path).sha256
    touch_recipe(tmp_path)
    assert gate("drugtoy", root=tmp_path) is False
```

- [ ] **Step 2:** Run `uv run pytest synth/tests/test_trial.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest synth -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "synth: 5-paper trial gate before an LLM-written corpus (D39)"`

### Task 8: New kinds registered; comparisons built from pairs in a study

**Files:**
- Modify:
  - `evidence/pack.py`: `Role` += `LIMITATION`, `DEPENDENCY`, `STUDY_LABEL`; `TypeDecl.context_field`; `domains/rag/pack.yaml` measurement `context_field: dataset`.
  - `evidence/protocol.py:37-40`: `Kind` and `KIND_BLOCKS` += `chaining: ("chaining",)`, `limitations: ("limitations",)`, `builds_on: ("builds_on",)`; models `Chaining`, `LimitationsQ`, `BuildsOnQ`; `DIGEST_OMIT_AT_DEFAULT` keeps old hashes.
  - `evidence/questions.py:25-37`: `TRUTH_FIELDS` += `chaining: ("metric", "min_effect", "source", "target")`, `limitations: ("thing",)`, `builds_on: ("thing",)`; `QuestionTruth` gains `source`, `target`, `thing`.
  - `evidence/kinds/__init__.py:23` (register the three modules, Tasks 9-11).
  - `evidence/engine.py:529` (`finish`: write `comparisons.json` before `answer`; pass `comparisons` to kinds that take it).
  - `evidence/rundir.py` (`COMPARISONS_FILE = "comparisons.json"`).
- Create: `evidence/comparisons.py`, `evidence/tests/test_comparisons.py`, `evidence/tests/fixtures/drugtoy/` (extend plan 1's fixture with types `population` (context), `limitation`, `dependency`, `study_label`).

**Interfaces:**
- Consumes: `RoleMap`, `NameGroups.group_of`, `synthesis.best_value` :83, `rules.effect`.
- Produces: `Comparison` and `build_comparisons` (Shared interfaces). Rules:
  1. Within one document, every unordered pair of compared-thing groups with measured values on the same metric canonical and the same context value forms one comparison. A value with context None pairs only when one side names no context, as `synthesis._pair` :103-107.
  2. `a` is the group whose name sorts first. Treatment and control are decided later, by the kind.
  3. Among several values of one group, `prefer` decides (`best_value`).
  4. A value whose item links to a dependency item with `reuses == "result"` gets `copied_from = <cited document>`. A comparison whose two values are both copied is dropped. A comparison equal in (a, b, metric, context, a_value, b_value) to one already listed from its cited document is listed under `"copied"`, not under `"comparisons"`.
  5. Ids are `cmp-<16 hex>` from `contract.digest`.
- The `effect` kind and the RAG protocols keep `synthesis.compare` (spec §6.2); `comparisons.json` is written for every kind.

- [ ] **Step 1: Write the failing tests**

```python
def test_three_arms_give_three_comparisons():
    cs = build(three_arm_items(), groups=GROUPS)
    assert {(c.a, c.b) for c in cs} == {("Morvectin", "Quintapride"), ("Morvectin", "placebo"), ("Quintapride", "placebo")}

def test_values_on_different_populations_do_not_pair():
    assert build(two_arms_two_populations(), groups=GROUPS) == []

def test_copied_control_counts_once_at_origin(tmp_path):
    out = drugtoy_run(tmp_path, papers=["origin.md", "copier.md"])
    data = json.loads((out / "comparisons.json").read_text())
    assert len(data["copied"]) == 1 and data["copied"][0]["copied_from"] == "origin"

def test_rag_protocol_hashes_unchanged_by_new_kinds():
    for path in RAG_PROTOCOLS:
        assert load(path).sha256() == OLD_SHA[path.stem]
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_comparisons.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: comparisons built from pairs in a study (comparisons.json); kinds chaining, limitations, builds_on registered"`

### Task 9: Chaining kind

**Files:**
- Create: `evidence/kinds/chaining.py`, `evidence/tests/test_chaining.py`.

**Interfaces:**
- Consumes: `comparisons.json` rows, `NameGroups.group_of`, `Chaining` block, `rules.effect`.
- Produces: `answer = {kind: "chaining", system, source, target, metric, verdict, inferred, via, studies, paths, reason, note}`.
  - `verdict ∈ {"better","worse","no_difference","refused"}`.
  - `note` is the exact string `"inferred through {via}, not tested directly"` when inferred, else null.
- Rules, in this order:
  1. If any comparison links source and target directly on the metric, the answer is the direct result with `inferred: false`, `reason: "direct_comparison"`. It is never chained.
  2. Paths X-Y-Z of at most `max_hops` steps use comparisons on `metric.canonical` only. A step on another metric is skipped and recorded as `metric_differs` when no path remains.
  3. Both steps must share the context value when both name one; otherwise `context_differs`.
  4. Each step's direction comes from `rules.effect` (`min_effect`). Better then better concludes better; worse then worse concludes worse. Anything else (including a neutral step) gives `mixed_directions`.
  5. Several paths with different verdicts give `paths_disagree`, verdict `refused`.
  6. No path at all gives `no_path`.
  7. `studies` lists every document the chosen paths rest on, in manifest order.
- `study()` per document returns its comparisons involving source, target or any via. `gap_types` escalates `measured_value` for `no_path`.

- [ ] **Step 1: Write the failing tests**

```python
def test_chain_concludes_and_is_marked_inferred():
    a = answer(cmps(("A", "B", "better", "adults", "s1"), ("B", "C", "better", "adults", "s2")), source="A", target="C")
    assert (a["verdict"], a["inferred"], a["via"], a["studies"]) == ("better", True, ["B"], ["s1", "s2"])
    assert a["note"] == "inferred through B, not tested directly"

def test_chain_refused_across_populations():
    a = answer(cmps(("A", "B", "better", "adults", "s1"), ("B", "C", "better", "children", "s2")), source="A", target="C")
    assert (a["verdict"], a["reason"]) == ("refused", "context_differs")

def test_chain_through_name_variant():
    a = answer(cmps(("A", "Drug B", "better", None, "s1"), ("drug-B", "C", "better", None, "s2")), source="A", target="C",
               groups=groups_joining("Drug B", "drug-B"))
    assert a["verdict"] == "better"

def test_direct_result_is_never_chained():
    a = answer(cmps(("A", "C", "worse", None, "s3"), ("A", "B", "better", None, "s1"), ("B", "C", "better", None, "s2")), source="A", target="C")
    assert (a["verdict"], a["inferred"], a["reason"]) == ("worse", False, "direct_comparison")

@pytest.mark.parametrize("d1,d2", [("better", "worse"), ("better", "no_difference")])
def test_mixed_steps_are_refused(d1, d2):
    assert answer(cmps(("A", "B", d1, None, "s1"), ("B", "C", d2, None, "s2")), source="A", target="C")["reason"] == "mixed_directions"
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_chaining.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: chaining kind (same metric and context, marked inferred, refusals named)"`

### Task 10: Limitations kind

**Files:**
- Create: `evidence/kinds/limitations.py`, `evidence/tests/test_limitations_kind.py`.

**Interfaces:**
- Consumes: the type with `Role.LIMITATION`. Its fields are `category` (enum = `Pack.limitation_categories`) and `quote` (span role `limitation`); its link `thing` points to the compared-thing type. Also `NameGroups.group_of` and `LimitationsQ.thing`.
- Produces: `answer = {kind: "limitations", system, thing, entries: [{thing, category, papers, items}], counts: {thing: {category: n_papers}}}`.
  - Grouping: (group of thing, category). `papers` are in manifest order. A copied limitation is not a concept, so every paper counts.
  - With `thing` set, only that group's entries.
  - Reasons: `no_limitation_items` (escalates the limitation type), `unlinked` (a limitation without a thing; kept under thing `null`).

- [ ] **Step 1: Write the failing tests**

```python
def test_limitations_grouped_by_thing_and_category():
    a = answer(lims(("p1", "Zelvora", "small_sample"), ("p2", "ZELVORA", "small_sample"), ("p2", "Zelvora", "side_effects")))
    assert a["counts"]["Zelvora"] == {"small_sample": 2, "side_effects": 1}

def test_question_thing_filters_entries():
    a = answer(lims(("p1", "Zelvora", "cost"), ("p1", "Morvectin", "cost")), thing="Morvectin")
    assert [e["thing"] for e in a["entries"]] == ["Morvectin"]

def test_unknown_category_is_rejected_by_schema():
    with pytest.raises(ValidationError):
        lim_item(category="bad_luck")
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_limitations_kind.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: limitations kind"`

### Task 11: Builds-on / influence kind

**Files:**
- Create: `evidence/kinds/builds_on.py`, `evidence/tests/test_builds_on_kind.py`.

**Interfaces:**
- Consumes:
  - the `Role.DEPENDENCY` type: fields `cited` (text as written), `reuses ∈ {method, dataset, result}`; link `thing` (optional);
  - the `Role.STUDY_LABEL` type: field `label`, one per paper (the byline);
  - `NameGroups.group_of` (resolves `cited` to the document whose label is in the same group).
- Produces: `answer = {kind: "builds_on", system, thing, links: [{from, to, reuses, items}], followers: {thing: [docs]}, influence: {thing: int}, ranking: [thing...], unresolved: [cited]}`.
  - Origin of a thing: the earliest document by its label's year (ties: manifest order) that mentions the thing with no dependency for it.
  - Followers: documents with a path of links to the origin, direct or indirect, with a visited set, so cycles end.
  - `influence[x] = len(followers[x])`. `ranking` sorts by influence, descending, then name.
  - A `cited` text with no matching label goes to `unresolved`.

- [ ] **Step 1: Write the failing tests**

```python
def test_direct_and_indirect_followers():
    a = answer(deps(("p2", "p1", "method"), ("p3", "p2", "method")), origins={"Zelvora": "p1"})
    assert a["followers"]["Zelvora"] == ["p2", "p3"] and a["influence"]["Zelvora"] == 2

def test_cycle_terminates():
    a = answer(deps(("p2", "p1", "method"), ("p1", "p2", "dataset")), origins={"Zelvora": "p1"})
    assert a["influence"]["Zelvora"] == 1

def test_unknown_citation_is_reported_not_dropped():
    assert answer(deps(("p2", "Nobody et al. (2017)", "result")))["unresolved"] == ["Nobody et al. (2017)"]
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_builds_on_kind.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evidence -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evidence: builds-on / influence kind"`

### Task 12: Evaluation off `synth.vocab`; generic truth reader

**Files:**
- Modify:
  - `evaluation/truth.py:28-36, 66-79`: `FACT_LISTS`/`MAIN_ROLE`/`TYPES` come from `ground_truth.types` when present, else the current constants; `limitation` and `dependency` facts are read from the new study keys.
  - `evaluation/canon.py`: `KEYS` and `KIND_OF` are built from the corpus's `ground_truth.json` (labels, synonyms, aliases, `variants`, condition `kind`). It becomes `Canon.from_truth(truth)` with `key(target, name)` and `kind_of(label)`; there is no import of synth.
  - `evaluation/score.py:160, 222` (`QUESTION_CANONICALS` from `truth.studies[*].metrics[0].canonical`).
  - `evaluation/expected.py:48, 67-69` (spec from `load_recipe(<corpus.json recipe.domain>)` and the domain's effect protocol, no longer `default_spec()`).
  - `evaluation/tests/test_expected.py:16`.
  - `evidence/tests/test_no_topic_words.py` (`CHECKED_DIRS += ["evaluation"]`).
- Test: `evaluation/tests/test_generic_truth.py`.

**Interfaces:**
- Produces: `Canon` (`key`, `kind_of`), passed into `score_kind`, `expected`, `integration_best`. Effect, inventory and best scores on the EV2 corpora (`tests/EV2/corpora/rag-claude-s1-mixed`) are unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_rag_scores_unchanged_on_ev2_corpus():
    assert score_answers(MIXED, [GOLDEN_ANSWER], question_id="rag-factuality") == GOLDEN_REPORT

def test_canon_built_from_truth_knows_name_variants():
    c = Canon.from_truth(GroundTruth.load(DRUG_GT))
    assert c.key("condition", "ZV-217") == c.key("condition", "Zelvora")

def test_evaluation_does_not_import_synth():
    assert "synth" not in {m.split(".")[0] for m in imported_modules("evaluation")}
```

`GOLDEN_*` come from `evaluation/tests/data/score-golden-tpl-s1-mixed.json`.

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_generic_truth.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement. `DRUG_GT` is a template-built drugtoy ground truth committed under `evaluation/tests/data/drugtoy/`.
- [ ] **Step 4:** Run `uv run pytest evaluation evidence/tests/test_no_topic_words.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evaluation: truth, canon and expected read the corpus, not synth.vocab"`

### Task 13: Expected answers and scores for chaining, limitations, builds-on

**Files:**
- Modify:
  - `evaluation/expected.py:289`: `BUILDERS` += `chaining` (from `ground_truth.network.chains`, filtered to `params.source/target/metric`; a pair with no truth chain expects `refused`/`no_path`), `limitations`, `builds_on` (from planted `dependencies` and the `origin` of each thing).
  - `evaluation/score.py`: `score_kind` :1207 and `integration_kind` :1288.
- Test: `evaluation/tests/test_score_new_kinds.py`.

**Interfaces:**
- Produces:
  - **Chaining, C** (`score_chaining`): `{verdict_correct, inferred_correct, path_correct, refusal_correct}`. `path_correct` compares the `via` group keys and the study set; `refusal_correct` is right when truth refuses and the answer refuses with the same `reason`. **B:** comparison precision/recall over (doc, group a, group b, metric, context) against truth `network.comparisons`.
  - **Limitations, A** (`score_extraction` through new fact type `limitation`): precision/recall of (study, thing, category). **C:** per-thing category lists, Jaccard and exact match.
  - **Builds-on, B:** link precision/recall over (from, to, reuses). **C:** per-thing follower-set F1, influence ranking Kendall τ (`scipy.stats.kendalltau`), and top-1 correct.
  - **No double counting, C:** `copied_counted_once` is true when no copied comparison appears in an answer's counted studies.
  - **Headline (cross-plan, plan 3 Task 6 reads it):** each new kind's C result carries a float `headline` key: chaining = mean of `verdict_correct` and `path_correct`; limitations = per-thing Jaccard mean; builds_on = follower-set F1 mean. The test helper `headline(result) -> dict` returns the C result's boolean/float fields used in the test below.

- [ ] **Step 1: Write the failing tests**

```python
def test_expected_answer_scores_perfectly_against_itself():
    for kind, params in NEW_QUESTIONS:
        exp = expected(DRUG, kind, params)
        assert all(v in (1.0, True) for v in headline(score_kind(DRUG, kind, params, None, exp | {"system": "x"})).values())

def test_wrong_via_scores_path_incorrect():
    exp = expected(DRUG, "chaining", CHAIN_PARAMS)
    assert score_kind(DRUG, "chaining", CHAIN_PARAMS, None, exp | {"via": ["Morvectin"]})["path_correct"] is False

def test_double_counted_copy_is_caught():
    assert score_kind(DRUG, "effect", EFFECT_PARAMS, None, counting_copy_twice())["copied_counted_once"] is False
```

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_score_new_kinds.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evaluation -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "evaluation: expected answers and A/B/C scores for chaining, limitations, builds-on"`

### Task 14: Baseline map prompts for the new shapes; effect map prompt without topic words

**Files:**
- Create:
  - `evaluation/baselines/prompts/map-effect-v2.md` (map-effect-v1.md with "retrieval" replaced by `<<TREATMENT>>`/`<<CONTROL>>` from `pack.display`);
  - `map-chaining-v1.md` (reply `{verdict, via, papers, inferred}`);
  - `map-limitations-v1.md` (reply `{entries: [{thing, category, papers}]}`, category an enum of the pack's list);
  - `map-builds-on-v1.md` (reply `{links: [{from, to, reuses}], followers: [{thing, papers}]}`).
  - Each prompt follows the map-inventory-v1.md layout: Task, Input fields, Output, Rules, three examples, with `<<NAME>>` placeholders.
- Modify `evaluation/baselines/common.py`:
  - `MAP_PROMPTS` :199 points at the new files;
  - `MAP_INSTRUCTIONS`/`LABEL_RULES` :94-110 and the `DEFAULT_QUESTION_ID` special case :198, 290 are removed; cache misses are accepted (D36);
  - `DEFAULT_QUESTION` :45 and `TARGET_TEXT` :201 examples come from the pack;
  - `map_prompt` :286 and `kind_answer_json` :331 (shapes for the new kinds; influence computed here from `followers`, never asked).
- Modify `evaluation/baselines/rag.py:60` (`SYSTEM = "bm25-answer-baseline"`, spec §6.1; old run dirs keep their name).
- Test: `evaluation/tests/test_baseline_new_kinds.py`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("kind", ["chaining", "limitations", "builds_on"])
def test_map_prompt_is_filled_and_reply_shaped(kind):
    text, reply = map_prompt(params_for(kind))
    assert "<<" not in text and reply.model_json_schema()

def test_effect_map_prompt_has_no_rag_words():
    text, _ = map_prompt(params_for("effect", pack="drugtoy"))
    assert "retrieval" not in text.lower() and "Zelvora" not in text

def test_limitation_category_outside_pack_list_fails_validation():
    _, reply = map_prompt(params_for("limitations"))
    with pytest.raises(ValidationError):
        reply.model_validate({"entries": [{"thing": "Zelvora", "category": "weather", "papers": []}]})

def test_baseline_chaining_answer_scores_like_engine(tmp_path, monkeypatch):
    guard_corpus(monkeypatch, DRUG_CORPUS)
    a = rag_baseline(DRUG_CORPUS, model=Scripted(chain_reply()).model(), question_id="drug-chain-zel-mor")
    assert a["kind"] == "chaining" and "verdict" in a
```

- [ ] **Step 2:** Run `uv run pytest evaluation/tests/test_baseline_new_kinds.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest evaluation -q`. Expected: PASS. Update `test_baseline_kinds.py:38` `test_effect_mapping_prompt_unchanged` to assert v2 instead, with comment "D36".
- [ ] **Step 5: Commit** `git commit -am "evaluation: baseline map prompts for chaining, limitations, builds-on; effect map prompt filled from the pack"`

### Task 15: Corpus tool server (port of research-harness-ui `packages/mcp_corpus`)

**Files:**
- Create: `packbuilder/__init__.py`, `packbuilder/server.py`, `packbuilder/cli.py`, `packbuilder/tests/__init__.py`, `packbuilder/tests/test_server.py`.
- Modify `pyproject.toml`:
  - `uv add "pydantic-ai-slim[openai,mcp]==2.55.0"`, which brings `mcp`;
  - `[project.scripts] packbuilder = "packbuilder.cli:main"`;
  - add `packbuilder` to `module-name` and `testpaths`.

**Interfaces:**
- Consumes: `evaluation.baselines.common.SystemCorpus` :58. It is the only reader: it opens `manifest.json` and listed files directly in `papers/` and checks each sha256.
- Produces `create_server(corpus: Path) -> FastMCP` (`mcp.server.fastmcp.FastMCP("corpus")`, as old server.py:14-16). Tools:

| Tool | Returns |
|---|---|
| `list_papers()` | `[{id, title, chars}]` (title = first `# ` line) |
| `read_paper(paper_id, offset=0, limit=20000)` | `{id, text, offset, total}` |
| `read_section(paper_id, heading)` | the `## heading` block; unknown heading is an error listing the headings |
| `search(query, k=10)` | `rank_bm25.BM25Okapi` over paragraphs (blank-line split, as `rag.paragraph`), tokens `\w+` lower-cased, as rag.py:67; returns `[{paper, start, end, score, text}]` |
| `grep(regex, limit=50)` | `[{paper, line, start, text<=200 chars}]`; invalid regex is an error |
| `tables(paper_id)` | Markdown tables as `{header: [...], rows: [[...]], start, end}` |

- An unknown `paper_id` is an error, not an empty result (old server.py:20-24).
- `packbuilder serve --corpus DIR` runs `mcp.run(transport="stdio")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_server_lists_exactly_six_tools():
    tools = run(create_server(CORPUS).list_tools())
    assert {t.name for t in tools} == {"list_papers", "read_paper", "read_section", "search", "grep", "tables"}

def test_server_never_opens_gold(monkeypatch, tmp_path):
    corpus = copy_corpus_with_gold(tmp_path)
    attempts = guard_corpus(monkeypatch, corpus)
    srv = create_server(corpus)
    for name, args in [("list_papers", {}), ("search", {"query": "response rate"}), ("grep", {"regex": "studies"}),
                       ("tables", {"paper_id": "S001"})]:
        run(srv.call_tool(name, args))
    with pytest.raises(Exception):
        run(srv.call_tool("read_paper", {"paper_id": "../ground_truth"}))
    assert attempts == []

def test_manifest_listing_gold_is_refused(tmp_path):
    with pytest.raises(ValueError, match="papers/"):
        create_server(corpus_whose_manifest_lists(tmp_path, "ground_truth.json"))

def test_search_is_bm25_ranked():
    hits = run(create_server(CORPUS).call_tool("search", {"query": "placebo response", "k": 3}))
    assert scores_descending(hits)
```

- [ ] **Step 2:** Run `uv run pytest packbuilder/tests/test_server.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest packbuilder -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git add packbuilder pyproject.toml uv.lock && git commit -m "packbuilder: corpus tool server over manifest.json and papers/ (MCP)"`

### Task 16: Pack builder agent and `freeze`

**Files:**
- Create:
  - `packbuilder/agent.py`, `packbuilder/freeze.py`, `packbuilder/proposal.py`;
  - `packbuilder/prompts/propose-v1.md`: one task. Input: the topic question and display-name request. Tools: the six above. Output: `PackProposal`. Rules: every word with a source quote, only from the papers; no gold files exist for you.
  - `packbuilder/tests/test_agent.py`, `packbuilder/tests/test_freeze.py`.
- Modify: `modelcall/exchange.py:48-68` (`_conversation`/`_schema` render tool calls, tool returns and the tool list into the request file), only if `test_agent_runs_through_exchange_with_tools` shows them missing.

**Interfaces:**
- Consumes: `create_server`, pydantic-ai `Agent(model, toolsets=[MCPServerStdio("uv", ["run", "packbuilder", "serve", "--corpus", str(corpus)])], output_type=PackProposal)`, `modelcall.exchange.model_for`, `load_pack`, plan 1's `pack check`.
- Produces:
  - `PackProposal(types: dict[str, TypeDecl], words: Words, display: dict[str, str], limitation_categories: list[str], names_seed: dict[str, list[str]], sources: list[Source])`, with `Source(claim: str, paper: str, quote: str)`.
  - `propose(corpus: Path, name: str, *, model, cache: Path, root: Path = DOMAINS) -> Path` writes `pack.yaml`, `words.yaml` and `provenance.json["words"] = {"by": "packbuilder propose", "model", "prompt_sha256", "corpus_id", "tool_calls": [{tool, args, result_sha256}], "sources": [...], "files_read": [...]}`.
  - Code checks: each `quote` is a verbatim substring of its paper; every enum value and word has a source; `files_read` may only hold `manifest.json` and `papers/*`.
  - `freeze(pack_dir: Path) -> dict` requires that `load_pack` and `pack check` pass, that `provenance.json` has an entry for `pack.yaml`, `words.yaml` and (if present) `generator.yaml`, and that the `words` entry's `files_read` never names `generator.yaml`. It writes `FROZEN.json {pack_sha256, recipe_sha256, files: {name: sha256}}` and prints `git tag ev4-pack-<name>-v1`.
  - Ontology search (§6.4, Should) is left to plan 3's reasoner task.

- [ ] **Step 1: Write the failing tests**

```python
def test_agent_runs_through_exchange_with_tools(tmp_path):
    path = propose(CORPUS, "toy", model=scripted_tool_agent(calls=[("grep", {"regex": "placebo"})], final=PROPOSAL),
                   cache=tmp_path / "c.jsonl", root=tmp_path)
    prov = json.loads((path / "provenance.json").read_text())
    assert prov["words"]["tool_calls"][0]["tool"] == "grep"

def test_non_verbatim_quote_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="quote"):
        propose(CORPUS, "toy", model=scripted_tool_agent(final=PROPOSAL_WITH_BAD_QUOTE), cache=tmp_path / "c.jsonl", root=tmp_path)

def test_freeze_refuses_words_written_from_generator(tmp_path):
    pack = frozen_ready_pack(tmp_path, words_files_read=["generator.yaml"])
    with pytest.raises(ValueError, match="generator.yaml"):
        freeze(pack)

def test_freeze_records_hashes(tmp_path):
    out = freeze(frozen_ready_pack(tmp_path))
    assert set(out["files"]) >= {"pack.yaml", "words.yaml", "provenance.json"}
```

- [ ] **Step 2:** Run `uv run pytest packbuilder -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest packbuilder modelcall -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "packbuilder: pack builder agent over the corpus tool server; freeze"`

### Task 17: D34 fallback helper

**Files:**
- Create: `packbuilder/helper.py`, `packbuilder/prompts/helper-v1.md` (same output `PackProposal`; input = all paper texts of the corpus, read through `SystemCorpus`), `packbuilder/tests/test_helper.py`.
- Modify: `packbuilder/cli.py` (`helper`).

**Interfaces:**
- Produces: `helper(corpus: Path, name: str, *, model, cache: Path, root: Path = DOMAINS) -> Path`. It uses the same quote checks and provenance shape as `propose`, with `"by": "packbuilder helper (D34)"`. It refuses when the corpus directory holds a `generator.yaml` or the corpus.json `recipe` names the target pack's folder as readable input; it only ever reads through `SystemCorpus`.

- [ ] **Step 1: Write the failing tests**

```python
def test_helper_reads_only_manifest_and_papers(monkeypatch, tmp_path):
    corpus = copy_corpus_with_gold(tmp_path)
    attempts = guard_corpus(monkeypatch, corpus)
    helper(corpus, "toy", model=Scripted(PROPOSAL_JSON).model(), cache=tmp_path / "c.jsonl", root=tmp_path / "d")
    assert attempts == []

def test_helper_prompt_holds_no_generator_words(tmp_path):
    m = Scripted(PROPOSAL_JSON)
    helper(CORPUS, "toy", model=m.model(), cache=tmp_path / "c.jsonl", root=tmp_path)
    assert not any(w in m.prompts[0] for w in recipe_only_words(DRUGTOY))
```

`recipe_only_words` are the recipe's filler and claim words, which are not in the corpus.

- [ ] **Step 2:** Run `uv run pytest packbuilder/tests/test_helper.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest packbuilder -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -am "packbuilder: D34 fallback helper"`

### Task 18: Build and freeze `domains/drugtrials`

This task runs the tools on real inputs; there is nothing to implement.

**Files:**
- Create:
  - `domains/drugtrials/{generator.yaml, trial.json, pack.yaml, words.yaml, provenance.json, FROZEN.json}`;
  - `domains/drugtrials/protocols/{dt-effect-response, dt-chain, dt-limitations, dt-builds-on, dt-inventory-arms, dt-best-response, dt-consistency}.yaml`;
  - `domains/drugtrials/questions.yaml`;
  - `tests/EV4/drugtrials/sources.md` (the 5-10 real papers used for drafting: PMCID, title, licence; none in `domains/heldout.yaml`);
  - `tests/EV4/drugtrials/calls/*.jsonl` (all exchange calls);
  - corpora under `tests/EV4/corpora/drug-s1-*`;
  - `evidence/tests/test_drugtrials_pack.py`.

**Interfaces:**
- Consumes: Tasks 1-17.
- Produces: the frozen drug-trials pack and corpus for plan 3's runbook.

- [ ] **Step 1: Write the failing tests**

```python
def test_drugtrials_pack_checks_for_every_question_kind():
    check(load_pack("drugtrials"), kinds=[q.kind for q in questions.load(questions_path("drugtrials"))])

def test_every_kind_has_a_question():
    assert {q.kind for q in questions.load(questions_path("drugtrials"))} == {
        "effect", "chaining", "limitations", "builds_on", "inventory", "best", "consistency"}

def test_frozen_hashes_match_files():
    frozen = json.loads((DOMAINS / "drugtrials/FROZEN.json").read_text())
    assert all(sha256_file(DOMAINS / "drugtrials" / f) == h for f, h in frozen["files"].items())

def test_regex_run_on_three_papers_builds_comparisons(tmp_path):
    out = regex_run(papers_of(DRUG_MIXED, 3), tmp_path, protocol_path("drugtrials", "dt-chain"))
    assert json.loads((out / "comparisons.json").read_text())["comparisons"]
```

- [ ] **Step 2:** Run `uv run pytest evidence/tests/test_drugtrials_pack.py -q`. Expected: FAIL (no pack).
- [ ] **Step 3: Draft the recipe.** Run `uv run synth draft --domain drugtrials --papers <dir of 5-10 PMC OA RCT reports> --model exchange:claude-sonnet-5-5 --exchange <ex>`; Claude subagents answer as in `docs/claude-writer.md`. **Stop for Aditya's ~10-minute review of `generator.yaml`.**
- [ ] **Step 4: Run the trial.** `uv run synth trial --domain drugtrials --model exchange:claude-haiku-5-5 --verify-model exchange:claude-sonnet-5-5 --exchange <ex>`. Expected: `"passed": true`. If it fails, fix the recipe, log why in `provenance.json`, and rerun.
- [ ] **Step 5: Build the corpus.** `uv run synth build --domain drugtrials --name drug-s1 --seed 1 --studies 24 --levels all --preset builds_on --renderer llm --model exchange:claude-haiku-5-5 --verify-model exchange:claude-sonnet-5-5 --min-retained 0.9 --out tests/EV4/corpora --cache tests/EV4/drugtrials/calls/build.jsonl --exchange <ex>`. Truth sizes (spec §8, builder's call): 3 things + placebo, 2 populations, 24 studies.
- [ ] **Step 6: Propose the extraction pack.** `uv run packbuilder propose --corpus tests/EV4/corpora/drug-s1-mixed --name drugtrials --model exchange:claude-sonnet-5-5`, given a fresh subagent brief that names no recipe file. If this is not ready in time, use `packbuilder helper` (D34). **Stop for Aditya's check.** Write the 7 protocols and `questions.yaml` by hand from the RAG ones (`protocol_path("rag", ...)`); the truth params name the drawn things.
- [ ] **Step 7: Freeze and test.** `uv run packbuilder freeze domains/drugtrials`, then `uv run pytest -q`. Expected: PASS.
- [ ] **Step 8: Commit** `git add domains/drugtrials tests/EV4 evidence/tests/test_drugtrials_pack.py && git commit -m "domains: drugtrials generator, corpus drug-s1, extraction pack (frozen; tag pending Aditya)"`. Then report the printed tag command to Aditya; do not run it.

---

## Self-review notes

- **Spec coverage:**

| Spec item | Tasks |
|---|---|
| D39 (draft from 5-10 real papers, invented names, 5-paper trial, one review, frozen) | 3, 7, 18 |
| §6.9 network (A vs placebo, A vs B, B vs C) and counts per arm | 4 |
| §6.11 builds_on preset, copied result counted once | 5, 8, 13 |
| Planted limitations and name variants | 5 |
| Schema-driven fidelity and blind reader | 6 |
| §6.2 comparisons built from pairs | 8 |
| §6.10 chaining with D6 refusals and the "inferred through B" note | 9 |
| §6.18 limitations and builds-on with A/B/C scores and map prompts | 10, 11, 13, 14 |
| §6.5 corpus server and its never-gold test | 15 |
| §6.4 builder, logged and frozen | 16 |
| D34 fallback | 17 |
| No topic words in synth/ and evaluation/ | 2, 12 |
| `rag` baseline renamed (§6.1) | 14 |

- **Left to plan 3:** ontology search and `ontology.ttl` (§6.3/§6.4 web search, Should), the protocol lock, run manifests, real-paper checks, the web app, and the runbook that scores drug trials (all kinds) and RAG (four kinds, D43).
- **Name consistency:** `Recipe`, `load_recipe`, `Comparison`, `build_comparisons`, `CHAIN_REASONS`, `create_server` and `PackProposal` are used under the same names in the tasks and in Shared interfaces. Plan 1's names (`load_pack`, `Pack`, `Role`, `RoleMap`, `protocol_path`, `questions_path`, `read_numbers`, `NameGroups.group_of`, `CHECKED_DIRS`) are used unchanged.
- **Open risk:** whether the exchange model passes tool calls through to the request file (`modelcall/exchange.py:48-68`) is unverified. Task 16 Step 1 tests it first, and the file is modified only if the test fails.
