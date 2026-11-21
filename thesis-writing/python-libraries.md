# Python libraries that support the research contribution

**Recommendation document — 6 November 2026.** Companion to [the improvement proposal](impromement.md), [UI plan](ui-and-components.md), and [dataset plan](datasets-and-benchmarks.md). No libraries were installed and no dependency files were changed.

## 1. Recommended shortlist

Start with **Hypothesis** for checking the uncertainty algorithm and **Z3** only where explicit alternative-world reasoning is needed. Add **Pint** when extending to scientific measurements. Consider **DuckDB** for querying accumulated artifacts and **pySHACL** if RDF graph-contract violations remain a measured problem.

These tools can make a research claim executable and testable. Installing them is not a scientific contribution. The contribution remains the uncertainty representation, its semantics, and evidence that it improves real end-to-end outcomes.

No recommendation requires an embedding model, vector database, dense retrieval, or embedding-based evaluation. Exhaustive document access remains the proposed default. Package status below means declared in [pyproject.toml](../pyproject.toml) or visible in source; it does not claim that every package imports successfully in the current Slurm environment.

## 2. Additions worth a focused prototype

| Priority and package | Concrete use here | Scientific value to test | Main limitation |
|---|---|---|---|
| P0 — `hypothesis` | Generate small evidence tables and sequences of ledger updates; compare abstract results with exhaustive concrete evaluation. | Detect false stability and incorrect premise reopening before expensive model runs. | Passing generated cases is not a formal proof. |
| P0/P1 — `z3-solver` | Encode alternative experiment assignments, eligibility constraints and competing winners; ask whether an alternative answer is possible. | Make conditional stability and conflict explanations inspectable. | Solver correctness applies to the encoding, not the truth of extracted evidence. |
| P1 — `pint` | Check dimensions and perform declared unit conversions for measurement tasks. | Reduce invalid scientific comparisons and test normalization explicitly. | Units do not determine metric meaning, experiment identity, or comparison validity. |
| P1 if artifact volume warrants it — `duckdb` | Query immutable JSON/Parquet exports for question-level comparisons, provenance joins and cost summaries. | Make denominators and paired comparisons reproducible and easier to audit. | SQL does not repair incompatible schemas or flawed evaluation units. |
| P2 — `pyshacl` | Validate graph shapes for measurements, experiments, provenance and permitted relations. | Catch graph-contract failures before executing a scientific query. | A shape-valid graph can still contain wrong or missing facts. |

The official sources and intended integration boundaries follow. Version selection, Python 3.13 compatibility and coexistence with the current lockfile must be tested in an isolated environment before adoption; this document does not recommend upgrading the production stack.

### Hypothesis: test the algorithm's invariants

Hypothesis provides property-based tests, including stateful tests that generate sequences of actions. Use it with the existing pytest suite to test the new ledger's behavior, rather than adding hundreds of implementation-shaped example tests. [Official introduction](https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html), [stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html).

Useful properties for this project:

- Every answer obtained by enumerating a small concrete completion is contained in the abstract answer set.
- A reported unique winner agrees with every permitted completion.
- An unread or failed source unit cannot become evidence of absence automatically.
- Refinement under unchanged premises cannot introduce new completions; a repaired premise may reopen them and must invalidate dependent conclusions.
- Duplicate storage does not double-count an experiment when the question asks for distinct experiments.
- Input order does not change a deterministic query result.
- Contradictory constraints produce an explicit inconsistency, not a successful answer.

Keep the concrete evaluator simple and independent of the optimized evaluator. Otherwise both can share the same bug. Store minimized counterexamples as developer regression fixtures; they are not new benchmark results or alterations of gold labels.

**First deliverable:** a finite-table reference evaluator and tests for ranking/list operators. This is the best first addition because it does not require an LLM, GPUs, or new datasets.

### Z3: check whether another answer remains possible

Z3's Python interface supports constraints, satisfiability checks, incremental solving, models and tracked assertions for unsatisfiable cores. [Python API](https://z3prover.github.io/api/html/z3.z3.html), [Programming Z3](https://z3prover.github.io/papers/programmingz3).

Proposed integration: the uncertainty evaluator owns a solver adapter; the LLM supplies typed proposals, never arbitrary executable solver code. For a current candidate answer, ask whether the ledger constraints admit a different answer:

- `sat`: preserve the alternative assignment as a witness that stability is not established.
- `unsat`: no alternative exists within the encoded universe and assumptions, provided the base constraints are themselves satisfiable.
- `unknown` or timeout: report unresolved; do not promote it to stability.

Store the encoded constraints, premise IDs, timeout, solver/version and result. An unsatisfiable core identifies a sufficient conflicting subset; it need not be the smallest or scientifically explanatory one. A model is an abstract witness, not a newly discovered paper measurement.

Use exact rational arithmetic for finite decimal values where appropriate. Do not replace scientific measurement uncertainty with floating-point equality. Unbounded undiscovered evidence must stay represented; encoding only extracted rows would create false assurance.

**Adoption gate:** use a solver only after simple interval/set propagation becomes inadequate. Compare solver results with exhaustive tiny-table enumeration and measure solving overhead. Do not introduce Z3 merely to advertise formal verification.

### Pint: scientific units without semantic shortcuts

Pint represents quantities and units and supports dimensional conversions. It is a useful candidate for MeasEval or materials experiments where a value's unit is central. [Official documentation](https://pint.readthedocs.io/en/stable/).

Keep `(raw value, raw unit, parsed quantity, conversion rule, converted value)` together. Require an explicit contract before interpreting percentages, fractions, temperatures, or dimensionless scores. BLEU and accuracy are not equivalent merely because both are dimensionless; two accuracy values from different test splits are not comparable because units match.

Add a small development suite for incompatible dimensions, ambiguous units, affine conversions and missing units. Record conversion failures as unresolved. Original corpus text and gold labels remain unchanged.

**Adoption gate:** demonstrate reduced unit errors on compatible annotated examples. If only dimensionless ranking questions are currently being evaluated, defer this dependency.

### DuckDB: an audit index over existing artifacts

DuckDB's Python API can query JSON and Parquet files using SQL. This is well suited to a read-oriented comparison layer over runs, questions, model calls and scores. [Official Python API](https://duckdb.org/docs/stable/clients/python/overview).

Build a derived index with stable `campaign_id`, `question_id`, question-text hash, corpus hash, run ID, system/configuration, repetition and scorer version. Join scores to the complete sampled question registry, not only completed runs. This makes blocked questions visible and helps prevent denominator drift.

Treat the index as rebuildable. Keep original files authoritative and immutable. Use explicit column types and migrations for legacy formats. Do not let a dashboard query infer scientific meanings from missing fields. Prefer one controlled index writer and bounded read queries over concurrent ad hoc writes to a shared file on Ceph; measure filesystem behavior before deployment.

**Adoption gate:** compare query latency and complexity with the existing pandas/file readers. The present corpus sizes alone do not justify adding another storage system.

### pySHACL: validate graph structure

pySHACL validates RDF graphs against SHACL shapes. [Official repository](https://github.com/RDFLib/pySHACL).

Candidate checks: every measurement has a metric and source selector; every experiment reference resolves; required value datatypes hold; query-relevant predicates belong to the declared schema. Link violations back to extraction records and question-contract obligations.

The repository uses PyOxigraph and RDFLib already. A bridge/export may be needed to validate the actual RDF representation; test it on the named-graph structure rather than assuming all graph semantics transfer automatically. Preserve the source graph and validator report separately. Structural validation should not silently add inferred facts or close unknown evidence.

**Adoption gate:** retain this only if it catches failures more clearly than existing typed validation and targeted SPARQL checks. For a small schema, those existing checks may suffice.

## 3. Get more value from libraries already declared

| Existing tool | Better use in this project | Boundary to preserve |
|---|---|---|
| Pydantic ecosystem + `jsonschema` | Typed question contracts, discriminated answer states, versioned API payloads and explicit nullable uncertainty fields. | Shape/type validation does not establish scientific interpretation. Pydantic itself is used in code; the manifest declares related packages rather than a separate direct Pydantic pin. |
| `pyoxigraph`, `rdflib`, `owlrl` | Keep the current graph execution and provenance pathway; make schema and reasoning exposure explicit. | A new graph database is unnecessary. Saved-template on/off results do not establish ontology benefit. |
| `rapidfuzz`, `regex`, standard-library `unicodedata` | Propose spelling/alias candidates with deterministic guards and preserved originals. | Fuzzy similarity must not merge different datasets, models or experiment conditions automatically. |
| `rank-bm25` | Existing lexical baselines and optional inspection ordering. | BM25 top-k is not exhaustive; do not use it to silently prune the proposed full-corpus condition. |
| `scipy`, `statsmodels`, `numpy`, `pandas` | Paired comparisons, uncertainty intervals, grouped analyses and transparent reporting. | Match independent resampling units; repeated calls and shared-paper questions are not independent observations. |
| `argilla` | Authentic annotation of complete scientific tuples and unresolved cases. | Real people must supply human labels; model agreement is not human confirmation. |
| `pdfplumber`; optional fetch-group `docling` | Preserve table structure, offsets and extraction-quality diagnostics. | Parser availability is not correct ingestion. Model-dependent parsing/OCR may require approved downloads and separate resource checks. |
| `dspy`, `pydantic-ai-slim`, existing `modelcall` | Reuse existing typed model-call infrastructure and isolated development optimization. | Keep prompt/task/verification separation and held-out data boundaries; avoid another orchestration layer by default. |
| `fastapi`, `sse-starlette`, `httpx` | Existing service/API foundations for the UI plan. | Do not replace working services just to add a new framework. |

Repository evidence: [manifest](../pyproject.toml), [normalization implementation](../backend/evidence/names.py), [graph construction](../backend/evidence/kg/build.py), and [statistical utilities](../backend/evaluation/stats.py).

Pydantic strict mode can reduce unintended coercions, though behavior depends on input type and field type; define deliberate coercions explicitly. [Strict-mode documentation](https://docs.pydantic.dev/latest/concepts/strict_mode/).

SciPy supports paired bootstrap calculations; Statsmodels offers proportion confidence intervals. Neither automatically solves the study-design problem. Reuse the existing scorer and specify cluster-level resampling when questions share papers. [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html), [Statsmodels proportion intervals](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html).

Argilla supplies annotation workflows, and Docling supplies document conversion capabilities. Any annotation deployment or additional parser model is a separate implementation decision, not needed to write these recommendations. [Argilla documentation](https://docs.argilla.io/latest/), [Docling documentation](https://docling-project.github.io/docling/).

## 4. Avoid additions that obscure the contribution

Do not add an embedding stack, vector search service, graph database server, or additional agent framework for this proposal. Keep the existing serving model and recorder. A general evaluation package with an LLM judge should not replace the dataset's exact scorer, especially when the same model family generates and judges outputs.

Also defer another experiment-tracking service unless file-based manifests and the proposed run registry fail a concrete requirement. For publication, complete provenance and reproducible analysis matter more than the number of integrated tools.

## 5. A minimal adoption experiment

1. **Reuse first:** implement strict answer/ledger schemas with the current infrastructure and a simple concrete evaluator.
2. **Add one dev dependency:** use Hypothesis to test finite completions and state transitions offline.
3. **Add one algorithmic dependency if needed:** evaluate Z3 on the same cases; compare accuracy, timeouts and runtime with interval/set propagation.
4. **Add by observed need:** Pint for units, pySHACL for graph contracts, DuckDB for artifact indexing. Keep each change isolated.
5. **Record the trade-off:** package/version, licence, Python/environment compatibility, lockfile diff, quality benefit, CPU/memory cost, and new failure modes. Pin only the tested versions.

The resulting paper should attribute these tools correctly. Its claim should describe the new evidence representation and verified behavior, not imply that a solver, validator or test library was invented here.
