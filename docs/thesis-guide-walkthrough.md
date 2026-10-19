# Thesis system walkthrough — recall notes

Use this as the preparation sheet for explaining the system to the thesis guide. Keep
[`thesis_pipeline.html`](../thesis_pipeline.html) open beside it. The map is a visual
overview; this document supplies the technical narrative and distinguishes implemented
work from extensions and evaluation plans.

## The one-sentence explanation

The system turns a research question into a hand-written executable protocol, runs that
protocol over a paper corpus using interchangeable evidence extractors, links the
extracted facts into an evidence graph, and derives an answer with explicit rules. A
synthetic benchmark with known ground truth lets us measure where the process succeeds
or fails, from finding a passage through producing the final answer.

## Suggested walkthrough (about 20 minutes)

| Time | Explain | Show on the HTML map |
|---|---|---|
| 0–2 min | Research goal and why evidence-level reasoning is useful | Research question; contrast answer-level and evidence-level reasoning |
| 2–5 min | Question and protocol | Question → protocol lane; click the protocol box |
| 5–8 min | Synthetic corpus and controlled difficulty | Synthetic benchmark lane; ground truth, difficulty knobs, fidelity, corpus |
| 8–12 min | Engine, extractors, and evidence graph | Execution engine and extractor library lanes |
| 12–15 min | Synthesis, answer, and traceability | Evidence graph → synthesis → answer → trace back |
| 15–18 min | Evaluation and baselines | Evaluation lane: locate recall, A/B/C, error attribution, baselines |
| 18–20 min | Reproducibility, limitations, and questions | Provenance/replay and infrastructure lanes; finish with open questions |

Keep the static map open at `http://127.0.0.1:28099/thesis_pipeline.html` in the
laptop browser. Click a box for its details and references. This is a diagram, not the
live run-results UI.

## Speaking notes, in order

### 1. The research question and the method

The first question is: **Does retrieval-augmented generation (RAG) improve the factual
accuracy of LLM-generated answers?** This is a useful first prototype question because
papers report experiments with systems, metrics, and numeric results that can be
represented and compared.

An answer-level system retrieves papers or passages and asks a model to state what the
literature concludes. This project also examines the underlying experimental evidence:
which conditions were compared, which metric was used, and what values were reported.
The system can therefore derive a conclusion from reported results even if a paper does
not state that conclusion directly. Authors' conclusions are extracted as another
evidence type, but the numeric synthesis is based on the reported measurements.

**Transition:** “To make that investigation repeatable, we specify the question as a
protocol before running the engine.”

### 2. The protocol: the executable research specification

**In plain language:** the research question is too broad for the program to act on by
itself. The protocol is the written set of instructions that makes it specific: which
papers count, which facts to find, how those facts connect, and how the answer follows
from them. Think of it as a research recipe that the engine follows consistently.

For this question, the recipe says to look for a RAG-versus-no-RAG comparison, find the
conditions and factuality metric, extract each reported value and dataset, then compare
the matched values. It also says how to label a study and combine study directions.
That means the final result follows declared rules, rather than an LLM improvising a
conclusion from the paper.

The protocol is a versioned YAML file: [`evidence/protocols/rag-factuality.yaml`](../evidence/protocols/rag-factuality.yaml).
It acts like an intermediate representation between the natural-language question and
the engine. It declares:

- Which papers are in scope and how documents are located. The current protocol uses
  exhaustive locating.
- A screening question and screen extractors to decide whether a paper reports a
  comparison of RAG with the same model answering without retrieval.
- The evidence types and schemas to extract: `condition`, `metric`, `measurement`, and
  `author_claim`.
- How extractors are selected for each evidence type, how items are linked, and how the
  final answer is synthesized.

For example, a condition has a label and role (`rag`, `baseline`, or `other`). A metric
has a paper-provided name and a canonical category such as `factual_accuracy` or
`hallucination_rate`. A measurement is a numeric value for a condition and metric, plus
the dataset when reported. Values for accuracy and rates are normalized to the
`[0, 1]` range and checked against schema bounds.

The protocol is written by hand for the first question. Automatic protocol generation
is an optional extension in the HTML map, not a required part of this first workflow.
The engine validates the protocol before a run; its parsed-content hash is recorded so
we can identify exactly which protocol a run used.

**Transition:** “Now we need a controlled set of papers where we know what evidence
should be present.”

### 3. The synthetic benchmark and its ground truth

**In plain language:** the corpus is the stack of papers we give the tool to read. We
start with made-up studies whose correct facts are known, then turn those facts into
papers. That lets us check whether the tool found the intended facts. The tool gets the
papers; the evaluator uses the hidden answer key afterward.

We vary how the same facts are written. In an explicit paper, a result may be easy to
spot; in a paraphrased or distributed paper, it takes more work to find or connect the
facts. This tests whether the method handles different writing difficulty, rather than
only an easy template. Template-written and LLM-written papers let us compare controlled
text with more natural variation.

The `synth/` package generates structured ground truth first, then renders papers from
it. The ground truth records the intended studies, conditions, metrics, measurements,
author claims, and expected effects. The papers are the input seen by the systems under
test; the engine and baselines do **not** read ground truth. It is used for scoring.

The benchmark varies how difficult facts are to find:

- **Explicit:** stated directly.
- **Paraphrased:** stated with different wording.
- **Distributed:** relevant facts appear in separate sections or locations.
- **Complex:** facts require more difficult linking or interpretation.
- **Contradictory:** the paper contains planted misleading or conflicting values.
- **Mixed:** a corpus containing examples across levels.

There are two renderers. The template renderer gives controlled, repeatable paper text.
The LLM renderer produces more natural variations and is checked against the intended
facts with fidelity checks and retries. The runbook builds the same seeded study sets
with both renderers, plus knob sets containing duplicates, missing values, outliers,
and irrelevant papers. It also defines a counterfactual variant that flips one study's
direction so we can check whether the measured answer changes as expected.

**Caveat to state clearly:** the LLM-written set excludes studies that fail fidelity;
the template set keeps all 20. This means corpus composition can differ and should be
considered when interpreting a direct renderer comparison. The synthetic benchmark
supports controlled diagnosis; by itself it does not establish performance on the full
real-world literature.

**Transition:** “Given a protocol and a corpus, the engine applies the same evidence
contract to different ways of finding facts.”

### 4. The engine, locating, and extractors

**In plain language:** the engine is the worker that follows the protocol for every
paper. It first screens the paper, finds the text to examine, asks extractors for the
needed facts, checks their answers against the paper, and links the facts together.
Finding the relevant text is *locating*; deciding what that text says is *extracting*.

The three main run settings are experiments with different amounts of work: `regex-only`
uses pattern matching; `cascade` with `all` runs the configured extractor sequence for
the benchmark; `cascade` with `gaps` starts with the first extractor and calls later
ones only when the evidence is not enough to classify the study. In `all` mode the
screening decision is recorded but does not exclude a paper, so screening quality can
be scored on that same run. In `gaps` mode, a paper screened out by the protocol is
skipped.

The Python engine interprets the protocol over the corpus. It screens documents,
locates relevant text, invokes the configured extractors, validates and merges their
items, links the evidence, and runs synthesis. The protocol fixes the evidence needed
and the synthesis rules; the locating and extraction implementations can vary while
returning the same typed output contract.

The extractor contract gives each call a task (document, evidence type, scope, and any
needed context) and expects a structured result. Results can contain typed items with
their source spans, rejected items with reasons, and a coverage report. The engine
checks cited spans against the source paper. The implemented library includes regex
extractors, single-call LLM extractors, and an agentic extractor that wraps the existing
research agent.

In the runbook's main engine comparison:

- **`regex-only`** runs the regex extractors.
- **`cascade`, strategy `all`** runs the configured extractor sequence for every
  evidence type and records what each found.
- **`cascade`, strategy `gaps`** screens first and escalates only where evidence is
  still missing. Some calls can be reused from the record cache; targeted gap calls
  are new tasks.

The agentic extractor and the agent baseline are different experiments. The agentic
extractor works behind the protocol's evidence-extractor contract. The agent baseline
receives the question without that evidence protocol.

**Transition:** “The extracted facts matter only if we preserve how they relate and
can trace the answer back to the paper.”

### 5. Evidence graph and deterministic synthesis

**In plain language:** after extracting facts, the system puts them into a connected
record rather than treating each number as an isolated result. It links each reported
number to the system that produced it, the metric it measures, the paper it came from,
and the text passage that supports it. Then it compares the RAG result with the
no-retrieval result using the protocol's rules.

For example, `0.62` and `0.70` alone do not say which system did better. The graph
preserves that `0.62` belongs to the no-retrieval condition and `0.70` to the RAG
condition, and that both are factual-accuracy measurements on the same dataset. The
protocol can then classify this study as supporting RAG. Results from other studies
may support, contradict, or show no meaningful effect; the system combines those
classifications into the final label.

Extracted items are merged into a graph. Its nodes represent documents, conditions,
metrics, measurements, and author claims; edges connect measurements to their
conditions and metrics and record the document context. Items retain the spans that
support them and which extractors found them.

For each study, synthesis pairs a RAG condition with a baseline condition on the same
dataset. It prefers a table cell over prose and then the earlier value in document
order. The protocol prioritizes factual accuracy, then hallucination rate. The
direction is derived from the numeric difference, with effects smaller than `0.01`
treated as neutral. Hallucination-rate direction is interpreted with its
lower-is-better setting. Studies are classified as supporting, contradicting, neutral,
or undetermined; the aggregate label is `supported`, `refuted`, `mixed`, `no_effect`,
or `insufficient`.

**What `insufficient` means in the Runs UI:** it is the answer label, not a job or run
failure status. The protocol assigns it when there are no usable supporting,
contradicting, or neutral study results to count. For example, the run may have found
no valid same-dataset RAG/baseline measurement pair, or every study may have been
undetermined or excluded as a duplicate. Check the run's counts and per-study details
to see which case occurred. A run can therefore complete successfully and still have
an `insufficient` answer: it means “this run did not get enough classifiable evidence
to answer,” not “the evidence shows no effect.” `no_effect` is the separate label for
usable evidence that is neutral under the protocol's threshold.

The answer can be traced back through the selected measurement, its condition and
metric, and the passage span. This is the key practical difference from a free-form
summary: the system exposes the evidence and the rule used to derive each direction.

### 6. Provenance and reproducibility

**In plain language:** we keep a record of the work, so we can answer “where did this
fact come from?” and “can we reconstruct this result?” Replay is like replaying a
recording; re-execution is asking the system to do the task again and seeing whether
the answer changes.

Each locate, extractor, merge, and synthesis operation is recorded in the run artifacts.
The event log is hash-chained. The record cache is keyed by extractor identity and task
hash, so the same task can reuse its full recorded result.

- **Replay** uses recorded calls only; it must reproduce the outputs and their hashes.
  It does not call a model.
- **Re-execution** calls the model or extractor again and reports stability or drift.

These answer different questions: replay checks that the recorded computation can be
reconstructed; re-execution measures how much a fresh run changes.

Typical evidence run artifacts include `run.json`, a copy of the protocol,
`events.jsonl`, per-call JSON records, `locate.json`, merged `evidence.jsonl`,
`graph.json`, and `answer.json`. Corpora and runs are stored under `$EV` on Ceph, not
committed as large data files.

### 7. Evaluation: where did the answer go wrong?

**In plain language:** evaluation checks three things separately: did the tool find the
right facts, did it connect them correctly, and did it draw the right conclusion? This
helps explain *why* an answer was right or wrong, instead of reporting only a final
accuracy number.

Evaluation compares outputs with the benchmark's ground truth and separates three
stages:

- **A — Extraction:** precision, recall, and F1 by evidence type and difficulty;
  measurement values and spans are checked against the known facts and placements.
- **B — Integration:** whether extracted measurements were linked to the correct
  condition and metric, and whether the engine selected the correct RAG/baseline pair.
- **C — Synthesis:** per-study direction accuracy and final answer-label accuracy.

Additional measures include locate recall (whether the extractors were given passages
containing planted facts), which extractor uniquely found items, stability on
re-execution, and cost. The score reports bootstrap confidence intervals for key
metrics and paired engine-versus-baseline differences.

The runbook compares with two answer-level baselines. The RAG baseline retrieves the
top eight BM25 passages from the corpus, asks for an answer with citations, and maps the
answer into per-paper stances. The agent baseline uses the research agent with the
question and no evidence protocol. Both use the same model alias as the engine's LLM
extractors for the planned comparison.

**Interpretation:** the A/B/C separation helps localize failure. A wrong final answer
may be caused by not locating the passage, extracting a fact incorrectly, linking a
fact to the wrong condition or metric, or applying synthesis incorrectly.

### 8. Slurm execution and the runbook

**In plain language:** Slurm gives the experiments access to the compute node and
model-serving job. The runbook says which work runs first, where logs and results are
stored, and which steps can share the model service. Code stays in the repository;
large corpora, run outputs, caches, and scores are stored under `$EV` on Ceph.

[`docs/slurm-evidence-runbook.md`](slurm-evidence-runbook.md) is the operational plan
for building corpora and running the experiments. In broad terms it covers setup,
LLM-written corpora, template corpora, the engine, replay/re-execution, agentic
extraction, baselines, scoring, fidelity review, and proposal-flow review. The engine
and baseline stages use the `orch-model` alias; corpus writing and fidelity checking
use separate sub-model aliases. Long model workloads are serialized as specified in
the runbook to avoid competing for the same model service.

You do not need to run the whole runbook just to prepare the walkthrough or inspect
existing runs. It is a first-live-experiment procedure with multi-hour model steps.
Run it when you intend to produce or refresh that experiment's artifacts; first check
which steps already finished under `$EV` and continue from the runbook's dependency
table. The runbook explicitly expects some steps to fail and requires recording them
in `$EV/failures.md`; it also marks fidelity hand-check and proposal review as user
steps.

**Current live-pass caveat (18–19 Oct 2026):** the LLM-written main corpus kept only
one of 20 studies in the explicit level and none in the other levels or mixed set.
The fidelity report says required numeric strings were ambiguous because they appeared
multiple times. Runs on those empty or near-empty corpora often show `insufficient`;
that is not evidence that RAG has no effect. Treat these LLM results as a diagnostic
of the corpus-generation/fidelity pipeline, not as a complete benchmark conclusion.
The saved outputs are under `/mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-cluster`.

The HTML diagram has a dated status panel. Its status text says it describes the state
on 14 October 2026, before the current Slurm run. Treat it as the conceptual design and
reuse map; use the runbook and actual run artifacts for current experiment status and
results. Do not quote the page's dated status as today's status without checking it.

## One concrete example to make the flow intuitive

Imagine a synthetic paper reports factual accuracy of `0.62` without retrieval and
`0.70` with retrieval on the same dataset. The extractor should return two
measurements, linked to the correct baseline/RAG conditions and the factual-accuracy
metric, each with source spans. Synthesis computes a difference of `0.08`, classifies
the study as supporting, and retains the path to both reported values. This is an
illustrative example; it is not a claim about the current experiment's measured result.

## Terms to keep straight

| Term | Meaning in this project |
|---|---|
| Research question | The natural-language question being investigated. |
| Protocol | Versioned YAML specification for scope, evidence types, extractors, and synthesis. |
| Corpus | Manifest and papers processed by a run; synthetic corpora also have ground truth for scoring. |
| Ground truth | Structured intended facts and expected effects used by evaluation, never by the engine or baselines. |
| Evidence item | One typed fact extracted from a paper, with source span(s) and provenance. |
| Evidence graph | The linked representation of documents, conditions, metrics, measurements, and claims. |
| Run | One execution of a protocol/system on a corpus, with settings and artifacts. |
| Replay | Reconstruction using recorded extractor results, without fresh model calls. |
| Re-execution | A fresh run used to measure stability or drift. |
| Agentic extractor | The research agent used as one extractor behind the protocol. |
| Agent baseline | The research agent answering from the question without the evidence protocol. |

## Likely supervisor questions

### The main limits to state plainly

- **Synthetic papers test the method, not the scientific claim about RAG.** They let us
  compare the system with known facts; real-paper evaluation is needed to establish how
  well it transfers to published research.
- **One question is a focused prototype.** The protocol and synthesis rules are tailored
  to RAG factuality; another question needs its own protocol and may need different
  evidence types or rules.
- **A study's evidence has to be comparable.** The current protocol pairs RAG and
  baseline measurements on the same dataset when possible, but papers can report
  incomplete or inconsistent details.
- **The current synthesis is a rule-based aggregation of study directions.** It is not
  a sample-size-weighted meta-analysis and does not model all sources of statistical
  heterogeneity.
- **LLM-generated papers can fail fidelity checks.** The LLM corpus excludes studies
  that fail; the template corpus retains all 20. Keep this difference in mind when
  comparing the two corpora.

**Why not just ask an LLM to summarize the papers?**

That is represented by the answer-level baseline. The evidence-level method makes the
comparison structure and numeric facts explicit, measures extraction and linking
separately from synthesis, and provides a trace from answer to passages.

**Why synthetic data?**

It gives known facts, exact intended placements, controllable difficulty, and a way to
attribute errors. It is a controlled first evaluation, with real-paper generalization
remaining a separate question.

**How do you know a generated paper reflects its intended facts?**

The LLM renderer uses fidelity checks and retries, and the runbook includes a human
fidelity review. Failed studies are excluded from the LLM corpus set. Template and LLM
sets can therefore differ in retained studies, which is a limitation to report.

**Is the final conclusion an LLM opinion?**

No. The engine uses extractors to obtain evidence, but its study directions and answer
label come from the declared numeric comparison and aggregation rules. The LLM-written
answer-level baseline is evaluated separately.

**What is the contribution?**

The core design is the protocol-driven evidence-level pipeline and its evaluation
decomposition. The implementation adds a common extractor contract, interchangeable
extractors including an agentic option, provenance/replay support, locate recall,
error attribution, and an agent baseline. Confirm the exact thesis contribution list
with the supervisor before presenting it as final.

## Short closing

“The goal is not only to produce a verdict. It is to make the evidence path inspectable
and to measure whether errors came from finding facts, extracting them, linking them,
or synthesizing them. The synthetic benchmark gives us controlled ground truth for
that first evaluation; the next question is how far the findings transfer to real
papers.”

## Rehearsal script (about 3–4 minutes)

Use the HTML map from left to right. This is a connected first explanation; expand a
stage if the guide asks for implementation detail.

> “My thesis is about a system that answers research questions from papers. I’m using
> the question ‘Does RAG improve the factual accuracy of LLM-generated answers?’ as the
> first case. I’m evaluating whether the paper-reading system works; I’m not running
> new RAG experiments on language models.
>
> “A natural-language question is too broad for a program to execute directly, so we
> write a protocol. The protocol is a versioned YAML file that says which papers are
> relevant, what facts to extract, how those facts should be linked, and how to derive
> an answer. For this question, the evidence includes the compared systems, the
> factuality metric, the reported values, and the dataset.
>
> “To evaluate the tool, we generate synthetic papers from structured ground truth.
> The tool sees the papers, and the evaluator compares its outputs with the separate
> ground truth. We vary how facts are written—from explicit to paraphrased,
> distributed, complex, or contradictory—and use both template and LLM renderers.
> This gives controlled tests, although it does not by itself establish performance
> on published literature.
>
> “The engine follows the protocol for each paper. It screens the paper, locates the
> text, and calls extractors. The extractors can use patterns, a language model, or an
> agent. The engine checks their evidence against the source text, merges the results,
> and links each measurement to its condition and metric in an evidence graph.
>
> “Synthesis then compares RAG with the no-retrieval baseline on the same dataset. A
> study can support, contradict, or show no meaningful effect under the protocol’s
> rules. The system combines those study directions into a final label and preserves
> the path back to the source passages.
>
> “We evaluate extraction, integration, and synthesis separately. That tells us
> whether an error came from missing a fact, linking it incorrectly, or drawing the
> wrong conclusion. We compare the engine with a retrieve-then-answer baseline and an
> agent baseline, and record the model calls and run artifacts. Replay checks that a
> saved run can be reconstructed; re-execution measures whether a fresh run changes.
>
> “The current benchmark is synthetic and the protocol covers one question, so the
> results show how well the method works under controlled conditions. Applying it to
> real papers and other questions is a further evaluation.”

**Pointing cues:** question/protocol; ground truth and corpus; engine and extractor
library; evidence graph and synthesis; evaluation and baselines; provenance/replay;
then the optional real-papers extension as future work.

## Source documents

- [`thesis_pipeline.html`](../thesis_pipeline.html) — interactive system/design map and references.
- [`docs/evidence-system.md`](evidence-system.md) — interfaces, run artifacts, extractor contract, and evaluation definitions.
- [`evidence/protocols/rag-factuality.yaml`](../evidence/protocols/rag-factuality.yaml) — current protocol and synthesis rules.
- [`docs/slurm-evidence-runbook.md`](slurm-evidence-runbook.md) — Slurm experiment procedure and artifact locations.
