# UI plan: make evidence, uncertainty and comparisons inspectable

**Design proposal — 6 November 2026.** Companion to [the improvement proposal](impromement.md), [Python libraries](python-libraries.md), and [datasets/benchmarks](datasets-and-benchmarks.md). This is a source-based audit and future design; no frontend code, running service or historical artifact was changed, and no live browser performance was measured.

## 1. The interface's central question

The main screen should answer: **“What is the answer, which evidence supports it, and what unresolved evidence could still change it?”**

This makes the proposed contribution observable. A large animated graph or a chat transcript alone does not demonstrate exhaustive evidence handling, correct uncertainty propagation or better answers. Every displayed scientific conclusion should link to its run, question, source evidence and scoring definition.

The priority is **visible runs and correct scores first**, then evidence inspection, then the new uncertainty workflow. A clear failed result is more useful than a convincing-looking empty dashboard.

## 2. Reuse the existing frontend

The current [routes](../frontend/src/app/routes.tsx) already provide guided question workflows, corpora, plans, jobs, runs, reports and comparisons. [RunPage](../frontend/src/pages/ev/RunPage.tsx) has answer/paper/protocol views, score presentation, traces and graphs. [TraceTab](../frontend/src/components/ev/TraceTab.tsx) exposes model-call details and polls while a job is active. These are implementation observations, not proof that every historical campaign is currently discoverable in the live UI.

Reuse React, TanStack Query/Table, React Flow, Dagre, Recharts and the existing Radix/shadcn-style controls from [package.json](../frontend/package.json). Keep the FastAPI API and generated OpenAPI types. A rewrite in Streamlit, Gradio or a new frontend framework would discard useful integration without addressing the scientific problem.

The current comparison view emphasizes synthetic direction accuracy. Add explicit report adapters for real tasks rather than making SciLead top-1 and SciREX list F1 look like the same synthetic score. The run page currently chooses its first linked report for its score tab; a future score selector should identify metric, sample, scorer version and source report clearly.

## 3. First fix the visibility contract

The viewer's [file reader](../backend/webapp/evfiles.py) documents runs under `$EV_RUNS/<group>/<name>` and IDs of `<group>~<name>`. The historical real campaign contains deeper dataset/condition/question paths. This is an integration point to validate; it is not a fresh diagnosis of the live service.

Introduce a **read-only campaign registry** that maps stable IDs to approved artifact roots and explicit format adapters. Do not move experiments, create duplicate result copies, follow arbitrary paths from payloads, or expose unrestricted filesystem traversal.

Required registry fields:

```text
campaign_id, run_id, question_id, question_text_hash,
dataset_id, corpus_hash, sample_hash, system, configuration,
repetition, run_location, artifact_schema, scorer_version,
execution_state, answer_state, scoring_state, last_indexed_at
```

Use manifest-based incremental indexing. Keep source artifacts authoritative, record damaged/unsupported formats, and preserve the existing root-containment checks. Missing or malformed data should produce an inspectable row, not vanish from the run list.

An empty page should distinguish:

- No runs exist for this campaign.
- Active filters hide existing runs, with a clear reset action.
- A configured root is unavailable or unreadable.
- Artifacts exist but their format is unsupported.
- Runs exist but matching score files are absent or unrecognized.
- The most recent refresh failed; previously loaded records are still shown.

The researcher-facing diagnostics can show configured roots and exact artifact paths. General answer views should show source titles and stable run links instead of filesystem details.

## 4. Proposed information architecture

Keep current routes stable and extend their views:

| View | Main content | Why it matters |
|---|---|---|
| Campaign overview | Dataset/sample counts, all question statuses, system matrix, failed/blocked counts and latest artifacts. | Prevents cherry-picking successful runs and hidden denominators. |
| Run workspace | Answer, evidence, unresolved cases, query execution, costs and source-linked trace. | Makes the method understandable at question level. |
| Corpus audit | Enumerated/processed units, missing sources, table/offset problems and scope definition. | Makes “exhaustive” a measurable property. |
| Comparison | Matched question IDs, metric definitions, paired scores, uncertainty intervals and cost. | Supports the actual improvement claim. |
| Review queue | Ambiguous tuples and policy decisions, with genuine reviewer provenance. | Separates automated verification from human decisions. |

Keep gold labels confined to evaluation views and scoring services. The generation worker must not receive evaluation answers just because the browser can display them after a run.

## 5. The main run workspace

Use a three-column desktop layout that collapses into tabs on small screens. The diagram is a proposed layout; it contains no invented experimental values.

```text
Campaign / Dataset / Original question ID      Execution | Answer | Scoring
Question text               Model/config      Corpus/sample identity

+----------------------+---------------------------+------------------------+
| Question contract    | Answer and evidence       | Unresolved evidence    |
| task, metric, split  | answer / partial result   | what could change it   |
| comparison rules    | metric + denominator      | why it matters         |
| assumptions         | selected measurement rows | next permitted action  |
+----------------------+---------------------------+------------------------+
| Source passage / table, with exact highlighted span and row/header context |
+-------------------------------------------------------------------------+
| Query bindings | Verification history | Costs | Artifact/replay details    |
+-------------------------------------------------------------------------+
```

The first visible answer status should be one of `complete`, `partial`, `abstained`, `blocked` or `unavailable`, with a reason. Execution success, answer correctness and stability under assumptions are separate fields. A green completed process must not imply a correct scientific conclusion.

### Components to implement or extend

| Proposed component | Inputs | Behavior and acceptance criterion |
|---|---|---|
| `CampaignRunTable` | Registry, sampled-question list, score references | Show every sampled question, including blocked cases and missing outputs. |
| `QuestionContractPanel` | Versioned typed contract | Show metric, split, direction, tie policy and unresolved choices; expose the saved revision. |
| `AnswerStatusCard` | Answer, completeness state, stability state, assumptions | Explain partial/unknown results; never equate successful execution with correctness. |
| `EvidenceLedgerTable` | Full tuples and selectors | Sort/filter by method, metric, experiment and status; preserve ambiguous alternatives. |
| `SourceInspector` | Server-produced segments and selectors | Open the exact quote/table context; flag unresolved selectors or hash mismatch. |
| `CoveragePanel` | Enumeration and processing counts | Display declared denominators and missing units; label processing coverage separately from evidence recall. |
| `AlternativeAnswerPanel` | Possible winners/lists/bounds and dependencies | Explain which unresolved source can alter the result; label solver witnesses as hypothetical. |
| `VerificationHistory` | Versioned attempts, premises, updates | Show accepted/rejected proposals, disagreements and invalidated conclusions without overwriting history. |
| `QueryBindingInspector` | Compiled operators, bindings, rejected rows | Identify where evidence failed a filter/join; distinguish zero rows from a proven negative. |
| `PairedComparisonTable` | Exact sample IDs and scorer outputs | Compare systems only when corpus/question/scorer compatibility checks pass. |
| `QualityCostChart` | Frozen operating points and observed measurements | Show answer coverage/error/cost with denominators and intervals; missing values remain missing. |
| `ArtifactDrawer` | Manifest, hashes, source paths | Export the recorded evidence needed to reproduce the displayed result. |

All uncertainty-specific components depend on backend artifacts proposed in `impromement.md`. Until those exist, mark the features unavailable or show explicitly labeled design fixtures. Do not infer “stable” from a high confidence score or populate a demonstration with fabricated research results.

## 6. Make provenance useful, not decorative

Default to a small evidence slice: **answer → selected measurement → experiment → source span**. Expand conflicting alternatives on demand. Keep the whole graph in advanced tools. Label edges by relation and distinguish supported, unresolved, conflicting and inferred information with text/icons as well as color.

Use the existing server-side source segmentation. The reader already accounts for Python code-point offsets versus JavaScript UTF-16 indexing; recomputing offsets in the browser would reintroduce highlighting errors. Keep table headers and footnotes visible when they determine a value's meaning.

Every selected row should expose the original value, normalized value, unit rule, experiment association and provenance. Clicking “why excluded?” should reveal the exact contract predicate and supporting premise, not just an LLM explanation.

For graphs, reuse React Flow and memoized node/edge components, hide expanded subgraphs when unnecessary, and avoid rerendering the entire graph on each trace update. These match the project's existing library and its [official performance guidance](https://reactflow.dev/learn/advanced-use/performance).

## 7. Comparisons that make the novelty testable

The comparison header must state: dataset, exact sample size, question IDs, corpus hash, model/pin, scoring version, cold/warm cache policy and relevant budget. Flag incompatibilities before offering a paired difference.

Show separate panels for:

1. **All-question effectiveness:** SciLead top-1, SciREX list F1, or the selected dataset's official measure. Retain every sampled ID.
2. **Conditional diagnostics:** accuracy among executed or answered cases, explicitly labeled with its smaller denominator.
3. **Uncertainty behavior:** answer coverage, false stability and bound/candidate-set validity, only when their new scorers and labels exist.
4. **Evidence:** locator availability, semantic support and recall as distinct measures; unavailable gold means unavailable recall.
5. **Computation:** new/cached calls, tokens, preprocessing and end-to-end time. Avoid comparing cached execution to fresh generation as though they were equivalent.

Historical baselines, proposed variants and unsupported comparisons need distinct labels. Keep fixed/random/uniform verification ablations adjacent so a reviewer can see whether the scheduler matters. Do not label these future conditions as completed experiments.

## 8. Fast interaction without hiding expensive computation

Treat these as proposed acceptance targets, not current measurements: on a recorded laptop/browser and representative SSH link, p95 filter/tab interactions below 200 ms after data is loaded, a useful warm run summary within two seconds, and an immediate visible acknowledgement when a job is queued. Measure network round-trip time separately; an SSH link may dominate load latency.

Implementation priorities:

- Fetch summary data first; load graphs, full call payloads and source documents on demand. Existing routes are already lazy-loaded.
- Paginate backend evidence/trace queries; do not ship every model response to render a list.
- Incrementally refresh changed artifacts. Preserve the existing trace cursor instead of rereading full logs on every poll.
- Poll only active jobs with backoff on connection errors; keep stale data visibly timestamped. Evaluate event streaming only if polling remains a measured bottleneck.
- Add `@tanstack/react-virtual` only for tables whose row count justifies it. TanStack Virtual provides list virtualization independently of the table implementation. [Official documentation](https://tanstack.com/virtual/latest/docs/introduction).
- Cache derived summaries using artifact signatures and schema versions; invalidate when a growing file changes. Atomic backend summary writes prevent half-written JSON views.
- Keep model work queued at the established safe concurrency. A double-click or browser retry must not submit duplicate evaluation jobs; use an idempotency key and return the existing job.

Benchmark page interaction with large **UI test fixtures** containing repeated neutral rows, clearly separated from scientific evaluation data. Rendering 10,000 fixture rows tests UI behavior; it is not an experiment on 10,000 papers.

## 9. Test the visible end-to-end behavior

Keep Vitest, Testing Library and MSW for component/API-contract cases already supported in the repository. Consider Playwright for browser journeys and trace capture, with axe checks for accessibility. These are proposed additions, not installed tools. [Playwright documentation](https://playwright.dev/docs/intro), [accessibility testing](https://playwright.dev/docs/accessibility-testing).

Required journeys:

| Journey | Observable pass condition |
|---|---|
| Open a historical real campaign | Every expected question is listed; original IDs, blocked cases and matching score denominators agree with disk artifacts. |
| Follow answer → evidence → source | Correct document/span/table context opens; source hash problems are visible. |
| Inspect an unsuccessful run | Distinguish execution failure, blocked plan, empty result and abstention; show the relevant stage/error artifact. |
| Compare engine and RAG | Use matched IDs and the correct task metric; incompatible samples cannot be silently paired. |
| Disconnect/reconnect | Cached rows remain visible with a stale indicator; reconnect does not duplicate work. |
| Launch a supported run | One job is queued, persisted and discoverable after refresh; status reaches a verified terminal state. |
| Review a future uncertain answer | Remaining alternatives and their assumptions appear; model review is never labeled human confirmation. |

Use saved real artifacts for read-only journeys before making new model calls. A live launch test should be a separately selected authorized workload, run once through existing logging with captured exit status and outputs. No completed synthetic campaign needs to be rerun for UI testing.

Keyboard access, focus management, named controls, non-color status indicators, readable tables and screen-reader status messages are necessary. A canvas graph needs a table/text alternative. Automated accessibility checks supplement manual keyboard inspection; they do not establish complete accessibility.

## 10. A truthful demonstration sequence

1. Open the existing SciLead sample and show all ten questions, including unsuccessful cases and the original baseline results.
2. Open a recorded run and trace an answer or empty query back through evidence and source context. Show what the current instrumentation can and cannot establish.
3. After the new method exists, show a real unresolved case, the alternative answer it permits, a recorded verification step and the resulting change or continued abstention.
4. Open the paired comparison and cost view. Show whether the measured benefit survives the exhaustive baseline.

Before implementation, step 3 belongs only in an explicitly labeled prototype using illustrative fixtures. The UI should not imply that the proposed improvement has already succeeded.

For optional completion sound, provide an opt-in toggle, volume/mute and a test button after a user gesture. Play once per terminal job transition; also show a visual notification. Browsers may block audio without interaction. Never depend on sound alone or repeatedly sound on polling refreshes.

## 11. Delivery order

**Phase A — trust the inventory:** registry/format adapters, all sampled IDs, clear empty/error states, task-specific real scoring and report selection. This directly addresses the earlier “I cannot see runs/scores” problem class.

**Phase B — trust the evidence display:** source navigation, tuple context, query bindings, bounded traces and accurate processing-coverage counters.

**Phase C — expose the research method:** uncertainty ledger, possible alternatives, premise changes and conditional stability. This phase requires the proposed backend artifacts, not just frontend work.

**Phase D — present comparisons:** matched datasets/questions, ablation panels, reliability/coverage/cost plots, exports and browser/accessibility checks.

Keep the UI on loopback behind the established SSH tunnel. This plan requires no public deployment, model restart, cache change or alteration of historical experiments. Success means a reviewer can inspect the claim and its counterexamples efficiently, including cases where the method fails.
