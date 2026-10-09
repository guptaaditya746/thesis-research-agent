# Context: thesis redesign, a free research agent with full provenance

*Aditya's original context note (8 Oct 2026), kept as the starting point of the redesign. The plan that
came out of it is `docs/plan.md`; the diagram is `thesis_pipeline.html`.*

## 1. Who I am and what the thesis is

I'm a Master's student (Aditya). My thesis builds a **research system that answers research questions over a
fixed corpus of scientific papers** and returns the answer as a **knowledge graph with full provenance**: the
user can see where every fact comes from.

- **The corpus:** 337 computer-science papers (37 originals, 150 from ACL 2025, 150 from EMNLP 2025), each
  verified against DBLP.
- **The questions:** two kinds.
  - *corpus-wide*: e.g. "Which benchmarks and datasets do the retrieval-augmented generation (RAG) papers
    evaluate on?"
  - *ambiguous*: e.g. "Who is the best author in the corpus?". Best by number of papers? By citations?
- **The models:** served locally (Qwen family, via LiteLLM on a Slurm GPU node).

## 2. What exists today (previous design)

This is built and working. Most of the code was written with an AI assistant.

- **Corpus:** PDFs parsed with GROBID into passages with stable ids, a BM25 and dense-embedding index, and an
  ontology (DBLP schema + CS-KG 2.0 subset + our own terms).
- **Four answering paths:** *Fast* (fixed pipeline); *Adaptive* (pipeline + evidence review + verification);
  *Agentic* (an LLM agent with 33 prescribed corpus tools over MCP, then the same extraction pipeline);
  *External* (a mini-SWE-agent baseline with bash).
- **Extraction:** EDC-style (Extract → Define → Canonicalize) into ontology triples, then evidence review, a
  cited answer and an answer graph.
- **Gold standard:** per question, an **evidence document D** built offline from the whole corpus (screen every
  paper, extract facts). A model triages D's triples, people review them in Argilla (with Cohen's κ), and the
  result is an **answer key**. D is my supervisor's idea: build gold independently of the systems, to avoid
  pooling bias (Zobel 1998).
- **Evaluation:** matching at three levels (strict, entailed via RDFS/OWL rules and Euzenat's semantic
  precision/recall, soft via variants + an LLM judge); vital recall (TREC RAG 2024 nuggets) and judged
  precision; AmbigQA-style set F1 for ambiguous questions; BCa bootstrap intervals; results by question
  complexity × path.

The system part is being redesigned (next section). The evaluation and gold parts will be redesigned
afterwards.

## 3. The new design

**Flow:** Question → **Concepts** → **Concept view** → **User picks one** → **Agent** → **Knowledge graph** →
**Trace back**.

1. **Concepts.** Given a question, the system proposes **standalone, non-ambiguous concepts**: as many as
   sensible, each precise enough to research without asking back. They are generated **without any knowledge
   of what the system already has**. Example: "best author" → "most papers in the corpus" / "most cited by
   corpus papers" / "most first-author papers at ACL 2025" / ….
2. **Concept view.** The concepts are presented so the user can compare them (e.g. each as a subschema). The
   representation is open.
3. **User picks one.** The only human steering point.
4. **Agent.** It works on the corpus, which is now **just parsed PDFs as Markdown files** (one `.md` per
   paper, no index, no embeddings, no pre-extracted facts). It has **complete freedom** in how it searches and
   retrieves: grep and read files; write and run Python scripts; shortlist papers then **launch subagents**;
   **invent new tools**. **Every step must be visible.** Time cost and empty results are acceptable.
5. **Knowledge graph.** The agent's findings as a graph; every node and edge links to its provenance (agent
   step, exact text in a `.md` file).
6. **Trace back.** Graph node → agent step → exact source text.

**Gone from the old design:** the search index, the fixed pipeline, the Fast/Adaptive/External paths, and
the 33 prescribed tools.

## 4. Decisions already made, and constraints

- One system: the free agent. The old paths are not kept as baselines in the diagram.
- Corpus = Markdown files only; the PDF-to-Markdown conversion must keep text stable so provenance can point
  to exact places.
- The user picks exactly one concept, and only that concept is researched.
- Concepts are proposed without looking at the corpus.
- Full visibility and full provenance are the core values, not speed.
- Evaluation and gold will be redesigned later and must fit the new design; D may survive in some form.

## 5. Open questions (answered in docs/plan.md)

5.1 Concepts: generation, how many, researchability, corpus-blind generation.
5.2 Concept representation: subschema, competency questions, answer shape, definition + measure, query
pattern, or a combination.
5.3 Agent toolbox and harness: starting kit, subagents, tool invention, models and context, guardrails.
5.4 Visibility: what a step is, log format, how to show and replay a trace.
5.5 Knowledge graph and provenance: triple emission, vocabulary, provenance model, robust text anchors,
computed facts.
5.6 Evaluation and gold: what to evaluate, whether D survives, comparing runs with different routes.

## 6. Related work found before the redesign

AmbigQA (Min et al., EMNLP 2020); Su & Cardie, arXiv 2605.25284; Structured Uncertainty guided
Clarification, arXiv 2511.08798; CQ4OE, arXiv 2609.26029; Li et al., Beyond Semantic Similarity, arXiv
2605.05242; Sen et al., Is Grep All You Need?, arXiv 2605.15184; SWE-agent (NeurIPS 2024) and
mini-SWE-agent; CodeAct (ICML 2024); Recursive Language Models, arXiv 2512.24601; Anthropic's multi-agent
research system post (2025); LATM (ICLR 2024); ToolMaker (ACL 2025); Alita, arXiv 2505.20286; Deep Research
Agents roadmap, arXiv 2506.18096; Deep Research survey, arXiv 2508.12752; Ding et al., arXiv 2608.05179;
OpenScholar, arXiv 2411.14199; PaperQA2; DeepResearch Bench, arXiv 2506.11763; ResearcherBench, arXiv
2507.16280; W3C PROV-O; PROV-AGENT, arXiv 2508.02866; From Agent Traces to Trust, arXiv 2606.04990; Graph of
Trace, arXiv 2606.15116; Agent Trajectory Explorer (AAAI 2025); AgentLens; LLM-empowered KG construction
survey, arXiv 2510.20345; EDC (EMNLP 2024); KGGen (2025); ORKG; nanopublications; Euzenat 2007; WebNLG 2020;
Text2KGBench; BenchIE; TREC RAG 2024; Zobel 1998; Cohen's κ; bootstrap intervals.
