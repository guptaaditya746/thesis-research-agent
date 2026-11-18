# synth3 Real Papers (plan 2 of 5): renamed real papers with the planted results, medicine first

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** each synth3 folder can be built from real open-access papers in its field instead of template papers.
Every real name in a paper is renamed, the real comparison against the control is removed, and the folder's
planted results are inserted. The truth stays exactly the template build's truth for the same world.

**Architecture:**
- **A real-paper config per domain** (`data/synth3/real/<domain>.yaml`): where the pool comes from, which words
  name the control, which lower-case names (drug names) to rename, which field words to keep, which headings
  mark the results and the conclusion. The approved domain spec and worlds are not touched.
- **A local pool per domain** (`data/synth3/pools/<domain>/`, git-ignored): cleaned markdown papers in one
  shape, whatever the source. Medicine fetches PubMed Central open-access JATS XML through NCBI E-utilities and
  converts it with the repo's existing `evidence.sources.pmc.jats_markdown`. Other sources come in by
  `pool-import` (markdown, JATS or PDF files). A seeded split keeps 30 test papers aside for the realism check.
- **The real edit** is synth2's code-only "template v2" method, made domain-general: rename (synth2
  `build_map`/`apply_map` + a pass for lower-case drug names), delete every sentence, table and heading that
  names the control or a planted name, insert the planted section (the template paper's own result rows, so
  the facts are the same) at the end of Results, and insert the exact template claim sentences into the
  abstract and the conclusion. Placements are shifted to the new offsets and checked with `missing_facts`.
- **`synth3 build-real`** writes the folder with the template folder's `ground_truth.json` keys and values,
  plus one new key `real`.
- **The realism checks of spec §10b:** `synth3 realism` runs synth2's local classifier against the test papers.
  `synth3 reader` is the blind reader: a model reads each paper and code compares its notes with the truth. It
  is built and tested with fake models only; Aditya runs it on the cluster.
- **Scope:** questions, judge and answer sheets are plan 3. Other domains stop at unapproved drafts.

**Tech Stack:** Python >= 3.13, httpx (already a dependency), xml.etree, pydantic, pyyaml, scikit-learn (already
a dependency, for realism), pytest with `httpx.MockTransport`. No new dependencies. Docling only for PDF imports,
from the existing optional `fetch` group.

**Spec:** `docs/superpowers/specs/2026-11-16-multi-domain-benchmark-design.md` (§3, §4 "Synthetic paper", §5.1,
§5.5, §10b "Realism per domain", §10b "Law source", §10c).

**The five plans:**
1. Worlds and template folders (merged).
2. **This plan:** real-paper planting per domain, medicine first.
3. Questions, checklist answer sheets, the judge (reads `ground_truth.json`), review page, baseline scores.
4. The system: model-written answers, the sub-question box and the one-page UI.
5. The readable evidence program and the 5-re-run measurement.

**Review history:** written 17 Nov 2026 by a planner agent. A fresh reviewer found 0 critical, 6 important and
18 minor issues (`.superpowers/sdd/plan2-review.md`); this version fixes the 6 important ones and the minors that
change what gets built. One minor is declined: M18 (reuse `evidence.arxiv.Client`), because its log lines and
User-Agent name arXiv; the PMC client stays small and separately tested.

## Global Constraints

- **No new model, no cluster run:** the paper edit is code only (template v2 style). The one model step, the
  blind reader (Task 10), goes through the existing cluster setup (`modelcall`, alias `sub-model-1`, as
  `docs/prompt-writing.md` assigns verification to a sub-model). It is tested with fake models only, and its
  run command is on Aditya's list. Nothing in this plan runs a model or touches the cluster.
- **Hashed files:** never edit the files listed under "Hashed files: never edit" in `backend/README.md`.
- **synth2 is read-only:** do not change any file in `backend/synth2/`. Import only these:
  - `synth2.realedit`: `build_map`, `apply_map`, `surviving`, `unsayable`, `apply_edits`, `META`,
    `MAX_INSERTED`, `SURNAME_POOL` and `_new_part` (private, but small and tested there; copying it would fork
    the renaming);
  - `synth2.realpool`: `clean_text`, `words`, `md_blocks`, `cut_pieces`, `write_pieces`, `slice_papers`;
  - `synth2.realism`: `c2st`, `style_gap`; `synth2.write`: `Paper`, `Placement`, `_Builder`;
  - `synth2.recipe`: `Strict`.
- **New code lives in `backend/synth3/`** (the evaluation service). It may import `evidence.sources` (engine)
  and `modelcall` (gateway), both below it. No new backend package, so `backend/tests/test_boundaries.py` needs
  no change.
- **Text files:** every read and write passes `encoding="utf-8"`; `tidy` turns `\r\n` into `\n`, so offsets
  never depend on how a file was read.
- **Network:** only `synth3 pool-fetch` uses the network. It calls the public NCBI E-utilities
  (`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`) with `tool=synth3-pool`, the User-Agent
  `synth3-pool/1 (open-access corpus builder)`, no `email`, no API key and no personal detail. At most one
  request per second (NCBI allows 3 without a key). Tests never open a socket: they use
  `httpx.MockTransport` and file fixtures.
- **Local only:** pools go under `data/synth3/pools/` and built folders under `data/synth3/built/`, both
  git-ignored. They are never committed, pushed or published. The `real/maps/*.json` files hold real names.
- **Same truth:** for the same approved world, `build-real` writes `world`, `spec`, `studies` and `facts`
  equal to the template build, the same `(paper, fact)` placements with new offsets, and one extra top-level
  key `real`. Every paper passes `synth3.write.missing_facts` or the build stops.
- **Planted names:** come from the domain spec (arm labels, setting names, measure names, study labels). Real
  names (drugs, trial names, cohorts, hospitals, places, cited authors) are renamed to invented names that are
  never a planted name. A cited author is never renamed to a surname of the spec's author list, because that
  would cite a planted study with findings it does not have.
- **Sources per folder (builder's call):** a source paper is used at most once in a folder. Across folders a
  paper may repeat, because each folder is a separate corpus that a system never reads together with another.
  The source order is cut into disjoint blocks of 40 per seed, so with 200 or more sources the first choices of
  the 5 folders share no paper. A rejected source's replacement comes from the rest of the order and may sit in
  another folder's block; `ground_truth.json` records it. Test papers are never sources.
- **Named seeds:** `random.Random(f"synth3:{seed}:real:<what>")` per folder; the pool split and source order use
  `random.Random(f"synth3:pool:{domain}:<what>")`.
- **Text checks:** new template text has no digits (except the table number), no ids, and every variant list
  has at least 3 entries.
- **Human gates:** Aditya approves domain specs and worlds. This plan never moves a draft spec into
  `data/synth3/`, never draws or builds a world for law, materials or RAG, and never sets `approved`.
- **Git:** branch `synth3-real`. Stage files by name only; never stage `backend/agent/tests/test_prompts.py`.
  Never push or merge. End every commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Tests:** run `uv run pytest -q backend/synth3` per task, and the whole suite `uv run pytest -q` at the end of
  Tasks 1, 8 and 12.

## Review Focus

- **The control hidden in a table column:** real trial tables put "Placebo" in the header row, not in a data
  row. The whole table and its caption must go, or the real numbers for the control stay without a name
  (Task 7 test `test_control_tables_go_whole`).
- **Drug names in many forms:** "Amlodipine" at the start of a sentence, "amlodipine/valsartan",
  "amlodipine-based" and "AMLODIPINE" must all get the same invented name (Task 5 test).
- **An invented name that equals a planted name:** the renaming must never produce "Alvenor" or a setting name,
  and a planted name already in the real text must be deleted with its sentence (Task 5 and Task 7 tests).
- **A stopped or repeated fetch:** a second `pool-fetch` reuses the saved XML, asks NCBI only for missing
  papers and does not duplicate index rows; a 429 waits for its Retry-After (Task 3 tests).
- **Papers without the usual headings:** no "Results" or no "Discussion" heading, a numbered heading
  ("3. Results") or a structured abstract must still give one place for each insert and pass every check
  (Task 2 and Task 7 tests).
- **A title that names the control** ("A randomised, placebo-controlled trial of ...") is cleaned, not a reason
  to reject the source (Task 7 test).

---

### Task 1: Real-paper config per domain

**Files:**
- Create: `backend/synth3/realspec.py`, `backend/synth3/tests/test_realspec.py`
- Create: `data/synth3/real/medicine.yaml`
- Modify: `backend/synth3/tests/conftest.py` (add `real_good()`, `write_real(dir, d)` and the fixture `REAL`)
- Modify: `.gitignore` (add `data/synth3/pools/` under the synth3 comment)

**Interfaces:**
- Produces: `REAL_SPECS = SPECS / "real"` and `POOLS = SPECS / "pools"`.
- Produces: `RealSpec(Strict)` with these fields:
  - `domain`, `source: Literal["pmc", "files"]`, `query: str = ""`, `max_fetch: int = 600`;
  - `article_types: list[str]`, `exclude_title: str` (regex), `min_words: int`, `max_words: int`,
    `min_tables: int`;
  - `results_heading: str`, `conclusion_heading: str`, `drop_sections: str`, `control_words: str` (regexes,
    case-insensitive);
  - `keep: list[str]` (field words never renamed), `name_stems: list[str]`, `name_words: list[str]`
    (lower-case names to rename), `n_test: int = 30`, `sha256`.
- Produces: `RealSpec.banned(spec: DomainSpec) -> re.Pattern`: `control_words`, every arm label and every
  setting name, case-insensitive, whole words.
- Produces: `RealSpec.heading(kind: Literal["results", "conclusion"], line: str) -> bool`: the heading text
  without its `#`s and without a leading section number ("3.", "3.1", "IV.") matches the regex.
- Produces: `TEMPLATE_WORDS = ("SD",)`: words our own planted text prints that synth2 would treat as a name.
  `load_real_spec` refuses a config whose `keep` lacks one of them.
- Produces: `load_real_spec(domain: str, root: Path = REAL_SPECS) -> RealSpec`. Any problem is a `ValueError`
  that names the field. CRLF hashes as LF (as `synth3/spec.py`).

- [ ] **Step 1: Write the failing tests.** `real_good()` is a `files` config with every field set:
  `article_types` `[research-article]`, `exclude_title` `"protocol|review"`, `min_words` 100, `max_words`
  5000, `min_tables` 1, `n_test` 5, stems `["pril", "dipine"]`, words `["chlorthalidone"]`, keep
  `["BP", "eGFR", "WHO", "SD"]`, `control_words` `"placebo|usual care"`, and medicine's `results_heading`,
  `conclusion_heading` and `drop_sections` (Step 3). The fixture `REAL` writes it under `tmp_path / "real"`, so
  it never overwrites the `demo.yaml` that `SPEC` wrote.

```python
def test_medicine_real_config_loads():
    rs = load_real_spec("medicine")
    assert rs.source == "pmc" and "open access" in rs.query and rs.n_test == 30
    assert rs.banned(load_spec("medicine")).search("Patients given placebo improved.")

@pytest.mark.parametrize("change, words", [
    (lambda d: d.update(control_words="(unclosed"), "control_words"),
    (lambda d: d.update(min_words=9000), "min_words"),
    (lambda d: d.update(n_test=3), "n_test"),
    (lambda d: d.update(source="pmc", query=""), "query"),
    (lambda d: d.update(source="ftp"), "source"),
    (lambda d: d.update(name_stems=["Pril"]), "lower case"),
    (lambda d: d["keep"].remove("SD"), "SD"),
])
def test_refuses_bad_real_configs(tmp_path, change, words):
    d = real_good(); change(d)
    with pytest.raises(ValueError, match=words):
        load_real_spec("demo", write_real(tmp_path, d))

def test_banned_covers_control_words_labels_and_settings(SPEC, REAL):
    pat = REAL.banned(SPEC)
    assert pat.search("on usual care") and pat.search("the standard care arm")
    assert pat.search("at the Northern hospital network") and not pat.search("targeted at kidneys")

def test_numbered_headings_match(REAL):
    assert REAL.heading("results", "## 3. Results") and REAL.heading("conclusion", "## IV. Discussion")
```

- [ ] **Step 2: Run the tests to watch them fail.** Run `uv run pytest -q backend/synth3/tests/test_realspec.py`.
  Expected: FAIL with `ModuleNotFoundError: synth3.realspec`.
- [ ] **Step 3: Implement `realspec.py` and write `data/synth3/real/medicine.yaml`.** Rules: regexes compile;
  `0 < min_words < max_words`; `n_test >= 5` (the classifier uses 5 folds); `pmc` needs a query; stems and
  words are lower case; `keep` holds `TEMPLATE_WORDS`. The medicine values (builder's call; tune `query` in
  Task 11 only):
  - `query`: `"open access"[filter] AND hypertension[MeSH Terms] AND (randomized[Title/Abstract] OR
    randomised[Title/Abstract]) AND (antihypertensive[Title/Abstract] OR "blood pressure"[Title/Abstract])`;
  - `article_types` `[research-article]`; `exclude_title` `protocol|review|meta-analys|rationale and design|
    erratum|correction`; words 2000–9000; `min_tables` 1;
  - `results_heading` `^results?\b|^findings\b`; `conclusion_heading` `conclu|discussion|summary`;
  - `drop_sections` `acknowledg|funding|conflicts? of interest|competing interests?|declarations?|author.{0,3}
    contributions?|abbreviations|supplementary|data availability|availability of data|ethics approval|consent
    for publication`;
  - `control_words` `placebo|usual care|standard care|standard (?:treatment|therapy)|conventional
    (?:care|treatment|therapy)|control (?:group|arm)s?|untreated`;
  - `keep` at least: BP SBP DBP HR CI OR RR SD SE SEM IQR BMI eGFR CKD HbA1c LDL HDL ACE ARB ARBs CCB CCBs RAAS
    ECG ICU RCT ITT ANOVA SAS SPSS Stata WHO FDA NIH ESC ESH ACC AHA JNC NICE MRI CT ABPM NYHA NCT COVID-19
    Kaplan Meier Cox (common eponyms and acronyms; renaming them would be a cue only the synthetic side has);
  - `name_stems` at least: pril sartan olol alol dipine thiazide azosin semide tanide tiazem pamil kiren statin
    gliflozin gliptin formin glutide parin xaban gatran prazole; `name_words` at least: chlorthalidone
    indapamide spironolactone eplerenone clonidine hydralazine minoxidil methyldopa moxonidine.
- [ ] **Step 4: Run the tests**, then the whole suite `uv run pytest -q`. Check
  `git check-ignore data/synth3/pools/x` prints the path. Expected: PASS.
- [ ] **Step 5: Commit** `backend/synth3/realspec.py`, `backend/synth3/tests/test_realspec.py`,
  `backend/synth3/tests/conftest.py`, `data/synth3/real/medicine.yaml`, `.gitignore`:
  `synth3: real-paper config per domain`.

### Task 2: A JATS paper to one cleaned markdown shape

**Files:**
- Create: `backend/synth3/pmc.py` (conversion part), `backend/synth3/tests/test_pmc.py`
- Create: `backend/synth3/tests/fixtures/jats/trial.xml`, `review.xml` and `docling.md` (hand-written, small)

**Interfaces:**
- Consumes: `RealSpec`; `evidence.sources.pmc.jats_markdown`; `synth2.realpool.clean_text`, `words`.
- Produces: `PoolPaper` (frozen dataclass) with `id`, `title`, `year: int | None`, `journal`, `license`,
  `article_type` and `text`. The text shape, for every source:
  `# <title>\n\n## Abstract\n\n<paragraphs>\n\n## <section>\n\n...`; captions as plain `Table N. <caption>`
  paragraphs; markdown tables; no figures, no references, no back matter.
- Produces: `jats_paper(data: bytes) -> PoolPaper`. `ValueError` when not XML or no body. Its text already
  has plain captions.
- Produces: `tidy(text: str, rs: RealSpec) -> str`, which the pool calls for every source. It:
  - turns `\r\n` into `\n` and removes HTML comments (Docling writes `<!-- image -->`);
  - cuts the text at a `references` or `bibliography` heading;
  - names the abstract heading `## Abstract`, whatever its case;
  - drops sections whose heading matches `drop_sections` (with their subsections);
  - removes URLs (synth2's `apply_map` would otherwise turn them into invented GitHub links that only the
    synthetic side has);
  - turns any `**Table ...**` caption into a plain paragraph;
  - runs `clean_text` on every non-table block.
- Produces: `unfit(paper: PoolPaper, rs: RealSpec) -> str | None`: the first reason a paper cannot be a source
  or test paper, e.g. `"article type review-article"`, `"title excluded"`, `"1840 words"`, `"no table"`,
  `"no abstract"`, `"no results or conclusion heading"`; `None` when it fits.

`trial.xml`: article-type `research-article`, a PMC id, a structured abstract (Background, Methods, Results,
Conclusions), body sections Introduction / Methods / Results / Discussion / Funding, a `<fig>`, a
`<table-wrap>` whose header names Placebo, a second `<table-wrap>` nested inside a `<p>`, numeric
`<xref ref-type="bibr">` citations (one followed by the sentence "Treatment lowered the stroke rate in older
patients."), and a `<back>` with references; at least 150 words. `review.xml`: article-type `review-article`,
otherwise minimal. `docling.md`: a Docling-shaped paper with `## ABSTRACT`, `<!-- image -->`, a URL and a
`## References` section.

- [ ] **Step 1: Write the failing tests:**

```python
def test_structured_abstract_becomes_one_section_with_run_in_labels():
    p = jats_paper((FIX / "trial.xml").read_bytes())
    head = p.text.split("## Introduction")[0]
    assert head.count("## ") == 1 and "Background: " in head and "Conclusions: " in head

def test_figures_citations_and_back_matter_are_gone(REAL):
    text = tidy(jats_paper((FIX / "trial.xml").read_bytes()).text, REAL)
    assert "Figure 1" not in text and "## Funding" not in text and "References" not in text
    assert not re.search(r"\[\s*[,–-]?\s*\]|\(\s*\)", text)   # no empty brackets left by removed citations
    assert "Treatment lowered the stroke rate in older patients." in text   # the text after a citation stays

def test_a_table_inside_a_paragraph_stays_a_table():
    text = jats_paper((FIX / "trial.xml").read_bytes()).text
    assert len(re.findall(r"(?m)^Table \d+\. ", text)) == 2 and len(re.findall(r"(?m)^\|( --- \|)+$", text)) == 2

def test_tidy_cleans_docling_markdown(REAL):
    text = tidy((FIX / "docling.md").read_text(encoding="utf-8").replace("\n", "\r\n"), REAL)
    assert "## Abstract" in text and "<!--" not in text and "http" not in text
    assert "References" not in text and "\r" not in text

def test_metadata_and_plain_caption():
    p = jats_paper((FIX / "trial.xml").read_bytes())
    assert p.id.startswith("PMC") and p.year and p.article_type == "research-article"
    assert re.search(r"(?m)^Table 1\. ", p.text) and "**" not in p.text

def test_unfit_names_the_reason(REAL):
    assert unfit(jats_paper((FIX / "review.xml").read_bytes()), REAL) == "article type review-article"
    assert unfit(jats_paper((FIX / "trial.xml").read_bytes()), REAL) is None

def test_not_xml_is_a_value_error():
    with pytest.raises(ValueError, match="not XML"):
        jats_paper(b"<html")
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** Builder's call, and why: JATS is already structured, so converting it is exact and
  needs only the standard library and the converter the repo already tests
  (`evidence/sources/pmc.py`); Docling would add a PDF round trip and lose the exact table cells. Before calling
  `jats_markdown`, change the parsed tree:
  - **Remove** `fig`, `supplementary-material`, `fn-group`, `ref-list`, `ack` and every `xref` with
    `ref-type="bibr"`. `xml.etree` drops an element's `tail` (the text after it) with the element, so first add
    the tail to the previous sibling's tail, or to the parent's text when there is no previous sibling.
  - **Hoist** a `table-wrap` found inside a `p` out of it, placing it right after that `p` (with the same tail
    rule), so `jats_markdown` prints it as a table.
  - **Flatten** each abstract `sec` into one `p` whose text starts with `"<title>: "`.

  Serialise with `ET.tostring` and pass the bytes to `jats_markdown`. Then remove empty brackets left by the
  citations and turn the `**Table ...**` captions into plain paragraphs. Metadata: `article/@article-type`,
  `article-id[@pub-id-type='pmc' or 'pmcid']` (prefix `PMC`), the first `pub-date/year`, `journal-title`, the
  `license` href or text.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** the two files and the fixtures: `synth3: JATS papers in one cleaned markdown shape`.

### Task 3: Filling a pool: PMC fetch and file import

**Files:**
- Modify: `backend/synth3/pmc.py` (client, search, fetch)
- Create: `backend/synth3/pool.py` (layout, index, import), `backend/synth3/tests/test_pool_fetch.py`
- Modify: `backend/synth3/cli.py` (commands `pool-fetch` and `pool-import`)
- Modify: `backend/synth3/tests/conftest.py` (`fake_paper(i)` and the fixture `REAL_PMC`)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces (pmc.py): `EUTILS`, `TOOL = "synth3-pool"`, `USER_AGENT = "synth3-pool/1 (open-access corpus
  builder)"`, `DELAY_S = 1.0`, `BATCH = 20`, `BACKOFF_S = (5.0, 30.0, 60.0)`.
- Produces: `Polite(transport=None, delay=DELAY_S, sleep=time.sleep, clock=time.monotonic, log=...)` with
  `get(url: str, params: dict) -> bytes`. Requests are spaced by `delay`; a 429 or 503 waits for its
  `Retry-After` (else the next backoff) and tries again, then raises.
- Produces: `search(client: Polite, query: str, limit: int) -> list[str]` (PMC ids, in NCBI's order; esearch
  `db=pmc`, pages of 500) and `articles(data: bytes) -> list[bytes]` (one serialised `<article>` per article of
  an efetch `pmc-articleset`).
- Produces (pool.py): the layout of `POOLS/<domain>/`: `raw/<id>.xml` (PMC only), `full/<id>.md`, `index.json`
  (rows `{id, title, year, journal, license, words, tables, kept, why}`, sorted by id).
- Produces: `add_paper(pool: Path, paper: PoolPaper, rs: RealSpec) -> dict` (tidies, writes `full/<id>.md` only
  when it fits, returns the index row), `load_index(pool) -> list[dict]`, `save_index(pool, rows)`.
- Produces: `fetch_pool(rs: RealSpec, pool: Path, client: Polite) -> dict`: search `rs.max_fetch` ids; fetch in
  batches of `BATCH` only the ids that have neither a `raw/<id>.xml` nor an index row; then rebuild `full/` and
  `index.json` from every raw file. Each returned `<article>` is saved under its own PMC id (read from the
  article, not from the request order). A requested id with no article gets the index row
  `why: "not returned"` and is not asked for again. A `jats_paper` error (e.g. a publisher that allows no
  full-text XML: "no <body>") counts as an unfit reason. Returns `{"found", "fetched", "cached", "kept",
  "unfit": {reason: count}}`.
- Produces: `import_files(src: Path, pool: Path, rs: RealSpec, convert_pdf=None) -> dict`: `.md` as is (title =
  first `# ` line), `.xml` through `jats_paper`, `.pdf` through `convert_pdf` (default
  `evidence.arxiv.docling_markdown(data, "pdf")`, needs `uv sync --group fetch`). The id is the file stem.
  Article type is `"research-article"` for imports. Same return shape as `fetch_pool` without `found`.
- Produces: `synth3 pool-fetch --domain D [--real-root R] [--pools P]` and
  `synth3 pool-import --domain D --from DIR [--real-root R] [--pools P]` (`--from` with `dest="src"`, since
  `from` is a keyword); each prints `kept <k> of <n>`, the unfit reasons and the licence counts.

- [ ] **Step 1: Write the failing tests.** A `handler(request)` serves esearch XML listing ids `101`, `102` and
  `103`, and an efetch `pmc-articleset` with `review.xml` (as PMC102) first, then `trial.xml` (as PMC101); 103
  is not returned. It records every request. `clock` always returns 0.0, so every request after the first waits
  the full delay.

```python
def test_fetch_is_polite_and_sends_no_personal_detail(tmp_path, REAL_PMC):
    seen, waits = [], []
    client = Polite(transport=httpx.MockTransport(handler(seen)), sleep=waits.append, clock=lambda: 0.0)
    out = fetch_pool(REAL_PMC, tmp_path / "pool", client)
    assert all(r.url.params["tool"] == TOOL and "email" not in r.url.params for r in seen)
    assert all(r.headers["user-agent"] == USER_AGENT for r in seen)
    assert waits == [DELAY_S] * (len(seen) - 1)
    assert out["kept"] == 1 and out["unfit"] == {"article type review-article": 1, "not returned": 1}
    assert "Placebo" in (tmp_path / "pool" / "raw" / "PMC101.xml").read_text(encoding="utf-8")

def test_second_fetch_uses_saved_xml_and_keeps_one_row_per_paper(tmp_path, REAL_PMC):
    fetch_pool(REAL_PMC, tmp_path / "pool", Polite(transport=httpx.MockTransport(handler([])),
                                                  sleep=lambda s: None))
    seen = []
    out = fetch_pool(REAL_PMC, tmp_path / "pool", Polite(transport=httpx.MockTransport(handler(seen)),
                                                         sleep=lambda s: None))
    assert out["fetched"] == 0 and out["cached"] == 2 and not any("efetch" in str(r.url) for r in seen)
    assert len(load_index(tmp_path / "pool")) == 3

def test_429_waits_for_retry_after(tmp_path):
    answers = iter([httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200, content=b"<x/>")])
    waits = []
    client = Polite(transport=httpx.MockTransport(lambda r: next(answers)), sleep=waits.append, clock=lambda: 0.0)
    assert client.get(EUTILS + "esearch.fcgi", {}) == b"<x/>" and 2.0 in waits

def test_import_reads_markdown_xml_and_pdf(tmp_path, REAL):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.md").write_text(fake_paper(1), encoding="utf-8")
    shutil.copy(FIX / "trial.xml", src / "b.xml"); (src / "c.pdf").write_bytes(b"%PDF")
    out = import_files(src, tmp_path / "pool", REAL, convert_pdf=lambda data: fake_paper(2))
    assert out["kept"] == 3 and {r["id"] for r in load_index(tmp_path / "pool")} == {"a", "b", "c"}
```

  `REAL_PMC` is a conftest fixture: `real_good()` with `source: pmc` and a query. `fake_paper(i)` is a
  conftest helper (defined here, used again in Tasks 4–10): a markdown paper of about 1,500 words in
  paragraphs of 60–100 words (so the piece cutter finds windows of 800–1,100 words), with
  `# <title>`, `## Abstract`, `## Introduction` (about 600 words, with "in Brightford", a trial name
  `HOPE-<i>`, "Lisinopril" at a sentence start and "lisinopril/amlodipine"), `## Methods`, `## Results` (a
  sentence about placebo, a `Table 1. ...` caption and a table whose header names Placebo), `## Discussion`;
  the text varies with `i`.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** Write files with `jsonio.write_json_atomic` / `write_text_atomic`. Raw XML is
  untrusted data: parse it only with `xml.etree` (no entity fetching), never run it.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `pmc.py`, `pool.py`, `cli.py`, `test_pool_fetch.py`, `conftest.py`:
  `synth3: fill a pool from PMC or from files`.

### Task 4: The split, the source order and the real test pieces

**Files:**
- Modify: `backend/synth3/pool.py`, `backend/synth3/cli.py` (command `pool-split`)
- Create: `backend/synth3/tests/test_pool_split.py`
- Modify: `backend/synth3/tests/conftest.py` (`make_pool(root, n, rs) -> Path`: writes `n` fake papers with
  ids `P001…` through `add_paper`)

**Interfaces:**
- Produces: `split_pool(pool: Path, rs: RealSpec) -> dict`. It shuffles the kept ids (sorted first) with
  `Random(f"synth3:pool:{rs.domain}:split")`. The first `rs.n_test` are `test`, the rest `sources`. It writes
  `split.json` `{seed, test, sources, counts, sha256}` (sha256 of the canonical lists) and the test pieces
  `pieces/<id>_pN.md` + `pieces/index.json`, cut with `md_blocks`, `cut_pieces` and `write_pieces`. It refuses
  an existing `split.json` ("refusing to overwrite: a new split could move test papers into sources") and a
  pool with fewer than `n_test + 1` kept papers.
- Produces: `load_split(pool: Path) -> dict` (`ValueError` "run synth3 pool-split first" when missing).
- Produces: `source_order(split: dict, domain: str) -> list[str]`: the sources shuffled with
  `Random(f"synth3:pool:{domain}:sources")`.
- Produces: `folder_sources(order: list[str], seed: int, n: int) -> list[str]`: `order` rotated to start at
  `((seed - 1) * n) % len(order)`. The first `n` are the folder's sources; the rest, in order, are reserves.
  `ValueError("pool has <k> source papers; a folder of <n> studies needs at least <n>")` when `len(order) < n`.
- Produces: `synth3 pool-split --domain D [--real-root R] [--pools P]`, printing the counts.

- [ ] **Step 1: Write the failing tests:**

```python
def test_split_is_seeded_disjoint_and_never_overwritten(tmp_path, REAL):
    pool = make_pool(tmp_path / "p", 20, REAL)
    s = split_pool(pool, REAL)
    assert len(s["test"]) == REAL.n_test and not set(s["test"]) & set(s["sources"])
    with pytest.raises(ValueError, match="refusing to overwrite"):
        split_pool(pool, REAL)

def test_same_pool_same_split(tmp_path, REAL):
    a = split_pool(make_pool(tmp_path / "a", 20, REAL), REAL)
    b = split_pool(make_pool(tmp_path / "b", 20, REAL), REAL)
    assert a["test"] == b["test"]

def test_test_papers_are_cut_into_pieces(tmp_path, REAL):
    pool = make_pool(tmp_path / "p", 20, REAL); s = split_pool(pool, REAL)
    index = json.loads((pool / "pieces" / "index.json").read_text())
    assert index and {x["paper"] for x in index} <= set(s["test"])

def test_big_pool_gives_disjoint_folders():
    order = [f"P{i:03d}" for i in range(200)]
    blocks = [folder_sources(order, s, 40)[:40] for s in range(1, 6)]
    assert all(len(set(b)) == 40 for b in blocks) and len(set().union(*blocks)) == 200

def test_small_pool_repeats_across_folders_never_within():
    order = [f"P{i:03d}" for i in range(60)]
    assert all(len(set(folder_sources(order, s, 40)[:40])) == 40 for s in range(1, 6))
    with pytest.raises(ValueError, match="needs at least 40"):
        folder_sources(order[:30], 1, 40)
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: pool split, source order and real test pieces`.

### Task 5: Renaming for a domain

**Files:**
- Create: `backend/synth3/rename.py`, `backend/synth3/tests/test_rename.py`

**Interfaces:**
- Consumes: `RealSpec`; `build_map`, `apply_map`, `surviving`, `_new_part`, `SURNAME_POOL` from
  `synth2.realedit`.
- Produces: `lower_names(rs: RealSpec) -> re.Pattern`: whole words ending in a stem (with at least 3 letters
  before it) or equal to a name word, case-insensitive.
- Produces: `rename_source(text: str, rs: RealSpec, seed: str, avoid: set[str]) -> tuple[str, dict[str, str]]`.
  It returns the renamed text and the map real → invented (drug names in lower case). The steps, in this
  order (drug names first, or synth2 would treat "AMLODIPINE-based" as an acronym and rename it by shape):
  1. **Rename drug names:** each `lower_names` match splits into a prefix and its stem (the longest matching
     stem, else the last 3 letters). The prefix gets `_new_part(prefix.lower(), seed, taken)`; the stem is kept
     ("amlodipine" → e.g. "brelodipine"). Case follows the original: lower, Capitalised or UPPER. The same
     real word always gets the same invented word in a paper.
  2. **Protect** each `rs.keep` word (whole word, case-sensitive) and each invented drug name (every case form)
     with a lower-case placeholder made of letters only (e.g. `qqkeepbqq`), so synth2's renaming never sees it.
  3. **Rename names** with `build_map(text, seed)`. Before `apply_map`, any mapped value with a word (lower case)
     in `avoid` is replaced: a cited surname by the next name of `SURNAME_POOL` (shuffled with
     `Random(seed + "|avoid")`) that is not in `avoid` and not already a value, any other name by
     `_new_part`. Then `apply_map`.
  4. **Restore** the placeholders.

  `avoid` is a set of lower-case words. The caller passes every word of the arm labels, the setting names and
  the surnames of every spec author (not only this study's). An invented drug name whose lower-case form is in
  `avoid` is drawn again.
- Produces: `names_left(text: str, mapping: dict[str, str], rs: RealSpec) -> list[str]`: `surviving(text,
  mapping)` plus every `lower_names` match that is not an invented name of the map.

- [ ] **Step 1: Write the failing tests:**

```python
SRC = ("# Lisinopril in HOPE-3\n\n## Abstract\n\nPatients in Brightford took lisinopril. "
       "Lisinopril/amlodipine lowered BP and eGFR held. LISINOPRIL-based care was compared, as WHO advises.\n")

def test_drug_names_get_one_invented_name_in_every_form(REAL):
    text, m = rename_source(SRC, REAL, "s1", set())
    new = m["lisinopril"]
    assert new.endswith("pril") and new != "lisinopril"
    for form in (new, new.capitalize(), new.upper()):
        assert form in text
    assert m["amlodipine"].endswith("dipine") and names_left(text, m, REAL) == []

def test_keep_words_stay_and_other_names_go(REAL):
    text, m = rename_source(SRC, REAL, "s1", set())
    assert all(w in text for w in ("BP", "eGFR", "WHO"))
    assert "HOPE-3" not in text and "Brightford" not in text and unsayable(m) == []

def test_same_seed_same_text_and_a_new_seed_a_new_text(REAL):
    assert rename_source(SRC, REAL, "s1", set()) == rename_source(SRC, REAL, "s1", set())
    assert rename_source(SRC, REAL, "s1", set())[0] != rename_source(SRC, REAL, "s2", set())[0]

def test_invented_names_avoid_planted_words(REAL):
    first = rename_source(SRC, REAL, "s1", set())[1]["lisinopril"]
    again = rename_source(SRC, REAL, "s1", {first})[1]["lisinopril"]
    assert again != first and again.endswith("pril")

def test_a_cited_author_never_takes_a_planted_author_surname(REAL):
    src = SRC + "\nAs Smith et al. (2010) showed, doses matter.\n"
    first = rename_source(src, REAL, "s1", set())[1]["Smith"]
    text, m = rename_source(src, REAL, "s1", {first.lower()})
    assert m["Smith"] != first and first not in text and m["Smith"] in text
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: renaming for a domain, drug names included`.

### Task 6: The planted blocks, with their placements

**Files:**
- Modify: `backend/synth3/write.py` (move the Results rows of `write_paper` into
  `results_block(b: _Builder, study, spec, text_level) -> None`; `write_paper` calls it; no output change)
- Create: `backend/synth3/realwrite.py` (blocks part), `backend/synth3/tests/test_realwrite_blocks.py`
- Modify: `backend/synth3/tests/conftest.py` (`supported`, and `approved` moved here) and
  `backend/synth3/tests/test_corpus.py` (uses the conftest `approved`)

**Interfaces:**
- Consumes: `results_block`, `_claim_sentence`, `_fact_claim` (same package), `Paper`, `Placement`, `_Builder`.
- Produces: `planted_section(study, spec, text_level: str, seed: str, table_no: int) -> Paper`. It holds:
  - a `### ` heading;
  - an intro paragraph that says what each arm is (`"<label> is <description>."`) and plants
    `<sid>.setting` in a sentence about where this comparison was run;
  - for `table`, a caption paragraph `Table <table_no>. ...`;
  - the `results_block` rows;
  - one closing sentence with no numbers and no claim.

  The text is stripped (no leading or trailing whitespace), so it can be found again after insertion.
- Produces: `claims_block(study, spec, place: Literal["abstract", "conclusion"], seed: str) -> Paper`: a lead
  sentence from that place's own list (never optional, so the two blocks always differ and neither is a part of
  the other), then every claim of the study as the exact `_claim_sentence`, planted under
  `_fact_claim(sid, key, place)`.
- Produces: template lists `HEADINGS`, `INTROS`, `CAPTIONS`, `CLOSERS`, `ABSTRACT_LEADS`, `CONCLUSION_LEADS`
  (at least 3 each, words only, domain-neutral: "arm", "group", "measure", never a field word; no lead appears
  in both lead lists). Choices come from `Random(f"{seed}|section")` and `Random(f"{seed}|{place}")`.

- [ ] **Step 1: Pin the template folders before any change.** Move `approved` into conftest. Create
  `test_realwrite_blocks.py` holding only the pin test below (`sha256_hex` from `jsonio`), with both ids set to `"?"`, and no import of `realwrite` yet. Run it, copy the 4 values from
  the failure messages, run again. Expected: PASS. The pin covers the `write.py` refactor here and the
  `corpus.py` refactor in Task 8; `corpus.json` is not pinned because it holds the code hash, which changes
  with every new module.

```python
PINS = {"table": ("?", "?"), "prose": ("?", "?")}   # (corpus id, sha256 of ground_truth.json + manifest.json)

@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_template_folders_unchanged_by_the_refactors(tmp_path, SPEC, level):
    out = tmp_path / level
    cid = build_folder(out, SPEC, approved(SPEC, 1), 40, level)
    digest = sha256_hex((out / "ground_truth.json").read_bytes() + (out / "manifest.json").read_bytes())
    assert (cid, digest) == PINS[level]
```

- [ ] **Step 2: Write the other failing tests:**

```python
@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_section_plants_the_same_values_as_the_template(SPEC, level):
    s = supported(SPEC, 1)[0]
    block = planted_section(s, SPEC, level, "x", 3)
    template = write_paper(s, SPEC, level, 1)
    got = {p.fact: block.text[p.start:p.end] for p in block.placements}
    want = {p.fact: template.text[p.start:p.end] for p in template.placements if ".claim." not in p.fact}
    assert got == want and block.text == block.text.strip()

def test_claim_blocks_hold_the_exact_claim_sentences(SPEC):
    s = supported(SPEC, 2)[0]
    for place in ("abstract", "conclusion"):
        block = claims_block(s, SPEC, place, "x")
        got = {p.fact: block.text[p.start:p.end] for p in block.placements}
        assert got == {_fact_claim(s.id, k, place): _claim_sentence(SPEC, k, w) for k, w in s.claims.items()}
    a, c = (claims_block(s, SPEC, p, "x").text for p in ("abstract", "conclusion"))
    assert a not in c and c not in a

def test_only_planted_numbers_and_the_table_number_are_digits(SPEC):
    s = supported(SPEC, 3)[0]
    block = planted_section(s, SPEC, "prose", "x", 3)
    spans = [(p.start, p.end) for p in block.placements]
    for m in re.finditer(r"\d+(?:\.\d+)?", block.text):
        assert any(a <= m.start() and m.end() <= b for a, b in spans)
    assert not re.search(r"\b(ctrl|m1|m2|m3|S\d{3})\b", block.text)

def test_wording_varies_with_the_seed(SPEC):
    s = supported(SPEC, 1)[0]
    assert len({planted_section(s, SPEC, "table", f"x{k}", 3).text.split("\n")[0] for k in range(12)}) >= 2
```

  `supported(SPEC, seed)` is a conftest helper: `draw_supported_studies(SPEC, draw_world(SPEC, seed), seed,
  40)[0]`. `approved` moves from `test_corpus.py` into conftest.
- [ ] **Step 3: Run the tests to watch them fail.** Expected: FAIL with `ImportError` on `realwrite`.
- [ ] **Step 4: Implement** the refactor and the blocks.
- [ ] **Step 5: Run the tests.** Expected: PASS, the pin test included.
- [ ] **Step 6: Commit**: `synth3: planted section and claim blocks for real papers`.

### Task 7: The real edit of one study, and its checks

**Files:**
- Modify: `backend/synth3/realwrite.py` (edit part)
- Create: `backend/synth3/tests/test_realwrite_edit.py`

**Interfaces:**
- Consumes: Tasks 5–6; `apply_edits`, `META`, `MAX_INSERTED` from `synth2.realedit`; `missing_facts`.
- Produces: `MAX_SEEDS = 10`, `MIN_REAL_SHARE = 0.65` (builder's call: synth2 v11 papers were about 90% real).
- Produces: `clean_block(block: str, banned: re.Pattern) -> str | None`, the same rules as
  `synth2.templedit._clean_block` with `banned` instead of the RAG words, plus: a table whose header row matches
  is dropped whole (`""`). A `Table N. ...` caption is dropped when its table is dropped.
- Produces: `clean_title(title: str, banned: re.Pattern) -> str | None`: the title without the words that name
  the control or a planted name. It drops the matching hyphenated word or phrase and the comma or "and"/"versus"
  joint it leaves ("A randomised, placebo-controlled trial of X" → "A randomised trial of X"; "X versus usual
  care in older adults" → "X in older adults"). It returns `None` when fewer than 3 words are left.
- Produces: `make_edits(renamed: str, study, spec, rs, text_level, seed: str) -> tuple[dict, list[Paper]]`. It
  returns the synth2 edits dict (`title`, `replace`, `insert_after`) and the three blocks it inserts. The title
  is `clean_title` of the renamed title; `None` is a problem "title names the control" (the source is then
  rejected). The anchors (headings matched with `rs.heading`, so "3. Results" counts):
  - **Abstract claims:** after the last paragraph under `## Abstract`.
  - **Section:** after the last block of the section whose heading is a results heading; else before the last
    conclusion heading; else after the last block.
  - **Conclusion claims:** after the first paragraph under the last conclusion heading; else after the section.

  When an anchor is not unique in the text, the previous unique block is used. `table_no` is one more than the
  number of `Table N.` captions left.
- Produces: `RealPaper` (frozen dataclass) with `paper: Paper`, `mapping: dict[str, str]`,
  `inserted: tuple[str, str, str]` (abstract claims, section, conclusion claims), `problems: tuple[str, ...]`,
  `seed: str`.
- Produces: `avoid_words(spec) -> set[str]`: every word, lower case, of the arm labels, the setting names and
  the surnames of every spec author.
- Produces: `edit_study(source: str, study, spec, rs, text_level: str, seed: str) -> RealPaper`, with
  `avoid = avoid_words(spec)`. For `k in range(MAX_SEEDS)`,
  with `s = seed if k == 0 else f"{seed}:{k}"`:
  1. `rename_source(source, rs, s, avoid)`;
  2. `make_edits`;
  3. `apply_edits(renamed, edits, study.label)`;
  4. placements: each block found once in the paper, its placements shifted by that offset;
  5. `check_real_paper`.

  It returns the first try with no problems, else the last try (with its problems).
- Produces: `check_real_paper(paper: Paper, inserted, study, spec, rs, mapping) -> list[str]`. "The real
  text" below is the paper without line 3 (the label) and without the three inserted blocks; our own text is
  never searched for real names, so a word like "SD" in our table header cannot sink a source. The problems:
  - `missing_facts` not empty;
  - the label is not the third line;
  - `names_left` in the real text;
  - a spec author surname in the real text (a cited author that looks like a planted study);
  - `unsayable(mapping)`;
  - `banned` text in the real text, the title included;
  - a block that is not found exactly once;
  - more than `MAX_INSERTED` inserted words, or a real share below `MIN_REAL_SHARE`. The real share is the
    words of the real text without the title, divided by all words of the paper;
  - a `META` word in the inserted text.

- [ ] **Step 1: Write the failing tests:**

```python
def edit(SPEC, REAL, i=1, source=None, level="table"):
    s = supported(SPEC, 1)[0]
    return s, edit_study(source or fake_paper(i), s, SPEC, REAL, level, f"synth3:1:real:{s.id}")

@pytest.mark.parametrize("level", TEXT_LEVELS)
def test_real_paper_keeps_every_planted_fact(SPEC, REAL, level):
    s, rp = edit(SPEC, REAL, level=level)
    assert rp.problems == () and missing_facts(rp.paper, s, SPEC) == []

def test_control_tables_go_whole(SPEC, REAL):
    _, rp = edit(SPEC, REAL)
    rest = rp.paper.text
    for t in rp.inserted:
        rest = rest.replace(t, " ")
    assert not REAL.banned(SPEC).search(rest) and "| Placebo" not in rp.paper.text

def test_inserts_land_in_abstract_results_and_discussion(SPEC, REAL):
    s, rp = edit(SPEC, REAL)
    t = rp.paper.text
    abstract = t[t.index("## Abstract"):t.index("## Introduction")]
    assert _claim_sentence(SPEC, *next(iter(s.claims.items()))) in abstract
    assert t.index(rp.inserted[1]) < t.index("## Discussion") < t.index(rp.inserted[2])
    assert t.split("\n")[2] == s.label

def test_paper_with_only_abstract_and_introduction(SPEC, REAL):
    bare = fake_paper(2).split("## Methods")[0]
    s, rp = edit(SPEC, REAL, source=bare)
    assert rp.problems == () and rp.paper.text.rstrip().endswith(rp.inserted[2].rstrip())

def test_a_planted_name_in_the_real_text_is_cut_with_its_sentence(SPEC, REAL):
    src = fake_paper(3).replace("## Discussion\n\n", "## Discussion\n\nTargeted therapy was popular. ")
    _, rp = edit(SPEC, REAL, source=src)
    assert rp.problems == () and "Targeted therapy was popular" not in rp.paper.text

def test_a_title_naming_the_control_is_cleaned_not_rejected(SPEC, REAL):
    src = "# A randomised, placebo-controlled trial of lisinopril in older adults\n" + fake_paper(4).split("\n", 1)[1]
    _, rp = edit(SPEC, REAL, source=src)
    line1 = rp.paper.text.split("\n")[0]
    assert rp.problems == () and not REAL.banned(SPEC).search(line1) and line1.startswith("# A randomised trial of")

def test_numbered_headings_and_template_words_do_not_sink_a_source(SPEC, REAL):
    src = (fake_paper(5).replace("## Results", "## 3. Results").replace("## Discussion", "## 4. Discussion")
           + "\nValues are given as mean and SD throughout.\n")
    bare_keep = REAL.model_copy(update={"keep": ["BP", "eGFR", "WHO"]})   # no SD: the real "SD" gets renamed
    _, rp = edit(SPEC, bare_keep, source=src, level="prose")              # yet our "(SD ...)" must not count
    t = rp.paper.text
    assert rp.problems == () and t.index(rp.inserted[1]) < t.index("## 4. Discussion")

def test_every_try_failing_returns_the_problems(SPEC, REAL, monkeypatch):
    monkeypatch.setattr(realwrite, "check_real_paper", lambda *a: ["always"])
    _, rp = edit(SPEC, REAL)
    assert rp.problems == ("always",) and rp.seed.endswith(f":{MAX_SEEDS - 1}")
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** Section headings are level-2 lines (`## `) for which `rs.heading` is true; a
  structured abstract is one `## Abstract` section after Task 2.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: real edit of one study with its checks`.

### Task 8: Real folders and the `build-real` command

**Files:**
- Modify: `backend/synth3/corpus.py` (move the file writing of `build_folder` into
  `write_folder(out, spec, world, drawn, attempt, papers, settings: dict, prefix: str, extra: dict) -> str`;
  `build_folder` calls it with `prefix="3"`, `extra={}`; no output change)
- Create: `backend/synth3/realcorpus.py`, `backend/synth3/tests/test_realcorpus.py`
- Modify: `backend/synth3/cli.py` (command `build-real`)
- Modify: `backend/synth3/tests/conftest.py` (fixtures `pool`, `real_dir`, `pool_root`)

**Interfaces:**
- Consumes: Tasks 1–7; `draw_supported_studies`, `missing_facts`.
- Produces: `build_real_folder(out: Path, spec, world, studies: int, text_level: str, rs: RealSpec, pool: Path)
  -> str`.
  - It refuses what `build_folder` refuses (unapproved world, non-empty `out`, bad text level).
  - It refuses a missing split and a pool too small (`folder_sources`).
  - It draws the same studies as `build_folder` (`draw_supported_studies`). In study order, each study takes
    the next unused id of `folder_sources(source_order(split, rs.domain), world.seed, studies)` and runs
    `edit_study` with `seed = f"synth3:{world.seed}:real:{sid}:{source_id}"`. A study whose source still has
    problems takes the next unused source, at most 3 sources per study; then a `ValueError` names the study and
    the first problem of each source. Nothing is written before every paper passes.
  - It writes through `write_folder` with `prefix="3r"`:
    - `papers/S*.md` and `manifest.json` as before;
    - `corpus.json` with `settings` `{seed, studies, text_level, attempt, real: true}`;
    - `ground_truth.json` with the template keys plus `real`: `{real_spec_sha256, split_sha256, sources: {sid:
      source id}, rejected: {sid: [{source, problem}]}, words: {sid: n}, inserted_words: {sid: n}}`;
    - beside them `real/maps/<sid>.json` (real names, private) and `real/inserted/<sid>.json`.
  - It returns the folder id `"<domain>3r-<8 hex>"`.
- Produces: `synth3 build-real --domain D --seeds ... --out O [--studies 40] [--text-level table]
  [--spec-root S] [--worlds W] [--real-root R] [--pools P]`. It checks every seed first (as `build` does), then prints
  `s<seed>: <id> (attempt <a>, <r> sources rejected) -> <folder>`.

- [ ] **Step 1: Write the failing tests** (`pool` is a conftest fixture: `make_pool(tmp_path / "pool", 50,
  REAL)` then `split_pool`; 45 sources):

```python
def test_real_truth_is_the_template_truth(tmp_path, SPEC, REAL, pool):
    build_folder(tmp_path / "t", SPEC, approved(SPEC, 1), 40, "table")
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    t, r = (json.loads((tmp_path / x / "ground_truth.json").read_text()) for x in ("t", "r"))
    assert set(r) == set(t) | {"real"}
    assert all(r[k] == t[k] for k in ("world", "spec", "studies", "facts"))
    assert {(p["paper"], p["fact"]) for p in r["placements"]} == {(p["paper"], p["fact"]) for p in t["placements"]}

def test_every_placement_points_at_its_planted_text(tmp_path, SPEC, REAL, pool):
    build_folder(tmp_path / "t", SPEC, approved(SPEC, 2), 40, "table")
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 2), 40, "table", REAL, pool)
    def spans(d):
        g = json.loads((d / "ground_truth.json").read_text())
        text = {p.stem: p.read_text(encoding="utf-8") for p in (d / "papers").glob("S*.md")}
        return {(p["paper"], p["fact"]): text[p["paper"]][p["start"]:p["end"]] for p in g["placements"]}
    assert spans(tmp_path / "r") == spans(tmp_path / "t")

def test_sources_unique_in_a_folder_and_never_test_papers(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    used = list(json.loads((tmp_path / "r" / "ground_truth.json").read_text())["real"]["sources"].values())
    assert len(used) == len(set(used)) == 40 and not set(used) & set(load_split(pool)["test"])

def test_same_world_same_bytes(tmp_path, SPEC, REAL, pool):
    for x in ("a", "b"):
        build_real_folder(tmp_path / x, SPEC, approved(SPEC, 3), 40, "table", REAL, pool)
    files = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    assert files and all((tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes() for f in files)

def test_pool_without_split_or_too_small_is_refused(tmp_path, SPEC, REAL):
    bare = make_pool(tmp_path / "bare", 50, REAL)
    with pytest.raises(ValueError, match="pool-split"):
        build_real_folder(tmp_path / "r1", SPEC, approved(SPEC, 1), 40, "table", REAL, bare)
    small = make_pool(tmp_path / "small", 30, REAL); split_pool(small, REAL)
    with pytest.raises(ValueError, match="needs at least 40"):
        build_real_folder(tmp_path / "r2", SPEC, approved(SPEC, 1), 40, "table", REAL, small)

def test_build_real_by_command(tmp_path, spec_dir, real_dir, pool_root):
    common = ["--domain", "demo", "--spec-root", str(spec_dir), "--seeds", "1", "--worlds", str(tmp_path / "w")]
    assert main(["draw", *common]) == 0
    f = tmp_path / "w" / "demo" / "s1.json"; d = json.loads(f.read_text()); d["approved"] = True
    f.write_text(json.dumps(d))
    assert main(["build-real", *common, "--real-root", str(real_dir), "--pools", str(pool_root),
                 "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "s1" / "real" / "maps").is_dir()
```

  `real_dir` writes `real_good()` as `demo.yaml`; `pool_root` holds a split `demo` pool.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** Hash `real_spec_sha256` and `split_sha256` from the loaded config and
  `split.json`.
- [ ] **Step 4: Run the tests**, then the whole suite `uv run pytest -q`. Expected: PASS (including
  `test_corpus.py` and Task 6's pin test, which now also covers the `write_folder` refactor).
- [ ] **Step 5: Commit**: `synth3: real folders and the build-real command`.

### Task 9: The realism check

**Files:**
- Create: `backend/synth3/realism.py`, `backend/synth3/tests/test_realism.py`
- Modify: `backend/synth3/cli.py` (command `realism`)
- Modify: `backend/README.md` (Run block: one line each for `pool-fetch`, `pool-import`, `pool-split`,
  `build-real` and `realism`)

**Interfaces:**
- Consumes: `c2st`, `style_gap` from `synth2.realism`; `slice_papers` from `synth2.realpool`; the pool's test
  pieces (Task 4).
- Produces: `domain_mask(text: str, rs: RealSpec, spec: DomainSpec) -> str`. It replaces with ` ARMNAME `,
  case-insensitive:
  - every `lower_names` match (real and invented drug names alike, since both keep the stem);
  - every arm label;
  - every `rs.control_words` match. The synthetic side has these deleted and says "Standard care" instead, so
    unmasked they would be a free cue, as synth2 masked its control words (`SYS_C`).

  Every setting name becomes ` SITE `. Real and synthetic papers then look the same on these words.
- Produces: `realism_report(folder: Path, pool: Path, rs, spec, work: Path, c2st=None, style_gap=None)
  -> dict`. `None` means synth2's own, imported inside the function so scikit-learn loads only when used. It:
  1. slices the folder's papers into `work/raw/synthetic/papers/` (`slice_papers`);
  2. copies the pool's test pieces to `work/raw/real/`;
  3. writes `domain_mask`ed copies of both under `work/masked/`;
  4. returns `{"pieces": {"real", "synthetic"}, "raw": c2st(raw), "masked": c2st(masked),
     "style gap": style_gap(raw real, {"folder": raw synthetic}), "synth2 template v2": {...}}`.

  The last entry is the reference numbers, as constants: AUC full 0.913, masked 0.742, function 0.572, surface
  0.575, masked + surface 0.606; style gap 0.12.
- Produces: `synth3 realism --domain D --folder F --out FILE [--pools P] [--real-root R] [--spec-root S]`. It
  writes the JSON and prints the two AUC tables. There is no pass mark (builder's call: realism is reported,
  as for synth2, not a gate).

- [ ] **Step 1: Write the failing tests:**

```python
def test_mask_hides_drug_arm_control_and_setting_names(SPEC, REAL):
    out = domain_mask("lisinopril beat brelopril, placebo and usual care, and Targeted therapy at the "
                      "Coastal health service", REAL, SPEC)
    assert not re.search(r"(?i)pril|placebo|usual care|Targeted therapy|Coastal", out)
    assert out.count("ARMNAME") == 5 and "SITE" in out

def test_report_feeds_both_sides_raw_and_masked(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    calls = []
    def fake(real_dir, syn_root, log=None):
        calls.append((sorted(p.name for p in real_dir.glob("*_p*.md")),
                      sorted(p.name for p in (syn_root / "papers").glob("S*_p*.md")),
                      " ".join(p.read_text(encoding="utf-8") for p in (syn_root / "papers").glob("*.md"))))
        return {"auc": {}}
    out = realism_report(tmp_path / "r", pool, REAL, SPEC, tmp_path / "w", c2st=fake, style_gap=lambda *a: {})
    assert len(calls) == 2 and calls[0][0] and calls[0][1]
    assert {n.split("_p")[0] for n in calls[0][0]} <= set(load_split(pool)["test"])
    labels = [a.label for a in SPEC.arms]
    assert any(l in calls[0][2] for l in labels) and not any(l in calls[1][2] for l in labels)
    assert set(out) == {"pieces", "raw", "masked", "style gap", "synth2 template v2"}
```

- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** Import `synth2.realism` inside `realism_report` and the command, as
  `synth2/cli.py:256` does (scikit-learn is heavy).
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: realism check against the pool's test papers`.

### Task 10: The blind reader (built and tested with fakes; Aditya runs it)

Spec §10b names two realism checks: the classifier (Task 9) and a blind reader. synth2's reader was run outside
the repo, and `realedit.check_base` only reads its RAG-shaped notes, so synth3 gets its own reader. It reuses
the repo's model call (`modelcall.ask_sync`, as `synth/draft.py` does). The model only reads; code does every
comparison (`docs/prompt-writing.md`: separate generation and verification, with verification on a sub-model).

**Files:**
- Create: `backend/synth3/reader.py`, `backend/synth3/prompts/reader-v1.txt`, `backend/synth3/tests/test_reader.py`
- Modify: `backend/synth3/cli.py` (command `reader`), `backend/README.md` (one Run line for `reader`)

**Interfaces:**
- Consumes: `modelcall` (`ask_sync`, `load_prompt`, `JsonlCache`, `default_key`, `CallSettings`),
  `modelcall.gateway.openai_model`; the folder's `ground_truth.json` and papers.
- Produces: the reply type `ReaderNotes(Strict)`:
  - `label: str`, `setting: str | None`;
  - `results: list[Row]`, where `Row` has `arm: str`, `subgroup: list[str]` (the level names as written),
    `measure: str`, `k: int | None`, `n: int`, `mean: float | None`, `sd: float | None` and `quote: str`;
  - `claims: list[Claim]`, where `Claim` has `arm`, `against`, `measure`, `direction` (`helps` / `hurts` /
    `no_effect`, where "helps" means better on that measure) and `quote`.
- Produces: `read_paper(text: str, spec, model, cache: JsonlCache) -> ReaderNotes`. The user prompt is the
  paper text plus the domain's measure names and units. It never contains arm labels, settings or values, so
  the reader is blind to what was planted.
- Produces: `check_notes(notes: ReaderNotes, study, spec, text: str) -> dict`, returning
  `{"ok", "problems", "other_results"}`. The problems:
  - a label or setting that differs from the study's;
  - a quote that is not in the paper (spaces squashed);
  - a planted row missing or with other values (count `k`/`n` exact; mean and sd rounded to the measure's
    `decimals`; subgroup level names mapped to level ids case-insensitively);
  - a row naming a planted arm that is not planted (real text that contradicts the truth);
  - a planted claim missing or with another direction.

  Rows for other names are counted in `other_results`.
- Produces: `read_folder(folder: Path, spec, model, cache: Path) -> dict`. It writes
  `real/reader.json` (the notes per paper) and `real/reader-check.json` (`check_notes` per paper plus
  `{"papers", "ok", "other_results"}`), and returns the summary.
- Produces: `synth3 reader --domain D --folder F [--model sub-model-1] [--spec-root S]`. The model is
  `openai_model(alias)`; the cache is `F/real/reader-calls.jsonl`. It prints `ok <k> of <n>, <m> other
  results`.
- Prompt `reader-v1.txt`: the task first (list every result and every overall claim the paper reports for
  each treatment group, with a verbatim quote), then the inputs, the output fields, and three examples:
  - a normal count row;
  - a confusing case: a lower-is-better measure worded "reduces side effects" = `helps`, and a percentage
    printed next to the count (report the count);
  - a missing case: no SD printed, so `sd` is null.

  `load_prompt` hashes the prompt into the cache key.

- [ ] **Step 1: Write the failing tests.** `perfect(study, spec, folder)` builds the `ReaderNotes` a perfect reader
  would give from the truth (quotes cut from the paper by placement). `scripted(*notes)` is a pydantic-ai
  `FunctionModel` that returns them in order, as in `backend/synth/tests/test_draft.py:47-57`.

```python
def test_a_perfect_reader_passes_every_paper(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    truth = json.loads((tmp_path / "r" / "ground_truth.json").read_text(encoding="utf-8"))
    studies = [Study.parse(s) for s in truth["studies"]]
    out = read_folder(tmp_path / "r", SPEC, scripted(*[perfect(s, SPEC, tmp_path / "r") for s in studies]),
                      tmp_path / "calls.jsonl")
    assert out["ok"] == out["papers"] == 40

def test_a_missing_row_a_false_quote_and_a_contradiction_are_named(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    s = supported(SPEC, 1)[0]
    text = (tmp_path / "r" / "papers" / f"{s.id}.md").read_text(encoding="utf-8")
    good = perfect(s, SPEC, tmp_path / "r")
    dropped = good.model_copy(update={"results": good.results[1:]})
    fake = good.model_copy(update={"claims": [good.claims[0].model_copy(update={"quote": "never said"})]})
    extra = good.model_copy(update={"results": [*good.results, good.results[0].model_copy(update={"n": 7})]})
    assert any("missing" in p for p in check_notes(dropped, s, SPEC, text)["problems"])
    assert any("quote" in p for p in check_notes(fake, s, SPEC, text)["problems"])
    assert any("not planted" in p for p in check_notes(extra, s, SPEC, text)["problems"])

def test_the_prompt_input_hides_the_planted_names(tmp_path, SPEC):
    seen = []
    model = FunctionModel(lambda messages, info: seen.append(messages) or reply(empty_notes()))
    read_paper("# T\n\nSome text.", SPEC, model, JsonlCache(tmp_path / "c.jsonl"))
    sent = str(seen[0])
    assert all(a.label not in sent for a in SPEC.arms) and all(m.name in sent for m in SPEC.measures)
```

  `reply` and `empty_notes` are small helpers in the test file. `Study.parse` is plan 1's.
- [ ] **Step 2: Run the tests to watch them fail.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement.** No test opens a socket or calls the cluster.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**: `synth3: blind reader for real folders, tested with fake models`.

### Task 11: Medicine: the pool, 5 real folders, the realism report

**Files:**
- Modify (only if Step 1 needs it): `data/synth3/real/medicine.yaml` (`query` or `max_fetch`)
- Nothing else is committed: the pool and the folders are git-ignored.

- [ ] **Step 1: Fetch the pool.** Run `uv run synth3 pool-fetch --domain medicine`. It makes about
  `max_fetch / 20 + 2` requests at one per second (about one minute for 600 ids). Expected:
  `kept <k> of <n>` with `k >= 230` (30 test papers + 200 sources, so the 5 folders share no source). If
  `30 + 40 <= k < 230`, go on (folders then share some sources, by design) and note it in the ledger. If
  `k < 70`, widen `query` (e.g. drop the `antihypertensive` term or raise `max_fetch` to 1500), commit the
  config (`synth3: widen the medicine pool query`) and run again: the saved XML is reused.
  Write the licence counts it prints into the ledger: the open-access filter also lets in no-derivatives
  and custom licences, and these papers are adapted, which is fine only because they stay local.
- [ ] **Step 2: Split.** Run `uv run synth3 pool-split --domain medicine`. Expected: `test 30`, `sources k-30`,
  and a pieces count above 0.
- [ ] **Step 3: Build.** Run `uv run synth3 build-real --domain medicine --seeds 1,2,3,4,5 --out
  data/synth3/built/medicine-real`. Expected: 5 lines, each with a `medicine3r-` id. A refusal names the study
  and the problems. Fix the cause in code (with a test) or in the real config, never by loosening a check.
- [ ] **Step 4: Check the truth against the template folders.** Run a scratchpad script: for each seed, compare
  `world`, `spec`, `studies` and `facts` of `data/synth3/built/medicine/s<n>/ground_truth.json` and
  `data/synth3/built/medicine-real/s<n>/ground_truth.json`. Expected: `5 of 5 equal`.
- [ ] **Step 5: Realism.** For each seed run `uv run synth3 realism --domain medicine --folder
  data/synth3/built/medicine-real/s<n> --out data/synth3/built/medicine-real/realism-s<n>.json`. Expected: two
  AUC tables per seed. Write the AUCs, the style gap and the top cues into the program ledger next to the
  synth2 template v2 numbers.
- [ ] **Step 6: Note the open items for Aditya in the ledger ("for Aditya to run or decide"):**
  - run the blind reader on the cluster, one folder at a time:
    `uv run synth3 reader --domain medicine --folder data/synth3/built/medicine-real/s<n>` (n = 1..5, with the
    usual LiteLLM settings), and read `real/reader-check.json`;
  - read `data/synth3/built/medicine-real/s1/papers/S001.md` and one more, and say if they read well;
  - decide whether the realism numbers are good enough.

  This plan does not wait for him and does not run the reader.

### Task 12: Other domains: real configs and spec drafts, then stop

**Files:**
- Create: `data/synth3/real/law.yaml`, `data/synth3/real/materials.yaml`, `data/synth3/real/rag.yaml`
- Create: `data/synth3/drafts/law.yaml`, `data/synth3/drafts/materials.yaml`, `data/synth3/drafts/rag.yaml`
- Modify: `backend/synth3/tests/test_domains.py`

**The pool source per domain:**
- **Law:** SSRN (spec §10b), `source: files`. SSRN has no public API and its terms do not allow automated
  downloading, so Aditya downloads the PDFs by hand (empirical legal studies with counts or measured values)
  into a local folder. Then `synth3 pool-import --domain law --from <folder>` converts them with Docling
  (`uv sync --group fetch`).
- **Materials science:** open journals indexed in PMC (e.g. *Materials (Basel)*), `source: pmc`, with the
  same fetcher and a query on the journal and the measures. Builder's call: this gives JATS instead of arXiv
  PDFs.
- **RAG:** the existing HF pool (`WKMarwat/arxiv-ai-papers`), `source: files`. Make the cleaned papers with
  `synth2 realpool-split` and `synth2 realpool-cut --side sources`, then run `synth3 pool-import --domain rag
  --from <cut>/full`. Exclude synth2's 30 test papers so the two benchmarks keep one held-out set.

- [ ] **Step 1: Write the failing test:**

```python
@pytest.mark.parametrize("domain", ["law", "materials", "rag"])
def test_domain_specs_load_and_fit_forty_studies(domain):
    live = (SPECS / f"{domain}.yaml").exists()      # true once Aditya approves and moves the draft
    spec = load_spec(domain, SPECS if live else SPECS / "drafts")
    assert len(spec.pairs) * MIN_PER_PAIR <= 40 * (1 - spec.head_to_head_rate)
    assert {m.kind for m in spec.measures} == {"count", "value"} and len(spec.measures) >= 3
    assert any(not m.higher_is_better for m in spec.measures) and any(c.from_setting for c in spec.conditions)
    assert load_real_spec(domain).domain == domain
```

  The test does not check that the drafts are not live (it would fail the day Aditya approves one); the
  plan reviewer checks that this task moves no draft.

- [ ] **Step 2: Run it to watch it fail.** Expected: FAIL with `no spec file`.
- [ ] **Step 3: Write the drafts.** Each has 1 control and 3 invented treatments, at least 3 measures (one
  lower-is-better, at least one `value`), 3 conditions (one `from_setting`), 6 settings, 40 surnames, and the
  same rates as medicine. Starting points (builder's call; Aditya edits):
  - **law:** standard prosecution against invented diversion programmes. Measures: reoffending (count, lower is
    better), cases closed (count), days to resolution (value, lower is better). Settings: urban and rural
    courts.
  - **materials:** untreated alloy against invented treatments. Measures: tensile strength (value, MPa),
    samples that cracked (count, lower is better), hardness (value, HV). Settings: industrial and university
    labs.
  - **rag:** a closed-book model against invented retrieval set-ups. Measures: questions answered right (count),
    answers with an invented fact (count, lower is better), answer time (value, ms, lower is better). Settings:
    cloud and on-device.

  The real configs fill `keep` (always with `TEMPLATE_WORDS`, which `load_real_spec` enforces), `name_stems` /
  `name_words` (e.g. alloy codes for materials, none for law) and `control_words` per domain. Run the test.
  Expected: PASS.
- [ ] **Step 4: Run the whole suite** `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** the six data files and the test: `synth3: draft specs and real configs for law,
  materials and rag`.
- [ ] **Step 6: Stop.** Add to the ledger's list for Aditya:
  - approve or edit each draft, and move it to `data/synth3/<domain>.yaml`;
  - for law, download the SSRN PDFs;
  - then draw, approve and build each domain with the commands of this plan.

  Do not draw, approve, fetch or build these domains.
