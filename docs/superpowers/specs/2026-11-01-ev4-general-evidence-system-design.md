# EV4 design: a general evidence system ("put any knowledge behind it")

Date: 1 Nov 2026. Written for the builder of EV4. Sources: Aditya's EV4 mood board (claude.ai artifact
7mnFE2FeHMWGaLRyD943VE, Want lane), a builder check, and a grilling session with Aditya on 1 Nov whose
decisions are listed in §10 (D1-D43). Card ids appear in brackets. Tim's quotes are from his 14 Oct
messages (`~/.claude/skills/tim/feedback.md`, M2 §1-§9).

## 1. Intent

EV1-EV3 built one vertical slice for one question ("Does RAG improve the factual accuracy of LLM
answers?"): a hand-written protocol, an extractor cascade (regex → abbreviation → GLiNER → LLM), synthesis,
a synthetic benchmark and three answer-level baselines. The topic lives in the code: regex patterns for
"retrieval-augmented", metric names like `factual_accuracy`, GLiNER labels, the synthetic vocabulary, and a
closed set of five evidence types. A new topic means editing Python.

EV4 makes it general: drop in a **domain pack** (a folder describing a topic) and a set of papers, and the
same code finds the evidence and answers. Tim's frame stays: evidence-level reasoning, an explicit protocol
as the intermediate step (§2, "compiler analogy"), reusable extractors (§3), honest comparison with
answer-level baselines (§7). EV4 also adds the first thing an answer-level system cannot do at all:
**chaining** results across studies to reach a conclusion no paper states (Tim §1).

**Scope claim of the thesis (D20, reopened by D37):** the system must not be limited to comparisons.
Aditya (1 Nov): "we can't be fixed with one type of things only". The old harness (research-harness-ui)
handled any question with a per-question schema, open extraction into evidence-anchored triples, four
claim shapes (Result, Comparison, Method, Limitation) and a SPARQL answer. **Resolved (D37, Aditya 1
Nov, after a /tim check):** EV4 adds a few fixed, scoreable answer shapes rather than a schema invented per
question, because Tim wants "a complete but deliberately limited prototype" (§8) where "we can
independently calculate the expected synthesis" (§5 C). The first two are **limitations** and
**builds-on / influence** (§6.18), both already in Tim's §5-§6 ("dependencies between studies",
"methodological limitations") and the second close to his own example, "How influential was a particular
scientist". Each shape must come with what to extract, a deterministic rule, generator truth and a score.
An open per-question schema stays future work.

## 2. Success

1. A second topic (drug trials) runs end to end with no change to extractor, engine or synthesis code.
2. No topic word appears in that code; a test proves it.
3. Old runs replay byte for byte at their own code tag; the RAG topic is rerun with EV4 code (§6.8).
4. Chaining gives the right answer on synthetic questions where no single paper holds it.
5. A small check on real labelled papers (SciREX) reports how well names are found.
6. The report shows where the engine loses, not only where it wins (Tim §7: "We should not assume that
   the evidence-level approach will necessarily perform better").

## 3. Words used in this document (also in GLOSSARY.md)

- **Domain pack**: a folder with everything topic-specific. Called **topic** in the web app.
- **Study**: one paper. **Comparison**: one treatment-vs-control result inside a study, on one metric and
  one dataset. A study can hold many comparisons.
- **Treatment / control**: the two sides of a comparison as the code names them (the thing tested, the
  thing it is compared against). Users see the domain's own names ("RAG system / closed-book model",
  "drug / placebo").
- **Chaining**: concluding A versus C from study 1 (A versus B) and study 2 (B versus C).

## 4. Non-goals and anti-goals

Not in EV4: answering with SPARQL and exporting runs as RDF (D9), adding a measured-value class to an
ontology (D9), a learned-versus-hand-written word comparison run (D10), learning words in an unlogged way,
a coverage ledger, a per-sentence verifier, SHACL, entailment-level scoring, protocol unit tests and a
protocol type checker, answer shapes beyond those of §6.18 (an open per-question schema), a confidence
score per answer, and
detecting the same study reported twice. Embedding-based
retrieval is excluded outright.

It is a failure, even if it technically works, if:

- an old run stops replaying at its code tag;
- topic words are only moved to another Python file;
- the drug-trials pack is copied from the generator's own word list (extraction would be easy by
  construction; see §6.4);
- a demonstration on real arXiv papers is presented as a score;
- a scored pack or protocol is changed after its scored run was looked at without being logged;
- the web app shows OWL, ontology or class jargon;
- the report only shows wins.

## 5. Constraints

- **Start:** `main` at or after tag `ev3b-code` (EV3b fixes merged and pushed 1 Nov: GLiNER items confirmed
  by the LLM, eager confirm, `relink`, per-paper RAG at 16,384 tokens as the main RAG row, agent prompt v3).
  The EV3b Slurm run was skipped (Aditya), so no fixed reference numbers exist yet (§6.8).
- **Replay:** an extractor id hashes its source files (`code_sha256`, evidence/extractors/base.py:22-33).
  Moving topic words out of the code gives every extractor a new id once; freezing old hashes would defeat
  the hash. So old runs replay at their own tag; EV4 numbers are new numbers (D36). The
  synthetic `rag-demo-*` and EV2 template corpora stay on disk unchanged (sha256 test on the files); the
  generalised generator does not have to regenerate them byte for byte (my call, from D36).
- **No embeddings** in retrieval or screening. BM25 (`rank_bm25`), regex and LLM screening are allowed.
- **Same model for all systems**; no change to `llm-setup` beyond the existing GLiNER addition.
- **Workflow:** Claude builds; Codex runs on Slurm from a `docs/` runbook; results come back on a results
  branch; nothing is merged, tagged or pushed without Aditya's go.
- **Frozen before scored:** a pack and protocol used for scoring are frozen under a git tag before its
  scored run; every file changed after the tag is logged in the report.
- **Prompts** follow `docs/prompt-writing.md` (atomic tasks, explicit inputs and outputs, deterministic
  validation, separate generation and verification).
- **Deterministic runs:** anything new in a run (reasoner inferences, agent proposals, web search results)
  is recorded in the run or frozen in the pack, so a replay never calls a live service.
- **Prefer maintained packages** (rdflib, owlrl, pydantic, the MCP SDK) over home-made code.

## 6. Design

### 6.1 Domain packs (g01, "no hard-coded keywords", h02)

A domain is a folder, `domains/<name>/`:

```
pack.yaml        evidence types (open, §6.2), their fields, roles, enum values, units, better direction,
                 the treatment/control mapping and display names
words.yaml       per type and per value: regex patterns, GLiNER labels, claim cues, screen and BM25 terms
ontology.ttl     the domain's OWL ontology subset (§6.3)
generator.yaml   what the synthetic generator draws from (only for synthetic domains)
protocols/       hand-written protocols (YAML, §6.6)
questions.yaml   the domain's questions
provenance.json  where the pack's words and ontology came from (hand-written / agent with its log, §6.4)
```

**What moves out of code into `domains/rag/`** (from reading the code and the builder check; the
no-topic-words test finds the rest): `evidence/extractors/terms.py` (`CONDITIONS`, `METRICS`,
`CLAIM_SUBJECT`, `CLAIMS`, `NOT_A_SYSTEM`), `gliner.py` `LABELS`, `units.py` `FRACTION_METRICS` and time
units, `dataset.py` `DEFAULT_PATTERN`, the metric names in `abbrev.py` and `evidence/propose/frame.py`,
all of `synth/vocab.py`, topic words in `evaluation/canon.py`, `evaluation/score.py`,
`evaluation/expected.py`, the baseline prompts in `evaluation/baselines/common.py`, and the web app's
`RunStep.tsx` and `ArxivFetchDialog.tsx`. The baseline system named `rag` (evaluation/baselines/rag.py)
gets a name that cannot collide with a pack value; old run directories keep their recorded names.

**Also moving (my call, from the builder check):** the protocols (`evidence/protocols/*.yaml`) and
questions (`evidence/questions.yaml`) move into `domains/rag/` as data. Prompts that hold topic words
(`synth/prompts/*.txt`, `evaluation/baselines/prompts/map-*.md`, `evidence/agentic/task.py`,
`evidence/propose/cards.yaml` and `draft.py`) become templates whose topic words are filled from the pack;
for `rag` the filled text should match today's as a migration check (not required, D36).

**Filling extractor configs.** Extractors take their patterns from `config` when the protocol gives them,
and otherwise fall back to word lists in code (regex.py:34 `default_patterns()`, gliner.py:109 `LABELS`,
dataset.py:29 `DEFAULT_PATTERN`, abbrev.py:219 `terms.CONDITIONS`). EV4 removes those fallbacks: the
engine reads the pack named by the protocol (`domain: <name>`; no key means `rag`) and fills each
extractor's config from `words.yaml`. For `rag` the filled configs are compared with today's as a
migration check that reports differences; it is not a gate (D36). Pack files are config, not code, so editing a pack changes only the
extractors whose words changed.

**Pack versus protocol (applies to every setting, words included).** If a protocol sets a value (screen
terms, query words, enum values, treatment/control, better direction, descriptions), the protocol wins;
otherwise the pack's value is used. `evidence pack check` warns where they disagree. Existing protocols
keep all their keys.

**No-topic-words test.** Lists every pack's words and values and searches `evidence/`, `synth/`,
`evaluation/`, `agent/` and `webapp/` (code and prompt templates; excluding `domains/`, tests, fixtures).
Expected hits: zero, apart from an explicit reviewed allowlist of generic words (e.g. "baseline"), each
with a reason.

### 6.2 Open evidence types (D1, D8)

A pack declares its own evidence types; the closed set (evidence/contract.py:20,
evidence/evidence_types.py:21, `ITEM_PREFIX` at contract.py:26) becomes open. The engine, the question
kinds (effect, inventory, consistency, best, chaining, and the new limitations and builds-on of §6.18),
the scorer and the web app work over whatever types the pack declares.

Every pack must map types onto three **required roles**, because answering "is A better than B" needs
them: **compared thing** (systems, drugs), **metric**, **measured value** (linked to a compared thing and a
metric). **Author claim** is an optional fourth role. Other types (dataset, task, population, dependency,
limitation) are **context**. `pack check` enforces only what the pack's questions need: a pack used only
for name finding (e.g. SciREX) may lack values and claims (my call). The question kinds and synthesis address roles, never type names. The inventory kind
lists any declared type (today it hard-codes condition/metric/dataset, evidence/kinds/inventory.py:22).

**Comparisons are built, not extracted (my call).** Today synthesis picks the two sides by a fixed kind
(`compare: {treatment: rag, control: baseline}`, evidence/synthesis.py:138) and takes one effect per study.
EV4 builds comparisons: within a study, every pair of compared things with measured values on the same
metric (and the same dataset or population, when named) is a comparison. Which side is treatment and which
is control comes from the question ("does A improve on B?") or, for effect questions, from the
protocol's treatment/control values as today. The `rag` protocols keep their `compare` setting; `rag`
results may still change (D36).

**The same thing across studies (D38).** Names are matched by general code, so no hand-written list is
the bottleneck. In order, over the whole corpus before answering:

1. **Clean:** Unicode NFKC, case, hyphens and spaces, Greek letters spelled out, plurals.
2. **Aliases defined in the paper:** abbreviation definitions ("Retrieval-Augmented Generation (RAG)",
   Schwartz-Hearst style, reusing `abbrev.py`) and "hereafter" aliases; the quote is kept.
3. **Near-match** with a string-similarity package (`rapidfuzz`), guarded: numbers and version tokens must
   match exactly ("GPT-3" ≠ "GPT-4", "Drug A" ≠ "Drug B").
4. **Group** the names of the whole corpus with steps 1-3; each group is one thing, named by its most
   frequent form. A pack's name list, if given, only seeds the groups; it is optional.
5. **Model last:** the model judges only names still unmatched against the groups, and must quote
   evidence; its matches are recorded and marked "model match" and may be used for chaining.

Every match records the step that made it. Names still unmatched are kept as their own thing, counted per
run (`unresolved_names`, like `dangling_links`), shown on the run page, and written to a candidate list
for the topic folder; the frozen folder never changes mid-run. The generator plants name variants (odd
spellings, code names, "hereafter" aliases) so name matching is scored (my call). Chaining (§6.10)
matches by group.

Item ids keep their recipe (a digest of type, fields and spans, contract.py:131). New fields (such as the
number form of D35) may change `rag` item ids; that is accepted (D36), and old runs replay at their tag.

### 6.3 Ontology per domain and the reasoner (D8, D13, D16, D18)

Each pack carries an OWL ontology subset (`ontology.ttl`). For computer-science domains the seed is CS-KG
2.0 (https://scholkg.kmi.open.ac.uk/cskg/ontology, namespace `https://w3id.org/cskg/ontology#`): compared
thing → `Method`, metric → `Metric`, dataset → `Material`, task → `Task`, builds-on → `based-on`. The
ontology seeds the pack; it does not limit it: a pack may add types it lacks, each naming its nearest
parent (`OtherEntity` by default). The drug-trials domain uses an ontology found by the pack builder
(§6.4). The measured value stays our own internal type (D9).

A **reasoner** runs in the engine (candidate `owlrl` over `rdflib`). It does two jobs:

1. **Matching kinds:** a narrower term counts for the broader one a question asks about ("top-1 accuracy"
   counts as "accuracy" when the ontology says so).
2. **Checking links:** a value linked to something that is not a metric (or not a compared thing) is
   flagged in the run.

Chaining (§6.9) stays in Python. Inferences are written into the run, so replays never re-reason.
The web app never shows OWL, ontology or class words (D13); users see plain names.

### 6.4 The pack builder agent (D4, D7, D11, D14, D17)

An agent proposes a new domain pack:

- It reads the papers through the corpus tool server (§6.5). It may read the corpus that will be scored
  (that is what a real user does), but **never** `ground_truth.json` or any gold.
- It proposes the evidence types and their roles, the words per type (regex patterns, GLiNER labels,
  claim cues, screen terms), and the display names for treatment and control.
- It searches the web (a general, Google-like search; the builder picks a free provider) for a fitting
  ontology and proposes a subset.
- Everything it proposes is logged with its source sentences and search results in `provenance.json`.
- The user approves or edits; the result is frozen in the pack before any scored run.

**For drug trials (my call):** the extraction pack comes from this agent plus Aditya's review, never from
`generator.yaml`. The generator's words and the extractors' words must come from different sources, or the
benchmark is easy by construction. **Fallback (D34):** if the agent is not ready in time, a fresh Claude
helper that is never shown `generator.yaml` writes the drug-trials pack from the drug-trial papers alone;
its work is logged in `provenance.json` and Aditya only checks it. Drug trials (Must) therefore do not wait
on the agent (Should).

### 6.5 Corpus tool server (h06)

Port the MCP corpus server of research-harness-ui (`packages/mcp_corpus`) to this repo's corpus layout:
`list_papers`, `read_paper`, `read_section`, `search` (BM25), `grep`, `tables`. It reads only
`manifest.json` and listed paper files, never `ground_truth.json` (a test). Users in EV4: the pack builder
agent, and optionally the agent baseline on new domains. The engine and existing baselines keep their
current reading code.

### 6.6 Protocols: YAML that behaves like code (e01, D19)

Tim favoured "a declarative protocol representation (e.g., YAML or JSON), executed by a Python-based
engine" (§2). Protocols stay YAML, with code habits:

- each step names a registered function and its inputs; an unknown name or missing input fails before
  any model call;
- every run writes `protocol.lock.json`: protocol digest, pack digest, every resolved extractor id, the
  ontology digest;
- `evidence protocol diff A B` prints what changed in plain lines.

### 6.7 Sealed runs (h13)

Every run directory ends with `manifest.json`: every file with its sha256, the corpus manifest sha256, the
protocol lock digest and the code commit. A failed run still writes all expected files (empty when there
is nothing). `evidence verify <run>` recomputes the hashes. Old runs: "no manifest (pre-EV4)".

### 6.8 RAG is rerun, not matched (D36)

Aditya (1 Nov): old answers do not matter. EV4 does not try to reproduce `ev3b-code` numbers: no
two-part reference run, no reuse of recorded calls by request text, no byte-identical prompt test. The RAG
topic is simply rerun with the EV4 code, and those are the RAG numbers in the thesis. Old runs still
replay at their own code tag (free, since tags keep the code). EV3's numbers are never a comparison
point. Every engine run reports `dangling_links` (expected 0).

### 6.9 Drug trials: the synthetic second domain (D2, D12)

A synthetic corpus of drug-trial papers generated from structured truth with our own generator (`synth/`),
generalised to read `generator.yaml`. Outcome: response rate reported as counts per arm ("41 of 120
patients") and as percentages; units are fraction and percent only. Population is a context type.

**Who writes `generator.yaml` (D39).** The recipe for a topic's synthetic papers (things tested, metrics
and better direction, realistic value ranges and sample sizes, reporting styles, limitation categories,
builds-on patterns) is drafted by the topic builder from 5-10 real papers of the topic (RAGEval's idea),
not written by hand. Generated things get invented names, so no model answers from memory. The helper
that writes `words.yaml` never sees `generator.yaml`, and each draft is logged separately in
`provenance.json`. Before a full corpus: a 5-paper trial must pass the fidelity check, and a blind reader
must find the planted values. Aditya looks over the draft once (about 10 minutes); then it is frozen under
a tag.

**One general number reader (D35).** The number extractor rejects counts and "N% of X" shares today
(evidence/extractors/numbers.py:26, 243-260), a rule made for RAG papers. EV4 replaces topic-tuned number
rules with one general reader used for every topic, with no per-topic switches: it reads the common forms
(plain values, percent, fractions, "k of n", ranges, ± spreads), keeps every number's span, and labels the
form; whether a number is a result, a sample size or something else is decided from its role in context,
not by a topic rule. The role is set by the step that already links values to things and metrics (code
where the sentence structure is clear, the existing model call otherwise); there is no extra model call
per number (my call). RAG numbers may change because of this; that is accepted (D36). The
truth contains a **network** of comparisons (drug A vs placebo, A vs B, B vs C) so chaining has known
answers, plus planted limitations and builds-on links (§6.18). Question kinds: effect, inventory,
consistency, best, chaining, limitations, builds-on. The RAG corpora stay as they are, so on RAG only the
first four kinds are scored; chaining and the two new shapes are scored on drug trials only, with
no new RAG corpus (D43, Aditya).

A search on 1 Nov (10 candidates) found no public tool that writes papers from chosen numbers and checks
each number's placement, so we keep `synth/` and borrow ideas only, not files: RAGEval (OpenBMB/RAGEval,
arXiv 2408.01262; CC BY-NC-SA, so no copied prompts): draft a topic from a few real papers, human-fixed;
DTBench (ZJU-DAILY/DTBench, arXiv 2602.13812): its 13-skill list to justify our difficulty levels;
ClashEval: graded wrong values (×0.5, ×2) as plausible and implausible decoys.

The fidelity and blind re-extraction checks (`synth/fidelity.py`) must read the domain's schema, not fixed
fields, before any drug-trials corpus is accepted.

### 6.10 Chaining (D5, D6)

From comparisons A>B (study 1) and B>C (study 2), conclude A>C, matching A, B and C by name group
(D38, §6.2). Allowed only when both use the same metric, and the same dataset or population
when the papers name it (D6). The answer marks it "inferred through B, not
tested directly", lists the studies it rests on, and never presents it as a direct result. Scored on drug
trials against the truth network (direction correct, path correct, refusals when the rule forbids a
chain). The answer-level baselines get the same questions, and the limitations and builds-on questions
too; each shape gets a baseline map prompt (like `evaluation/baselines/prompts/map-*.md`) that turns the
free-text answer into the shape's scored form (my call). We expect baselines to fail chaining, and report
it either way.

### 6.11 Studies that build on each other (t05)

The generator gets a `builds_on` preset: some studies reuse an earlier study's drug/model or dataset, and
some report an earlier study's result as their own control ("as reported by [X]"). A `dependency` context
type records it. A copied result counts once, at its original study. Scored in B (dependency links) and C
(no double counting). Old presets and corpora unchanged. Must, since the builds-on shape (§6.18) depends on
it; built with the generator in step 4.

**Who drafts what, from which papers (my call, from D7, D34, D39).** Three paper sets stay apart:
(1) `generator.yaml` is drafted by a Claude drafting helper (a prompt plus log, available at step 4,
before the full pack builder agent) from 5-10 real papers fetched for that purpose; (2) `words.yaml` is
written by the pack builder agent or the D34 helper from the synthetic scored corpus only, as a real user
would; (3) real-paper test sets (Yun et al., SciLead, SciREX) are read by neither helper.

### 6.12 SciREX small check (D21)

SciREX (Jain et al., ACL 2020, github.com/allenai/SciREX): real ML papers with labelled Datasets, Methods,
Tasks and Metrics. 1-2 days: load the test split, run the frozen extractors with a SciREX pack, and score
name finding (A) at two levels: mention level, and salient-cluster level (an extracted name is right if it
matches any mention of a salient cluster; headline). No links, answers or chaining. The builder confirms
what the gold contains and reports how many papers fit the budget.

**More real-paper checks (D42, Should; research notes of 1 Nov, kept with the plan).** Each about 1-2
days, reported as "real-paper check", never mixed with synthetic scores:

1. **Drug trials:** Yun et al. 2024 (MLHC), github.com/hyesunyun/llm-meta-analysis,
   `evaluation/data/annotated_rct_dataset.csv`, Apache-2.0: 120 real RCT reports (markdown), 699 records
   with intervention, comparator, outcome and events / group size per arm (or mean and SD), each with an
   Evidence Inference prompt id; Evidence Inference 2.0 (MIT, GitHub copy) adds the significantly better /
   worse / no difference label. Scores A, B and C separately. Only 59% of records have complete numbers;
   score the rest on names and direction only.
2. **ML papers:** SciLead (EMNLP 2024): 43 hand-checked papers, 295 (task, dataset, metric, result)
   entries, 27 leaderboards. Scores "best" and chaining on real papers; the method-to-value link is soft
   because each value is the paper's best number.
3. **arXiv RAG papers, edit test:** change a number, swap a method name, or delete a limitation sentence
   in the 5 real papers and check the right item, link and answer change; plus a random 100-item hand
   sample for precision. This shows the system follows the text, not that it is right.

Not used as main scores: ClinicalTrials.gov registry values (disagree with the paper in about 20% of
trials, Hartung 2014) and an LLM judging the same model's output.

### 6.13 Scale: 10,000 papers, no embeddings (n03; cut first)

(Cut first, except `evidence estimate`, which is Should per D41.) BM25 first pass over all papers against the protocol's screen terms (`prefilter: {method: bm25, keep: N}`,
default off), then the existing regex and LLM screens. `evidence estimate <protocol> <corpus>` prints
papers reaching the LLM and expected calls and tokens before a run. Test on a synthetic template corpus
of 10,000 papers (about 2% relevant): first-pass recall, wall time, estimated vs actual calls.
BM25 may use DuckDB's text search (D33).

**Model calls (D41).** No new speed-up machinery: the existing funnel (cheap code first, the model fills
gaps) stays. `evidence estimate` moves out of "cut first" into Should, so every Slurm run is preceded by
an estimate. The report shows model calls and tokens per system next to its scores (§6.16).

DuckDB is a read-only helper (D33): it queries run folders and corpora in place for cross-run reports
and the BM25 first pass. Nothing is stored in it; deleting it loses nothing, and run folders stay the
truth (D27).

### 6.14 Web app (c13, c14, c09)

- **Scores page removed** (`webapp/web/src/pages/ev/ScoresPage.tsx`, route, nav). Its numbers appear on
  the Report page (all runs) and the Run page (one run).
- **Readable evidence graph** (Developer tools, Run page, `@xyflow/react`): three columns: Papers →
  Claims (comparisons with both values, limitations, builds-on links) → Verdict (the shape's answer and
  the rule). Edges coloured by direction; dependencies and chains as dashed edges. Internal items
  hidden until clicked. The builder reviews the EV3 graph first and lists what to drop.
- **Add a topic (demo, never scored; cut first):** choose papers → the pack builder agent proposes kinds,
  words and ontology → the user approves or edits → ask a question → get a protocol, shown beside a
  hand-written one with `evidence protocol diff`.

### 6.15 Real arXiv papers (c11, demo)

`evidence fetch` already builds an arXiv corpus without gold, which the app refuses to score. Run the
frozen RAG protocols on about 30 arXiv papers and produce a hand-check sheet for 5 papers (each item with
its source sentence, right / wrong). The report gives sampled precision, labelled "demonstration, not an
evaluation".

**Reading real papers (D40, Should).** `evidence fetch` prefers arXiv's HTML version (built from the
authors' LaTeX, so tables are exact) and falls back to Docling for PDFs, replacing pymupdf4llm. GROBID
(old harness) is the alternative if Docling falls short; it needs its own server. Synthetic papers and
SciREX are text already, so this only affects the arXiv demo.

### 6.16 Report shows losses (c16)

Per domain, the first table lists every question with each system's result, losses first. Each engine
loss gets one line: missed / wrongly linked / names not grouped / wrong rule. Next to the scores: model
calls and tokens per system (D41). Tim's §7 sentence opens the comparison section.

### 6.17 Architecture (D23-D27)

```
domain pack (folder) ──► pack check + reasoner setup
papers ──► corpus tool server ──► pack builder agent ──► domain pack
protocol + pack ──► lock ──► engine: find → screen → extract → merge → reason → compare → answer → chain ──► run folder + manifest
generator + pack ──► synthetic papers + truth ──► scorer ◄── run folder
web app reads run folders only
```

- Domain packs live in the repo under `domains/`, versioned with git and frozen with tags (D23).
- Every engine step writes its own file in the run folder, so each step's input and output can be
  opened on its own (Tim's "show the steps") (D24).
- The reasoner runs after merge and before comparisons; it reads the merged items and the pack's
  vocabulary and writes what it inferred to its own file (D25).
- Answering is three steps, each with its own file: build comparisons, answer the question, chain.
  A wrong answer then points at the step that failed (D26).
- The web app only reads files; no database. A run folder is the whole truth of a run (D27).
- One loader reads a domain pack and hands the engine one pack object; no code reads topic words from
  anywhere else (D28).
- The pack builder agent and the corpus tool server live in their own folder with their own command;
  the web app starts them as a normal job (D29).
- The reasoner is a setting; a missing setting means off, so old runs replay unchanged (same rule as
  relink) (D30).
- Gold is read only by the scorer; the engine cannot import it, and a test checks this (D31).
- Papers are built locally; only runs go to Slurm, as today (D32).

### 6.18 New answer shapes: limitations and builds-on (D37; details accepted by Aditya 1 Nov)

| | Limitations | Builds-on / influence |
|---|---|---|
| Example question | "What limitations do papers report for drug A?" | "Which later studies build on method X, and how influential is it?" |
| What to extract | author-stated limitation sentences, linked to a compared thing, with quote; a category from the pack's limitation list (e.g. cost, side effects, small sample) | dependency links: a study reuses an earlier study's method, dataset or result (the `dependency` type of §6.11) |
| Rule | group by thing and category; count papers per category | follow links: direct and indirect followers of X; influence = number of later studies reaching X |
| Generator truth | planted limitations per study, with category | the builds_on preset's dependency network |
| Score | A: precision/recall of (study, thing, category); C: per-thing category list | B: link precision/recall; C: follower sets and influence ranking |

Each shape is a registered question kind like the four existing ones, works over pack roles, and has a
fidelity check. Names in both use the name groups of D38.

## 7. Priority (D22) and build order

| Tier | Items |
|---|---|
| Must | domain packs and open types (§6.1-6.2), name grouping (D38), general number reader (D35), RAG rerun (§6.8), generator drafting + 5-paper trial (D39), drug trials (§6.9), builds_on preset (§6.11), chaining (§6.10), limitations and builds-on shapes with baseline map prompts (§6.18) |
| Should | reasoner (§6.3), pack builder agent with web search (§6.4), corpus tool server (§6.5), protocol lock and diff (§6.6), sealed runs (§6.7), `evidence estimate` (D41), real-paper checks: SciREX, Yun et al. + Evidence Inference, SciLead, arXiv edit test (§6.12, D42), Scores page out and new graph (§6.14), arXiv HTML/Docling and demo (§6.15, D40), losses and costs in report (§6.16) |
| Cut first | BM25 first pass and 10,000-paper scale (§6.13), add-a-topic web demo (§6.14) |

Build order: (1) pack format and `domains/rag`, config migration check, no-topic-words test (the old
number extractor keeps working until step 3); (2) open types and role-based kinds; (3) general number
reader and name grouping; (4) generator generalised with the drafting helper, drug-trials truth network,
builds_on preset, planted limitations and name variants, fidelity schema-driven, 5-paper trial;
(5) comparisons and chaining; (6) limitations and builds-on shapes with baseline map prompts; (7) drug-trials
pack: the pack builder agent with tool server, or the D34 helper; frozen; (8) reasoner; (9) lock, diff,
manifests, estimate; (10) real-paper checks; (11) web app; (12) runbook for Codex: RAG rerun (four kinds),
drug trials (all kinds), real-paper checks, arXiv demo; report. Steps 8-11 are independent of each other.

## 8. Left to the builder

Module and file names, the exact `words.yaml` and `pack.yaml` layout, the allowlist mechanics, the MCP
library, the web-search provider (free), the reasoner package if `owlrl` falls short, graph layout details,
the drug-trials truth sizes, and the number of SciREX papers (reported).

## 9. Open for later (not EV4)

An open per-question schema (old-harness style) and answer shapes beyond §6.18; SPARQL answering;
confidence per answer; protocol unit tests and a type checker.

## 10. Decision log (1 Nov)

D1 packs declare their own types · D2 synthetic second domain, keep `synth/`, borrow ideas · D3 names
(domain pack/topic, study, comparison) · D4 treatment/control inside, domain names outside, proposed by an
agent · D5 chaining is a goal · D6 chain only on the same metric (and dataset), marked inferred · D7 the
agent may read the scored corpus, never gold, logged and frozen · D8 three required roles plus an optional claim, CS-KG as seed
not limit · D9 no ontology extension, no RDF export · D10 no learned-vs-hand-written run · D11 the agent
reads through the tool server · D12 drug trials · D13 ontology per domain, OWL never in the UI · D14 the
system finds its vocabulary online, frozen · D15 add-a-topic flow (demo) · D16 a reasoner runs during
runs · D17 general web search · D18 reasoner matches kinds and checks links; chaining in code · D19
protocols stay YAML that behaves like code · D20 scope claim · D21 SciREX small check · D22 priority tiers · D23 packs in the repo under `domains/` · D24 one file per
engine step · D25 reasoner after merge, before comparisons · D26 answering split into three steps · D27
web app reads files only · D28 one pack loader · D29 pack builder separate, run as a job · D30 reasoner
is a setting, off when missing · D31 gold only in the scorer · D32 Slurm as today · D33 DuckDB read-only helper · D34 plan B for the drug pack is a fresh Claude helper blind to
generator.yaml · D35 one general number reader, no per-topic switches · D36 old answers do not matter:
no reference-run matching, RAG is rerun · D37 not comparisons only: a few fixed scoreable shapes, first limitations and builds-on · D38 names matched by
general code (clean, in-paper aliases, guarded near-match, corpus grouping, model last), never silent · D39 generator.yaml drafted from 5-10 real papers, invented
names, kept apart from words.yaml, 5-paper trial, one review, frozen · D40 arXiv HTML first, Docling fallback (Should) · D41 keep the funnel, estimate before
runs (Should), calls and tokens reported per system · D42 real-paper checks: Yun et al. + Evidence Inference
(drug trials), SciLead (ML), edit test on 5 arXiv papers · D43 new shapes and chaining scored on drug
trials only.
Also from the builder check: replay via code tags; pack gives defaults, protocol
overrides; SciREX scored at two levels. EV3b Slurm run skipped (Aditya).
