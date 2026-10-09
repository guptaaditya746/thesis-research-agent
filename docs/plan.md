# Thesis redesign: plan and brainstorm

Oct 8, 2026 · @Aditya Gupta

## Summary

The new design holds together if one thing is fixed early: **the agent records its findings through the harness, not after the fact.** Every fact the agent asserts is written by a `claim` tool that stores the triple, the agent step that produced it, and an exact text anchor in a `.md` file. The knowledge graph, the trace-back view, and the evaluation are then all reads over one append-only log. Nothing has to be reconstructed later.

The five recommendations that matter most:

1. **Concept = a research brief, not a subschema.** Show each concept as a one-line definition with its measure, an answer shape (a table or graph template with placeholders), and two or three competency questions. A subschema is derived from the answer shape automatically and shown on demand. This is what the user can compare, what the agent can act on, and what evaluation can score against (5.2).
2. **Harness = a mini-SWE-agent loop with a read-only corpus, a scratch directory, Python, and three built-in tools** (`claim`, `spawn`, `save_tool`). Everything else the agent builds itself. Logging is done by an interceptor outside the agent's control, which also answers the trace-tampering problem reported in September 2026 (5.3).
3. **Trace = one JSONL event log, one event per tool call or model call,** mapped to W3C PROV-O on export. The trace view is a claim-to-evidence graph (claim → step → quoted text), with a timeline and a subagent tree as secondary views (5.4).
4. **Provenance anchor = quote + position + hash** (Web Annotation `TextQuoteSelector` plus `TextPositionSelector` plus a hash of the file). It survives small edits to the Markdown and can be verified mechanically (5.5).
5. **Evaluate three things separately:** provenance faithfulness (does the quoted text support the fact), answer correctness for the chosen concept (the evidence document D survives, scoped to the concept), and process cost and coverage. Runs with different routes are compared on these outcomes, never on the route (5.6).

Build order: corpus conversion and anchor library first, then the harness with the logger and `claim` tool, then the trace viewer, then concept generation and view, then the graph and trace-back UI, then evaluation. The agent can be tested end to end from step two on with a hand-written concept.

## Plan: components, interfaces, build order

Seven components, each with one file-based interface, so every part can be built and tested alone and every artifact is inspectable on disk. The run directory is the contract: `runs/<run-id>/` holds the concept, the event log, the claims, the tools the agent wrote, and the exported graph.

&#91;embedded content: architecture · 8 components, the files that connect them\]

The harness is the only component that runs the model on the corpus; everything to its right reads files the harness and the interceptor wrote.

| Component | Does | Reads | Writes |
| --- | --- | --- | --- |
| Corpus builder | PDF → one `.md` per paper, with a stable id and a content hash | `pdf/*.pdf`, DBLP metadata | `corpus/<paper-id>.md`, `corpus/manifest.json` (id, title, hash, byte length) |
| Concept generator | question → N research briefs, corpus-blind | the question, the ontology vocabulary (names only) | `concepts.json` (list of briefs, schema in 5.2) |
| Concept view | shows briefs side by side; the user picks one | `concepts.json` | `runs/<run-id>/concept.json` (the chosen brief) |
| Harness | runs the agent loop: model call → tool call → result, until the agent stops | `concept.json`, `corpus/` read-only, `tools/` | `scratch/`, `tools/`, `claims.jsonl` via the `claim` tool |
| Interceptor (logger) | wraps every model call and tool call outside the agent's reach | the harness's calls | `events.jsonl` (append-only, hash-chained) |
| Graph builder | claims → canonical triples → graph with provenance | `claims.jsonl`, `events.jsonl`, `corpus/` | `graph.json`, `graph.ttl` (PROV-O), `anchors.json` |
| Viewer | graph, trace, replay, trace-back | the run directory | nothing |

Interfaces that matter: the `claim` tool is the only way a fact enters `claims.jsonl`, so provenance is complete by construction. The interceptor assigns every event an id; the `claim` tool records the id of the step it was called from. A subagent is a nested run directory (`runs/<run-id>/sub/<sub-id>/`) with its own event log, and its result is a file the parent reads, so the parent's trace shows the handoff as an ordinary tool call.

Build order, with what each step lets you test:

1. **Corpus and anchors (1 to 2 weeks).** Convert the 337 PDFs, freeze the Markdown, write and unit-test the anchor library (`anchor(file, start, end)` → selector; `resolve(selector)` → text or failure). The whole provenance story depends on this being solid.
2. **Harness, interceptor, `claim` (2 to 3 weeks).** Start from mini-SWE-agent. Run a hand-written concept end to end. Check that `events.jsonl` replays and that every claim resolves to text.
3. **Trace viewer (1 to 2 weeks).** Timeline plus claim-to-evidence links over the run directory. Needed early: it is how you will debug the agent.
4. **Concept generator and view (2 weeks).** Prompting, the brief schema, the researchability check, the side-by-side view.
5. **Graph builder and trace-back UI (2 weeks).** Canonicalisation, PROV-O export, the node → step → text path in the viewer.
6. **Subagents and tool invention (2 weeks).** Both are additions to the harness that the trace already handles.
7. **Evaluation (remaining time).** Faithfulness checks first, since they need no gold; then gold for a few concepts; then process measures.

Steps 2 and 3 are where the thesis risk sits; do them before polishing concepts.

## 5.1 Concepts: generating standalone, unambiguous interpretations

Generate concepts by enumerating the **ambiguity axes** of the question and combining their values, then merge and prune; do not ask the model for "a list of interpretations" in one shot. The one-shot list is what AmbigQA-style prompting does, and it tends to return three or four surface rewordings. Axes make the space explicit and give you a reason for every concept that exists.

**Generation, step by step**

1. *Axes.* The model names the open choices in the question: the entity type (author, paper, method), the measure (count, citation count, first-author count), the scope (all papers, one venue, one year), the aggregation unit (per author, per paper), and any undefined predicate ("best", "recent", "evaluate on"). For "best author": measure ∈ {papers, citations by corpus papers, first-author papers, distinct co-authors}, scope ∈ {corpus, ACL 2025, EMNLP 2025}.
2. *Combine.* Take the cross product, then drop combinations the model judges meaningless or redundant. Keep at most 12.
3. *Write briefs.* Turn each survivor into a research brief (schema in 5.2).
4. *Check.* Run the researchability check below on every brief; repair or drop.
5. *Rank and cut.* Order by plausibility of being what a user means; show the top 3 to 7, the rest behind "more".

**How many, and when only one.** A question yields one concept when every axis has a single value. "Which benchmarks do the RAG papers evaluate on?" still has two: what counts as a RAG paper (self-described, or uses retrieval at all) and what counts as evaluating on a benchmark (reports a number, or merely mentions). So "just one" will be rare and should be a result of the axes, not a shortcut. Show the single concept anyway so the pick step is uniform.

**What "researchable without asking back" means, and how to check it.** A brief is researchable when four things hold: the scope names a concrete set of papers; the measure names an operation (count, list, extract, rank, compare) over named fields; every column of the answer shape has a type; and no predicate is left undefined. Three checks, cheapest first:

| Check | How | Catches |
| --- | --- | --- |
| Structural | the brief JSON validates: all required fields present, no word from a banned list (best, important, recent, good) outside the `definition` field | missing scope, vague measures |
| Critic | a second model call with the four conditions as a checklist, asked to *judge* not to answer; Su and Cardie (May 2026) show models flag ambiguity reliably when asked explicitly, but almost never when just answering | hidden choices in the definition |
| Two-procedure test | ask the model twice, at temperature, to write the procedure it would follow; a third call judges whether the two procedures would produce the same table. Disagreement means an axis is still open | ambiguity the critic missed |

The two-procedure test is the one to report in the thesis; it is cheap and it measures what you care about: that two independent researchers would do the same thing.

**Corpus-blind generation.** Keep it. The benefit is the same one your supervisor gave for the evidence document D: concepts are not biased toward what is easy to find, so a concept the corpus cannot answer is a finding about the corpus, not an error. The risk is a user picking a concept that needs data the corpus lacks (external citation counts, say). Two mitigations, neither of which looks at the corpus content:

- Give the generator a **corpus fact sheet**: 337 CS papers, ACL 2025 and EMNLP 2025 plus 37 others, DBLP metadata (title, authors, venue, year), full text as Markdown, no external citation data. This is knowledge about the kind of corpus, not its contents.
- Make every brief carry a **needs** line ("needs: author lists; citation parsing within the corpus"). The user sees the cost before picking.

**Flag after the pick, yes, and by the agent itself.** The agent's first step is a feasibility check that is traced like any other step. If the concept cannot be answered, the run ends with an explicit, cited "not answerable from this corpus because …" claim. That is consistent with the design value that empty results are acceptable, and it gives evaluation a clean category.

One argument for the thesis text: IDRBench (January 2026) and InteractComp (October 2025, revised July 2026) both find that research agents almost never ask clarifying questions and that their accuracy on ambiguous queries collapses (best model 13.7% on InteractComp versus 71.5% with full context). The single pick step moves the one necessary interaction to the front, where the user can see all options at once, instead of hoping the agent asks mid-run.

## 5.2 Concept representation: the research brief

Show each concept as a **research brief**: a one-line definition with its measure, an answer shape, and two or three competency questions. The subschema is derived from the answer shape and shown only on request. No single candidate from the list meets all three criteria; the brief combines the two that users can compare (definition, answer shape) with the one that evaluation needs (competency questions).

| Candidate | Easy to compare | Precise enough to research | Usable for evaluation | Verdict |
| --- | --- | --- | --- | --- |
| Subschema (classes + relations) | poor: two subschemas for "most papers" and "most cited" look nearly identical | medium: says what, not how | good: it is the target graph's shape | derive it, do not lead with it |
| Competency questions | good: plain sentences | medium: CQs still hide the measure | good: each CQ becomes a test the answer must pass | include 2 to 3 per brief |
| Example answer shape (table or graph template) | best: the user sees what they will get | good: columns force the fields | best: the gold is a filled template | include, always |
| One-line definition + measure | good | best: names the operation and the scope | medium | include, as the first line |
| SPARQL-like pattern | poor for non-experts | best in principle, but there is no triple store any more | medium | drop |

**Schema** (one JSON object per concept, written by the generator, validated before the view):

```json
{
  "id": "c3",
  "title": "Most first-author papers at ACL 2025",
  "definition": "The author who appears as first author on the largest number of ACL 2025 papers in the corpus.",
  "measure": {"operation": "count", "of": "Paper", "group_by": "first_author", "order": "desc"},
  "scope": {"papers": "venue == ACL 2025"},
  "answer_shape": {"kind": "table", "columns": [{"name": "author", "type": "Person"}, {"name": "first_author_papers", "type": "integer"}, {"name": "papers", "type": "list<Paper>"}]},
  "competency_questions": ["Which ACL 2025 papers list X as first author?", "How many such papers does each author have?", "Are two spellings of one name merged?"],
  "needs": ["author order per paper", "venue per paper"],
  "subschema": {"classes": ["Person", "Paper", "Venue"], "relations": ["Paper firstAuthor Person", "Paper publishedAt Venue"]}
}
```

The `subschema` is computed from `answer_shape` and `measure` by a fixed mapping onto the ontology (DBLP for Person, Paper, Venue; CS-KG for Method, Task, Dataset, Metric), so it stays consistent across concepts. A graph-shaped answer uses `"kind": "graph"` with node and edge types instead of columns; "which benchmarks do RAG papers evaluate on" is a graph: Paper → evaluatesOn → Dataset, with an optional Metric per edge.

**The view.** Cards side by side, one per concept, in this order: title, definition, the answer shape rendered as an empty table header or a three-node mini-graph, the competency questions, the needs line. Differences between cards are highlighted by diffing the `measure` and `scope` fields, so that "most papers" and "most first-author papers" differ visibly in one word. A "show schema" toggle reveals the subschema. The user picks one card.

**Why this also serves evaluation.** The filled `answer_shape` is exactly what a gold answer key looks like for this concept, and each competency question is a check that a run's graph must satisfy. That links 5.2 to 5.6 without any further format. Bench4KE (2025) and CQ4OE (September 2026) give criteria for competency-question quality (answerable, atomic, not leading) that you can reuse as the brief's validation rules.

## 5.3 The agent's toolbox and harness

Give the agent **one action, a shell command**, in a sandbox that holds the corpus read-only, a writable scratch directory, Python, and three small commands the harness provides: `claim`, `spawn`, and `save_tool`. Everything else (grep, reading, scripts, new tools) the agent does through the shell. This is the mini-SWE-agent model, and it has two properties the thesis needs: the trace is uniform (one step = one command and its output) and "complete freedom" is literally true rather than a list of 33 permitted things.

**Starting kit: options**

| Option | Trace | Freedom | Known results |
| --- | --- | --- | --- |
| Shell only (mini-SWE-agent) | one event per command, trivial to replay | total | SWE-agent, NeurIPS 2024; Li et al. May 2026 use exactly grep, reads and scripts over raw text and beat BM25, dense and reranking baselines on BRIGHT and BEIR |
| Shell + typed file tools (read, grep, glob) | several event types | same, with hints | Sen et al. May 2026: the harness and how tool output is shown change scores more than the retrieval method; inline output beats output in files |
| Python REPL as the action (CodeAct) | one event per cell | total, code-shaped | CodeAct, ICML 2024; Recursive Language Models, December 2025, for long inputs held as variables |

Recommendation: shell only, with Python installed, and tool output shown **inline**, truncated to the first N lines with the path of the full output file appended. The agent can always `head`, `tail` or `grep` the full file. This follows the inline finding of Sen et al. without breaking the one-event-per-step trace.

**The three harness commands.** They are ordinary executables in the sandbox, so they appear in the trace like any other command, but the harness implements them and controls what they write.

- `claim --subject S --predicate P --object O --file paper.md --quote "..." [--via script.py --inputs ...]` records a fact with its anchor (5.5). It fails loudly if the quote is not found in the file. This is the only route into the knowledge graph.
- `spawn --brief sub.json --files a.md b.md --return schema.json` starts a subagent and blocks until it returns `result.json`. Several `spawn` calls in one command run in parallel, capped by the harness.
- `save_tool --name count_first_authors --script tools/x.py --description "..."` registers a script the agent wrote as a reusable tool (below).

**Subagents.** The agent decides when to launch them; the pattern you expect (grep to shortlist, then one subagent per paper or per batch of papers) is what Anthropic reports for its research system: an orchestrator writes each worker a narrow objective, an output format, and a boundary. Each subagent receives the chosen concept, a sub-brief written by the parent ("for these 12 papers, list every dataset the paper reports a number on, with the quote"), the file list, the return schema, and the same sandbox with its own scratch and its own event log under `sub/<id>/`. It has `claim` too; its claims go into the shared `claims.jsonl` tagged with the subagent id, so provenance never has to be merged. What is merged is only the `result.json` files, which the parent reads as ordinary command output. Give subagents the smaller model; give them no `spawn` (depth 1) in the first version.

**Tool invention.** Three steps, all logged:

1. The agent writes a script in scratch and runs it; this is already visible.
2. `save_tool` copies it into `tools/<name>/` with a `SKILL.md` header (name, description, usage, inputs, outputs) in the Agent Skills format Anthropic released as an open standard in late 2025. The harness records a `tool_created` event with the script's hash.
3. On the next turn the harness lists the tool's name and description in the agent's context (progressive disclosure: the body is read only when used). Every later call to the tool is a normal command whose event carries the tool hash, so a computed fact can cite the exact script version and its inputs.

Reuse across runs is a switch: off by default, so every evaluated run starts from an empty `tools/` and runs are comparable; on in a "warm" mode for a second experiment on whether tools accumulate. LATM (ICLR 2024), ToolMaker (ACL 2025) and Alita (2025) are the references for the idea; the Skills format is the reference for the packaging.

**Models and context.** Use the largest Qwen you can serve with a 128k context for the orchestrator and a smaller Qwen for subagents, both through LiteLLM as now. Four context devices, in the order to try them: subagents (the main one: the parent never reads papers whole); inline truncation with the full output on disk; observation masking, where tool outputs older than K steps are replaced by a one-line stub, as SWE-agent's history processors do; and, if a run still overflows, a compaction step whose summary is itself an event, so the trace stays complete. Only the first two are needed to start.

**Guardrails that do not restrict freedom.** Read-only corpus (a read-only bind mount or a separate user), no network, a CPU-time limit per command (120 s, extendable by the agent with a flag that is logged), and two budgets that are announced rather than enforced silently: a step budget (say 300 commands) and a token budget. When a budget is reached the agent is told and asked to conclude with what it has, so a budget stop is a visible event, not a crash. On a Slurm node without Docker, Apptainer is the practical sandbox.

**Logging from outside.** The interceptor runs in the harness process; the agent sees only its sandbox, where `events.jsonl` does not exist. Qin et al. (September 2026) showed that every mainstream local agent harness except one let the agent delete its own traces when asked; keeping the log outside the agent's reach is the fix they recommend, and it costs nothing here.

## 5.4 Visibility of the process

**A step is one model call or one command.** Nothing smaller (a token) and nothing larger (a "phase") is a step, because those are the two things that actually happen. Phases, if you want them, are labels the viewer infers; they are never written by the agent.

**The log: `events.jsonl`, append-only, one JSON object per line, hash-chained.** Five event types cover everything:

| Type | Fields beyond `id`, `t`, `agent`, `parent`, `prev_hash` | Produced by |
| --- | --- | --- |
| `model_call` | `model`, `input_hash`, `output` (the assistant message in full), `tokens_in`, `tokens_out` | interceptor, around every LLM request |
| `command` | `cmd`, `cwd`, `exit`, `stdout_path`, `stdout_head`, `duration_ms`, `tool` (name and hash if it is a saved tool) | interceptor, around every shell action |
| `claim` | `claim_id`, `triple`, `anchor`, `via` (script hash and input paths, for computed facts) | the `claim` command |
| `spawn` / `return` | `sub_id`, `brief_path`, `files`, `result_path` | the `spawn` command |
| `tool_created` | `name`, `path`, `hash`, `description` | the `save_tool` command |

`agent` is `main` or a subagent id; `parent` is the id of the event that caused this one (a `command` points at the `model_call` that asked for it; a subagent's first event points at the parent's `spawn`). `prev_hash` chains each line to the one before, so a run can be checked for gaps. The model's full input is not stored per event, since it is reconstructible from earlier events; its hash is, so a replay can verify it. Export to OpenTelemetry's GenAI conventions (`invoke_agent`, `execute_tool`, `chat` spans) is a one-page mapping if you ever want to use an existing trace UI; the conventions are still marked experimental as of mid-2026, so do not make them the primary format.

**How to show the trace: three views, one primary.**

1. **Claim-to-evidence graph (primary).** Nodes are claims, steps, scripts and quoted passages; edges are "produced by", "derived from", "input of". Clicking a fact in the knowledge graph opens this view centred on that claim. LEDGER (August 2026) builds exactly this from agent sessions and argues it is what a reviewer needs, since a chronological log hides which actions support which conclusion.
2. **Timeline.** Every event in order, subagents as collapsible bands, filterable by type. This is the debugging view and the one a reader of the thesis will recognise.
3. **Subagent tree with dataflow.** Parent and children, the files each one touched, what it returned. AgentTrails (July 2026) shows that turning the log into a provenance graph of actions and artifacts reveals dependencies the timeline misses; Graph of Trace (ACL 2026 demo) is a comparable tool aimed at scientific agents.

All three are projections of `events.jsonl` plus `claims.jsonl`; build the data model once and the views are cheap.

**Replay.** Two modes. *Offline replay* reads the log and re-renders the run without running anything: every command's stored output is shown, every model output is shown, and the hash chain is verified. This is what the viewer does and what you ship with the thesis. *Re-execution* reruns the commands against the frozen corpus and diffs their outputs with the stored ones; model calls are not rerun (the stored outputs are injected), so the check is whether the deterministic part of the run reproduces. That is also the mechanism that makes computed facts verifiable: rerun the script on its recorded inputs and compare.

**What this buys in the thesis.** Ding et al. (June 2026) coded 24 runnable research-agent systems and found only 38% release seeds or execution traces. A system whose every run is a self-verifying log, with replay, is a contribution in itself and worth a paragraph in the introduction.

## 5.5 Knowledge graph and provenance

**The agent emits claims as it goes; canonicalisation is a separate, logged step afterwards.** This keeps the step link (a claim knows which command made it) that a post-hoc extraction over the agent's final report would lose, and it keeps the agent's wording, which is what the quote supports. The canonical triple points back to the raw claim, so nothing is overwritten.

| Option | Keeps the step link | Faithful to the quote | Fits the ontology | Verdict |
| --- | --- | --- | --- | --- |
| Agent emits ontology triples directly | yes | medium: the agent squeezes findings into classes it was given | yes | too rigid |
| Extract from the final report (EDC over the answer) | no | medium | yes | loses provenance |
| Agent emits free claims via `claim`; Define and Canonicalise afterwards | yes | yes | yes, with an escape hatch | recommended |

**Vocabulary.** At emission the agent uses free predicates, with the ontology's relation names listed in its prompt as hints (`evaluatesOn`, `usesDataset`, `proposes`, `firstAuthor`). Canonicalisation maps each raw predicate to DBLP, CS-KG 2.0 or your own terms using EDC's Define and Canonicalise steps as now; a predicate that maps to nothing is kept under an `ours:` namespace and listed in a report, so alignment stays a later, visible decision rather than a silent drop. Entities get the same treatment: author strings are resolved against DBLP metadata, datasets and methods against CS-KG, with the raw mention kept.

**Provenance model: a small PROV-O subset, nothing more.** You need four classes and five relations.

- Entities: a *Claim*, a *Passage* (the anchored text), a *File* (a `.md` with its hash), a *Script* (a tool with its hash), a *Result* (a script's output file).
- Activities: a *Command* step and a *ModelCall* step, both identified by their event id.
- Agents: `main`, each subagent, the model (with its name and version), and the user (who picked the concept).
- Relations: `wasGeneratedBy` (Claim → Command), `wasDerivedFrom` (Claim → Passage, Claim → Result, canonical Claim → raw Claim), `used` (Command → File or Script), `wasAssociatedWith` (Command → agent), `wasInformedBy` (Command → ModelCall).

```turtle
:claim_041 a prov:Entity, ours:Claim ;
    ours:triple ( dblp:Paper_2025_acl_123 cskg:evaluatesOn cskg:Dataset_HotpotQA ) ;
    prov:wasGeneratedBy :cmd_0187 ;
    prov:wasDerivedFrom :passage_041 .
:passage_041 a prov:Entity, ours:Passage ;
    ours:inFile :file_2025_acl_123 ;
    ours:exact "We evaluate on HotpotQA and 2WikiMultiHopQA" ;
    ours:prefix "ments. " ; ours:suffix " using the" ;
    ours:start 18422 ; ours:end 18466 .
:cmd_0187 a prov:Activity ;
    prov:used :file_2025_acl_123 ;
    prov:wasAssociatedWith :sub_03 ;
    prov:wasInformedBy :model_0186 .
```

That is enough for every trace-back path in the design, and it is standard, so a reader can load it into any PROV tool. PROV-AGENT (2025) extends PROV with prompts, responses and decisions for MCP-based workflows; cite it as the closest prior model, and note that you need less because every decision is already a `ModelCall` activity.

**Pointing to exact text robustly: use three anchors together.**

| Anchor | Survives | Breaks on | Role |
| --- | --- | --- | --- |
| Line range | nothing beyond an identical file | any edit, and Markdown lines are long | do not use |
| Character offsets (`TextPositionSelector`) | identical file | any edit before the span | fast path, checked by the file hash |
| Quoted span with prefix and suffix (`TextQuoteSelector`) | re-conversion, small edits, reflow | the quote vanishing | fallback, and what the user sees |
| File hash (SHA-256) | nothing | nothing: it is the check | decides which path to use |

This is the W3C Web Annotation model, with `exact`, `prefix` (32 characters) and `suffix` (32 characters) plus `start` and `end`, and the hash on the file. Resolution: if the hash matches the manifest, use the offsets; otherwise find the exact quote, disambiguated by prefix and suffix; otherwise report the anchor as broken. The `claim` command refuses an anchor whose quote it cannot find, so a broken anchor can only come from a later change to the corpus. Freeze the corpus: convert once, record hashes in `manifest.json`, never regenerate in place. If the conversion must be redone, that is a new corpus version, and old runs keep pointing at the old files.

**Computed facts point to the script and the inputs, and the inputs are themselves claims.** `claim --via tools/count_first_authors.py --inputs claims.jsonl` records a Result derived from a Script run on named inputs. The rule to enforce: an aggregate (count, ranking, average) is only accepted when the per-item facts it aggregates are already claims. Then "Alice has 4 first-author papers at ACL 2025" derives from four paper-level claims, each with its quote, and the harness can check the arithmetic by re-running the script. A ranking over the whole corpus therefore shows, in the trace-back view, the script, its hash, the four claims, and the four quotes. That is the full chain the design promises, and nothing in it is reconstructed after the fact.

## 5.6 Evaluation and gold (sketch)

**Evaluate three layers, in this order: provenance faithfulness, answer correctness for the chosen concept, process cost and coverage.** The first needs no gold and can start as soon as the harness runs; the second keeps the evidence document D, now built per concept instead of per question; the third is what makes runs with different routes comparable.

| Layer | Question | Needs gold | Measures |
| --- | --- | --- | --- |
| 1. Provenance faithfulness | Does the cited text support each fact? | no (a human-labelled sample to calibrate the judge) | anchor resolves; passage relevant; passage supports the triple; computed facts recompute |
| 2. Answer correctness | Is the graph right and complete for the chosen concept? | yes: D and an answer key per concept | strict, entailed and soft precision and recall (carried over); set F1 for table-shaped answers; vital recall |
| 3. Process | What did it cost, and what did it look at? | partly (coverage uses D's paper list) | steps, tokens, wall time, papers opened, coverage of D's papers, budget stops, subagent count |
| 0. Concept quality | Are the concepts clear, distinct and the ones a person would want? | yes: human interpretations per question | concept recall against human interpretations (AmbigQA-style), two-procedure agreement, pairwise distinctness ratings |

**Layer 1 is the thesis's own contribution and the cheapest to do well.** Every claim carries a quote, so the check is: does this quote entail this triple? Use an LLM judge, but calibrate it. Goo et al. (July 2026) found that on identical outputs the measured unsupported-citation rate moved from about 3% to 18% depending only on how strict the verifier was, and Onweller et al. (May 2026) found that deep-research agents keep links valid above 94% while factual accuracy against the cited source sits at 39% to 77%. So: label 200 to 300 claims by two people (Argilla, Cohen's κ, as before), pick the judge threshold on half, report judge agreement on the other half, and always name the judge and protocol. Computed facts are checked mechanically by re-execution (5.4). The three Onweller dimensions map directly: anchor resolves (should be 100% by construction), passage relevant, passage supports.

**Layer 2: the evidence document D survives, and gets easier.** Build D per *concept*: screen every paper for the concept's answer shape ("does this paper report a number on any dataset?"), extract into the template, triage, review in Argilla, produce the answer key. Because the concept fixes the measure and the scope, the screening question is sharper than it was for a whole ambiguous question, and the answer key is a filled `answer_shape`, so matching is a comparison of two tables or two small graphs rather than two free triple sets. Zobel's argument still holds: D is built from the whole corpus without looking at any run. Keep the three matching levels; for table answers add set F1 over rows; keep vital recall for the facts reviewers mark as essential. Budget: D for 6 to 10 concepts from 3 to 5 questions is realistic for a thesis; pick concepts that differ in shape (a count, a list, a graph) and in difficulty (metadata-only versus full-text).

**Layer 3 answers "how do you compare runs that take different routes": you do not score the route.** Two runs on the same concept are compared on layers 1 and 2 and on cost. Route-independent process measures: papers opened out of D's relevant papers (coverage), commands per claim, tokens per claim, share of claims from subagents, whether a budget stop occurred. Run each concept 3 to 5 times (the agent is stochastic) and report BCa bootstrap intervals over runs and over concepts, as planned before. The route itself is described qualitatively from the trace views, with one or two runs shown in full in the thesis.

**Layer 0 is new and small.** For each question, two or three people write the interpretations they would want; concept recall is how many of those the generator covers. Add the two-procedure agreement rate from 5.1 as the automatic measure of "standalone".

**Ablations the design makes natural**, each a harness switch: tool output inline versus in files; subagents on or off; tool invention on or off; corpus-blind versus corpus-aware concepts; a smaller orchestrator model. The first two mirror Sen et al. and Li et al. and give you a direct comparison with published findings on a scientific corpus.

## Related work: verified and new

All arXiv ids from your section 6 that I checked resolve to the papers you describe. The table lists what I opened on 8 October 2026, what each contributes to the design, and the new papers found. "Opened" means I read the abstract page; "listed" means I confirmed the id and venue from a search result only. References from section 6 not in this table (CodeAct, LATM, ToolMaker, Alita, SWE-agent, EDC, Zobel, PROV-O and the evaluation papers) are established and I did not re-check them.

| Paper | Status | Use in the design |
| --- | --- | --- |
| [Li et al., Beyond Semantic Similarity: direct corpus interaction, May 2026](https://arxiv.org/abs/2605.05242) | opened | the closest prior system: grep, reads and scripts over raw text, no index; beats sparse, dense and reranking baselines on BRIGHT and BEIR (5.3) |
| [Sen et al., Is Grep All You Need?, May 2026](https://arxiv.org/abs/2605.15184) | opened | harness and tool-output presentation change results more than the retriever; inline output wins (5.3, ablations in 5.6) |
| [Su and Cardie, Knowing but Not Showing, May 2026](https://arxiv.org/abs/2605.25284) | opened | models judge ambiguity well when asked explicitly, almost never ask when answering; retrieved context makes it worse (5.1 critic check) |
| [Structured Uncertainty guided Clarification for LLM Agents, Findings of ACL 2026](https://aclanthology.org/2026.findings-acl.2028/) | listed | arXiv 2511.08798; published venue confirmed |
| [InteractComp, Oct 2025, v2 Jul 2026](https://arxiv.org/abs/2510.24668) | opened, new | search agents on ambiguous queries: best model 13.7% versus 71.5% with full context; supports the up-front pick (5.1) |
| [IDRBench, Jan 2026, v3 Sep 2026](https://arxiv.org/abs/2601.06676) | opened, new | interaction improves deep-research alignment on average but hurts in 20% of tasks; what is asked matters (5.1) |
| [CQ4OE, Sep 2026](https://arxiv.org/pdf/2609.26029) and [Bench4KE, 2025](https://arxiv.org/abs/2505.24554v3) | listed | competency-question quality criteria for brief validation (5.2) |
| [Ding et al., Autonomous Research Agents and the Verification Gap, Jun 2026](https://arxiv.org/abs/2608.05179) | opened | 24 runnable systems, 83% release code, 38% release seeds or traces; the reviewer checklist is a frame for the thesis (5.4) |
| [LEDGER: claim-to-evidence trace graphs, Aug 2026](https://arxiv.org/abs/2608.18398) | opened, new | the primary trace view: claims linked to actions, artifacts and checks (5.4) |
| [AgentTrails, Jul 2026](https://arxiv.org/abs/2607.18816) | opened, new | trajectories as provenance graphs of actions and artifacts; aligning several runs on one canvas (5.4, comparing runs) |
| [Graph of Trace, ACL 2026 demo](https://aclanthology.org/2026.acl-demo.29/) | listed | arXiv 2606.15116; venue confirmed; a trace visualiser for scientific agents (5.4) |
| [From Agent Traces to Trust: a survey, Jun 2026](https://arxiv.org/pdf/2606.04990) | listed | the title is "A Survey of Evidence Tracing and Execution Provenance in LLM Agents"; cite as the survey for 5.4 and 5.5 |
| [Qin et al., LLM Agents Can Easily Tamper With Their Own Traces, Sep 2026](https://arxiv.org/abs/2609.30266) | opened, new | all tested local harnesses but one let the agent delete traces; log through an interceptor outside the agent's control (5.3) |
| [PROV-AGENT, 2025](https://arxiv.org/abs/2508.02866) | opened | PROV extended with prompts, responses and decisions; the closest provenance model (5.5) |
| [Goo et al., Citation Faithfulness in Agentic Scientific Synthesis, Jul 2026](https://arxiv.org/abs/2607.20527) | opened, new | verifier strictness alone moves the unsupported rate from 3% to 18%; validate the judge on human gold and name the protocol (5.6) |
| [Onweller et al., Cited but Not Verified, May 2026](https://arxiv.org/abs/2605.06635) | opened, new | three citation dimensions (link works, relevant, fact check); accuracy falls as tool calls rise (5.6) |
| [AutoResearchBench, Apr 2026](https://arxiv.org/abs/2604.25256) | opened, new | literature-discovery benchmark with a "wide research" task scored by IoU against a target set; a model for scoring list-shaped concepts (5.6) |
| [Anthropic, Agent Skills, Oct 2025](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) | opened | the `SKILL.md` packaging and progressive disclosure for invented tools (5.3) |
| [OpenTelemetry GenAI semantic conventions, explained (Sep 2026)](https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained) | opened | `invoke_agent`, `execute_tool`, `chat` spans; still experimental, so an export target, not the primary log (5.4) |
| [Recursive Language Models, Dec 2025](https://arxiv.org/abs/2512.24601v1) | listed | long inputs as variables in a REPL with recursive calls; an alternative context device (5.3) |

Two things to verify yourself before citing: the exact venue of Ding et al. (arXiv only, as far as I saw) and whether CQ4OE has a published version.

## Changes to propose for thesis\_pipeline.html

To apply once you have reacted to the plan; each is an edit to one data block.

| Block | Change | Why |
| --- | --- | --- |
| `SOURCES` | add `li2026` (direct corpus interaction), `sen2026` (grep and harnesses), `ledger` (claim-to-evidence graphs), `qin2026` (trace tampering), `goo2026` (citation faithfulness), `skills` (Agent Skills format), `webanno` (W3C Web Annotation selectors); un-dash `codeact`, `latm`, `provo` if you confirm them | the new design now has a direct precedent and a provenance standard |
| `LANES` | rename the toolbox lane's sub to "shell, Python, three harness commands"; add a lane `trace` ("Trace and provenance", per run) between system and eval, or fold it into system as two boxes | the log and viewer are components, not a property of the agent box |
| `STAGES`, toolbox | `grep` → "Shell" (desc "grep, read, scripts"); add `claim` ("Claim tool", desc "fact + quote + step", ours: "only route into the graph"); keep `subagents` and `newtools` with `sources: ["skills", "latm"]` | matches 5.3 |
| `STAGES`, system | `concepts`: desc "ambiguity axes → briefs"; `view`: name "Research briefs", desc "definition · answer shape · CQs", ours "brief, schema derived"; `agent`: sources `["sweagent", "li2026", "sen2026"]`; `kg`: sources `["provo", "webanno"]`; `trace`: sources `["ledger"]` | matches 5.1, 5.2, 5.4, 5.5 |
| `STAGES`, eval | replace `runs`/`match`/`scores`/`results` with `faith` ("Faithfulness", desc "quote supports fact", llm, sources `["goo2026", "judge", "kappa"]`), `correct` ("Correctness", desc "vs answer key, 3 levels", sources `["webnlg", "euzenat", "trec"]`), `process` ("Process", desc "cost · coverage", sources `["bootstrap"]`); keep `open: true` on the lane until you have decided | the three layers of 5.6 |
| `STAGES`, gold | `screen`: desc "every paper, per concept"; `D`: desc "filled answer shape"; keep the rest | D per concept |
| `LINKS` | `["claim", "kg", "claims.jsonl"]`, `["agent", "trace", "events.jsonl"]`, `["view", "D", "answer shape = gold template"]`, `["kg", "faith"]`, `["key", "correct"]` | shows the file contracts from the plan |
| `STAGE_DETAILS` / `SOURCE_DETAILS` | one entry per new stage and source, drawn from the sections above | the panels |

When you are ready, tell me which rows to apply and I will edit the data blocks in a copy of the file.
