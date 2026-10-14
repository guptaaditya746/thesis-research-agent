/**
 * Fixture data for the MSW handlers (dev with VITE_MOCK=1, and the tests), shaped like the
 * backend's responses (webapp/models.py) and the files behind them (score.json, report.json, the
 * gold report).
 *
 * Modelled on the repo's own test runs (agent/tests/runs.py: research_run, baseline_run) and the
 * D1 fixture papers (tests/D1/docling, numbered p1..p10 as agent/tests/conftest.py write_corpus
 * does): every quote and passage below is real text from those papers at its real offsets.
 *
 * - q01 has a picked graph concept, a reviewed key and three runs: claim_on (RUN.on, from the
 *   m4-72 batch, with a sub-agent, a literal edge and a rejected claim), claim_off (RUN.off, with
 *   the attach step) and RUN.live, a web-app run still going (the mock stream finishes it).
 * - q02's runs ended at the budget with no answer (as the M1-real runs did); q07 has three
 *   proposed briefs and no pick; most other questions have nothing yet.
 */
import type {
  Answer,
  AnswerKey,
  AppConfig,
  Claim,
  ConceptBrief,
  EventRecord,
  FactLabel,
  FactWalk,
  GoldEntry,
  GraphEdge,
  Job,
  JobStep,
  KeyRow,
  KnowledgeGraph,
  ModelCall,
  Passage,
  Pick as ConceptPick,
  Question,
  QuestionResult,
  ResultsReport,
  RunDetail,
  RunSummary,
  Score,
  Step,
  SupportDetail,
  Verdict,
} from "@/api/types"
import { utf16Index } from "@/lib/passage"

/** The fixture runs' ids, as the backend names them (<batch>~<name>; `web` for the app's own runs). */
export const RUN = {
  on: "m4-72~q01-claim_on-r1-a1",
  off: "m4-72~q01-claim_off-r1-a1",
  live: "web~q01-claim_on-s2-web20261013T080209-3f2a",
  q02on: "m4-72~q02-claim_on-r1-a1",
  q02off: "m4-72~q02-claim_off-r1-a1",
  q07: "web~q07-claim_on-s1-web20261012T140458-9c1d",
} as const

// --- passages (real text of the D1 papers) -------------------------------------------------------

const P1_TITLE = "Uncovering the Impact of Chain-of-Thought Reasoning for Direct Preference Optimization: Lessons from Text-to-SQL"

/** A window of a paper as GET /api/corpus returns it, the span given in file offsets (code points). */
function passage(paper_id: string, title: string, offset: number, text: string, start: number, end: number, length: number): Passage {
  const highlight = { start: start - offset, end: end - offset }
  return {
    paper_id, title, text, offset, length, highlight,
    highlight_utf16: { start: utf16Index(text, highlight.start), end: utf16Index(text, highlight.end) },
  }
}

export const PASSAGES = {
  spider: passage(
    "p1", P1_TITLE, 2770,
    "nhanced dataset (Orange). This shows that CoT reasoning is crucial for unlocking DPO's potential, ensuring its effectiveness and stability.\n\n<!-- image -->\n\nand supervised fine-tuning (SFT) methods (Pourreza and Rafiei, 2024b; Li et al., 2023, 2024a). Prompting-based methods often rely on powerful closed-source LLMs, making them costly and slow, and raising data privacy concerns. In contrast, SFT trains open-source, deployable LLMs using benchmark datasets like Spider and Bird. However, SFT performance is often limited by the scarcity of highquality training data, which is expensive and timeconsuming to create.\n\nRecent studies in complex reasoning tasks, such as math word problems (Xu et al., 2024) and code generation (Zhang et al., 2024), have demonstrated that preference optimization algorithms ( e.g. , DPO (Rafailov et al., 2024b), KTO (Ethayarajh et al., 2024), SimPO (Meng et al., 202",
    3190, 3251, 61_204,
  ),
  author: passage(
    "p1", P1_TITLE, 0,
    "## Uncovering the Impact of Chain-of-Thought Reasoning for Direct Preference Optimization: Lessons from Text-to-SQL\n\nHanbing Liu 1 * , Haoyang Li 2,3 * , Xiaokang Zhang 2,3 , Ruotong Chen 2 , Haiyong Xu 5 , Tian Tian 5 , Qi Qi 1 , Jing Zhang 2,4 †\n\n2 School of Information, Renmin University of China, Beijing, China, 3 Key Laboratory of Data Engineering and Knowledge Engineering, Beijing, China, 4 Engineering Research Center of Database and Business Intelligence, Beijing, China, 5 China Mobile Information Technology Center\n\n1 Gaoling School of Artificial Intel",
    117, 145, 61_204,
  ),
  gsm8k: passage(
    "p5", "BIG5-CHAT: Shaping LLM Personalities Through Training on Human-Grounded Data", 6124,
    " come at the cost of diminished cognitive performance. This aligns closely with our motivation by highlighting potential risks to authenticity and effectiveness in applications such as mental health platforms or conversational agents. To explore this, we evaluate our aligned models not only with traditional personality tests but also across five reasoning domains: social reasoning using SocialIQA (Sap et al., 2019), math reasoning using GSM8K (Cobbe et al., 2021) and MathQA (Amini et al., 2019), hallucination detection using TruthfulQA (Lin et al., 2021), commonsense reasoning using CommonsenseQA (Talmor et al., 2019) and PIQA (Bisk et al., 2020), and general reasoning using MMLU (Hendrycks et al., 2020) and GPQA (Rein et al., 2023). Our experiments show that models trained with higher levels of conscientiousness and agreeableness consistently outperform",
    6544, 6570, 88_431,
  ),
  hotpotqa: passage(
    "p6", "How Do Large Vision-Language Models See Text in Image? Unveiling the Distinctive Role of OCR Heads", 19282,
    "vated.\"\n\n## 5 Unveiling the Functional Roles of OCR Heads in Downstream Applications\n\nTo compare the impact of OCR heads and retrieval heads on downstream tasks, we conduct three complementary analyses: CoT prompting, attention head masking, and sink token redistribution. We also use the OCR-VQA (Mishra et al., 2019), Multi-Page DocVQA (Tito et al., 2023), DocVQA (Mathew et al., 2021), NQ (Kwiatkowski et al., 2019), and HotpotQA (Yang et al., 2018) datasets for the downstream tasks. Furthermore, the evaluation metric for all the datasets in the downstream tasks is the F1 score.\n\nTable 2: The average scores of the top 10 OCR and Retrieval heads when CoT prompting is applied in the OCR-VQA task.\n\n| Qwen2-VL-7B    | Method              |   Score |\n|----------------|---------------------|---------|\n| Top10          | Avg OCR Score       |  0.4004 |\n| OCR H",
    19702, 19726, 47_918,
  ),
  megapairs: passage(
    "p4", "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval", 0,
    "## MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval\n\nJunjie Zhou 1 , 2 * , Yongping Xiong 1 ∗ , Zheng Liu 2 , 5 † , Ze Liu 3 , 2 , Shitao Xiao 2 , Yueze Wang 2 , Bo Zhao 4 , Chen Jason Zhang 5 , Defu Lian 3 †\n\nBeijing University of Posts and Telecommunications\n\n1 State Key Laboratory of Networking and Switching Technology,\n\n2 Beijing Academy of Artificial Intelligence\n\n4 Shanghai Jiao Tong University, 5 The Hong Kong Polytechnic University {junjiebupt, zhengliu1026}@",
    3, 71, 52_660,
  ),
} satisfies Record<string, Passage>

/** The exact quote of a passage (what the claim's anchor covers). */
export const quoteOf = (p: Passage) => p.text.slice(p.highlight_utf16!.start, p.highlight_utf16!.end)
/** The anchor of a passage's quote: raw offsets in the paper file. */
export const anchorOf = (p: Passage) => ({ start: p.offset + p.highlight!.start, end: p.offset + p.highlight!.end })

// --- config and questions ------------------------------------------------------------------------

export const config: AppConfig = {
  corpus: "/scratch/thesis/corpus-md",
  runs_root: "/scratch/thesis/runs",
  gold_root: "/scratch/thesis/gold-data",
  concepts_root: "/scratch/thesis/concepts",
  llm_base_url: "http://127.0.0.1:4000/v1",
  llm_key_set: true,
  argilla_url: "http://127.0.0.1:26900",
}

const Q = (id: string, category: string, question: string, source: string): Question => ({
  id, category, question, source, notes: null,
  concept: { status: "none", title: null, picked_by: null },
  gold: { status: "none", rows: null, facts: null, stage: null },
  runs: { claim_on: 0, claim_off: 0 },
})

export const QUESTIONS: Question[] = [
  Q("q01", "corpus_wide", "Which benchmarks and datasets do the retrieval-augmented generation papers in the corpus evaluate on?", "nlp33"),
  Q("q02", "corpus_wide", "What kinds of attacks or safety risks do the LLM safety and red-teaming papers in the corpus evaluate?", "nlp34"),
  Q("q03", "corpus_wide", "Which low-resource languages do the papers in the corpus study, and for which tasks?", "nlp35"),
  Q("q04", "corpus_wide", "What approaches do the papers in the corpus propose to detect or reduce hallucinations in large language models?", "nlp36"),
  Q("q05", "corpus_wide", "Which metrics do the papers in the corpus use to measure hallucination or factual errors?", "nlp42"),
  Q("q06", "corpus_wide", "Which EMNLP 2025 papers in the corpus introduce a new benchmark for evaluating large language models, and what does each benchmark measure?", "nlp44"),
  Q("q07", "ambiguous", "Which retrieval-augmented generation approach is best among the papers in the corpus?", "nlp30"),
  Q("q08", "ambiguous", "Which paper in this corpus is the most influential?", "nlp48"),
  Q("q09", "ambiguous", "Who are the leading researchers on retrieval-augmented generation in this corpus?", "nlp49"),
  Q("q10", "ambiguous", "Which evaluation benchmark is the most popular among the papers in the corpus?", "nlp53"),
  Q("q11", "ambiguous", "Which large language model is used most successfully across the papers in the corpus?", "nlp62"),
  Q("q12", "ambiguous", "Is retrieval augmentation or fine-tuning the better approach according to this corpus?", "nlp66"),
]

const Q01_SHA = "c9ee5264652bee36c072408974aa3b46a0116f27372671768fed3a38b2e32284"

// The concept the q01 runs use (agent/tests/fixtures/concept_graph.json).
export const Q01_CONCEPT: ConceptBrief = {
  id: "c2",
  title: "Benchmarks used by RAG papers",
  definition: "Every dataset that a retrieval-augmented generation paper in the corpus reports results on, with the metric it reports.",
  measure: { operation: "list", of: "Dataset", group_by: "Paper" },
  scope: { papers: "papers that propose or evaluate a retrieval-augmented generation method" },
  answer_shape: {
    kind: "graph",
    nodes: [{ type: "Paper" }, { type: "Dataset" }, { type: "Metric" }],
    edges: [{ source: "Paper", predicate: "evaluatesOn", target: "Dataset", attributes: [{ name: "metric", type: "Metric" }] }],
  },
  competency_questions: ["Which datasets does paper X evaluate its RAG method on?", "Which metric does paper X report on dataset Y?"],
}

export const BRIEFS: Record<string, ConceptBrief[]> = {
  q01: [
    {
      id: "c1",
      title: "Evaluation datasets of retrieval-augmented generation papers",
      definition: "Each dataset on which at least one corpus paper evaluates a retrieval-augmented generation (RAG) method, with the papers that report results on it.",
      measure: { operation: "list", of: "Dataset", group_by: "dataset", order: "desc" },
      scope: {
        papers: "corpus papers that propose or evaluate a method in which retrieved passages are given to a language model that generates the output",
        datasets: "datasets with reported results (tables or text) in those papers; datasets only cited or only used for training do not count",
      },
      answer_shape: {
        kind: "table",
        columns: [{ name: "dataset", type: "Dataset" }, { name: "papers", type: "list<Paper>" }, { name: "paper_count", type: "integer" }],
      },
      competency_questions: [
        "Which datasets does a given RAG paper report results on?",
        "How many corpus papers evaluate a RAG method on Natural Questions?",
        "Are name variants of one dataset (NQ, Natural Questions, NaturalQuestions) counted as one dataset?",
      ],
      needs: ["which papers propose or evaluate a RAG method", "the evaluation datasets per paper"],
    },
    Q01_CONCEPT,
    {
      id: "c3",
      title: "Most used benchmarks among RAG papers",
      definition: "The ten datasets that the most retrieval-augmented generation papers in the corpus report results on.",
      measure: { operation: "rank", of: "Dataset", group_by: "dataset", order: "desc", limit: 10 },
      scope: { papers: "papers that propose or evaluate a RAG method", datasets: "datasets with reported results" },
      answer_shape: {
        kind: "table",
        columns: [{ name: "rank", type: "integer" }, { name: "dataset", type: "Dataset" }, { name: "paper_count", type: "integer" }],
      },
      competency_questions: ["Which dataset do most RAG papers evaluate on?", "How are ties in paper count ordered?"],
    },
  ],
  q02: [
    {
      id: "c1",
      title: "Attack and risk types evaluated by safety papers",
      definition: "Each kind of attack or safety risk that an LLM safety or red-teaming paper in the corpus evaluates, with the papers.",
      measure: { operation: "list", of: "Risk", group_by: "risk" },
      scope: { papers: "papers whose main contribution is an LLM safety, jailbreak or red-teaming study" },
      answer_shape: {
        kind: "table",
        columns: [{ name: "risk", type: "Risk" }, { name: "papers", type: "list<Paper>" }, { name: "paper_count", type: "integer" }],
      },
      competency_questions: ["Which risks does paper X evaluate?", "Is prompt injection counted apart from jailbreaking?"],
    },
  ],
  q07: [
    {
      id: "c1",
      title: "Best reported score on shared benchmarks",
      definition: "For each benchmark that at least two RAG papers report, the approach with the highest reported score.",
      measure: { operation: "rank", of: "Method", group_by: "benchmark", order: "desc", limit: 1 },
      scope: { papers: "RAG papers with results on a benchmark another RAG paper also reports", scores: "as reported, same metric only" },
      answer_shape: {
        kind: "table",
        columns: [
          { name: "benchmark", type: "Dataset" }, { name: "metric", type: "Metric" }, { name: "approach", type: "Method" },
          { name: "score", type: "number" }, { name: "paper", type: "Paper" },
        ],
      },
      competency_questions: ["Which approach scores highest on HotpotQA?", "Are scores with different metrics compared?"],
    },
    {
      id: "c2",
      title: "Head-to-head comparisons",
      definition: "Every reported comparison in which one RAG approach outperforms another on a named dataset.",
      measure: { operation: "list", of: "Comparison" },
      scope: { papers: "RAG papers that compare against another RAG approach" },
      answer_shape: {
        kind: "graph",
        nodes: [{ type: "Method" }, { type: "Dataset" }],
        edges: [{ source: "Method", predicate: "outperforms", target: "Method", attributes: [{ name: "dataset", type: "Dataset" }, { name: "margin", type: "number" }] }],
      },
      competency_questions: ["Which approaches does method X beat?", "On which dataset was the comparison made?"],
    },
    {
      id: "c3",
      title: "Most adopted RAG approaches",
      definition: "The RAG approaches that the most corpus papers use or build on.",
      measure: { operation: "count", of: "Paper", group_by: "approach", order: "desc" },
      scope: { papers: "all corpus papers that use a RAG approach" },
      answer_shape: {
        kind: "table",
        columns: [{ name: "approach", type: "Method" }, { name: "papers", type: "list<Paper>" }, { name: "paper_count", type: "integer" }],
      },
      competency_questions: ["How many papers build on approach X?", "Are variants of one approach merged?"],
    },
  ],
}

export const PICKS: Record<string, ConceptPick> = {
  q01: { choice: 2, picked_by: "provisional-first", reason: "Graph shape keeps the metric per paper and dataset.", title: Q01_CONCEPT.title, concept_sha256: Q01_SHA },
  q02: { choice: 1, picked_by: "user", reason: "Only one brief; scope matches the question.", title: "Attack and risk types evaluated by safety papers", concept_sha256: "5d1f0e7c3b2a19f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a3928170" },
}

// --- runs ------------------------------------------------------------------------------------------

let taskNo = 0
const nextTask = () => `t${String(++taskNo).padStart(6, "0")}`

const call = (tokens: number, seconds: number, reply = "command", parse = "strict", final_answer = false): ModelCall => ({
  task_id: nextTask(), status: "finished", tokens, prompt_tokens: tokens - 160, completion_tokens: 160, seconds, parse, reply,
  finish_reason: "stop", final_answer, error: null,
})

const step = (n: number, s: Partial<Step>): Step => ({
  step: n, agent_id: "main", origin: "research", phase: "research", started_at: null, ended_at: null, model_call: null,
  command: null, exit_code: 0, timed_out: false, output_head: null, output_bytes: null, output_file: null, repeat: null,
  claims: [], coverage: [], spawned: [], fact_id: null, ...s,
})

const claimCmd = (file: string, pattern: string, triples: [string, string, string][]) =>
  `q=$(rg -o -N -m1 '${pattern}' "$CORPUS/${file}")\n` +
  triples.map(([s, p, o]) => `jq -n --arg q "$q" '{s: "${s}", p: "${p}", o: "${o}", file: "${file}", quote: $q}' | claim`).join("\n")

const ok = (...ids: string[]) => ids.map((id) => `{"ok": true, "claim_id": "${id}"}`).join("\n")

function accepted(id: string, s: string, p: string, o: string, from: Passage, at: number, extra: Partial<Claim> = {}): Claim {
  return {
    claim_id: id, task_id: nextTask(), status: "accepted", reason: null, s, p, o, file: `${from.paper_id}.md`, paper_id: from.paper_id,
    quote: quoteOf(from), quote_submitted: quoteOf(from), step: at, agent_id: "main", origin: "research", anchor: anchorOf(from), ...extra,
  }
}

const ref = (c: Claim) => ({ claim_id: c.claim_id, status: c.status, reason: c.reason, s: c.s, p: c.p, o: c.o })

const configFor = (runId: string, condition: string, seed: number, created: string): Record<string, unknown> => ({
  schema_version: 1, run_id: runId.split("~").at(-1), created_at: created, condition,
  models: { orchestrator: { alias: "orch-model", name: "Qwen/Qwen3.8-27B-FP8", revision: "017b9c7", thinking: false } },
  budget: { steps: 60, tokens: 2_000_000, announced: true },
  sampling: { temperature: 0.7, seed },
  prompt: { version: condition === "claim_on" ? "v2" : "v2-baseline", sha256: "4be1c3d0a8f2e7b96c51d3a0f4e2b8c7d6a5f4e3d2c1b0a9f8e7d6c5b4a39281" },
  hashes: { concept_sha256: Q01_SHA },
  git_commit: "bcbbb36",
  sandbox: { mode: "landlock", abi: 8 },
})

// RUN.on: claim on, finished (agent/tests/runs.py research_run, with real quotes).
const onClaims: Claim[] = [
  accepted("claim-000001", "p1", "evaluatesOn", "Spider", PASSAGES.spider, 3),
  accepted("claim-000002", "p1", "evaluatesOn", "BIRD", PASSAGES.spider, 3),
  accepted("claim-000003", "p5", "evaluates on", "GSM8K", PASSAGES.gsm8k, 4),
  accepted("claim-000004", "p1", "authored by", "Hanbing Liu", PASSAGES.author, 4),
  accepted("claim-000005", "p6", "evaluatesOn", "HotpotQA", PASSAGES.hotpotqa, 6, { agent_id: "sub-01" }),
  accepted("claim-000006", "p4", "proposes", "MegaPairs", PASSAGES.megapairs, 6, { agent_id: "sub-01" }),
  accepted("claim-000007", "p4", "title", "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval", PASSAGES.megapairs, 6, { agent_id: "sub-01" }),
  {
    claim_id: null, task_id: nextTask(), status: "rejected", reason: "not_found", s: "p3", p: "evaluatesOn", o: "HellaSwag", file: "p3.md", paper_id: "p3",
    quote: "we evaluate on HellaSwag with exact match", quote_submitted: "we evaluate on HellaSwag with exact match", step: 7, agent_id: "main",
    origin: "research", anchor: null,
  },
]
const [c1, c2, c3, c4, c5, c6, c7, r1] = onClaims

const onSteps: Step[] = [
  step(1, {
    model_call: call(8_912, 4.1),
    command: `rg -l -i 'retrieval-augmented|retrieval augmented|\\bRAG\\b' "$CORPUS" | sort | head -40`,
    output_head: "p1.md\np3.md\np4.md\np6.md\np9.md", output_bytes: 29,
  }),
  step(2, {
    model_call: call(9_604, 5.3),
    command: `rg -n -i 'spider|bird' "$CORPUS/p1.md" | head -5`,
    output_head: "9:and supervised fine-tuning (SFT) methods (Pourreza and Rafiei, 2024b; Li et al., 2023, 2024a). Prompting-based methods often rely on powerful closed-source LLMs, making them costly and slow, and raising data privacy concerns. In contrast, SFT trains open-source, deployable LLMs using benchmark datasets like Spider and Bird. …",
    output_bytes: 1_402,
  }),
  step(3, {
    model_call: call(10_288, 6.0),
    command: claimCmd("p1.md", "deployable LLMs using benchmark datasets like Spider and Bird", [["p1", "evaluatesOn", "Spider"], ["p1", "evaluatesOn", "BIRD"]]),
    output_head: ok("claim-000001", "claim-000002"), output_bytes: 84, claims: [ref(c1), ref(c2)],
  }),
  step(4, {
    model_call: call(11_150, 7.2),
    command: `${claimCmd("p5.md", "math reasoning using GSM8K", [["p5", "evaluates on", "GSM8K"]])}\n${claimCmd("p1.md", "Hanbing Liu 1 \\* , Haoyang Li", [["p1", "authored by", "Hanbing Liu"]])}`,
    output_head: ok("claim-000003", "claim-000004"), output_bytes: 84, claims: [ref(c3), ref(c4)],
  }),
  step(5, {
    model_call: call(11_702, 3.9),
    command: "spawn --task 'Find the evaluation datasets of p4 and p6 and claim each one.'",
    output_head: '{"agent_id": "sub-01", "status": "started"}', output_bytes: 44, spawned: ["sub-01"],
  }),
  step(6, {
    agent_id: "sub-01",
    model_call: call(6_240, 2.8),
    command: `${claimCmd("p6.md", "and HotpotQA \\(Yang et al", [["p6", "evaluatesOn", "HotpotQA"]])}\n${claimCmd("p4.md", "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval", [["p4", "proposes", "MegaPairs"], ["p4", "title", "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval"]])}`,
    output_head: ok("claim-000005", "claim-000006", "claim-000007"), output_bytes: 126, claims: [ref(c5), ref(c6), ref(c7)],
  }),
  step(7, {
    model_call: call(12_431, 8.8),
    command: `sed -n 1,40p "$CORPUS/p3.md"\njq -n '{s: "p3", p: "evaluatesOn", o: "HellaSwag", file: "p3.md", quote: "we evaluate on HellaSwag with exact match"}' | claim`,
    exit_code: 1,
    output_head: "## SCAR: Data Selection via Style Consistency-Aware Response Ranking for Efficient Instruction-Tuning of Large Language Models\n\nZhuang Li 1 , Yuncheng Hua 2 , Thuy-Trang Vu 3 , Haolan Zhan 3 , Lizhen Qu 3 , Gholamreza Haffari 3\n…\n{\"ok\": false, \"reason\": \"not_found\"}",
    output_bytes: 6_120, claims: [ref(r1)],
  }),
  step(8, { phase: "conclude", model_call: call(1_093, 12.4, "answer", "answer_json_block", true), exit_code: null }),
]

const graphRow = (n: number, s: string, o: string, claims: string[], origin: string, metric: string | null = null) => ({
  id: `r${n}`, source: s, source_type: "Paper", predicate: "evaluatesOn", target: o, target_type: "Dataset",
  attributes: { metric }, facts: [{ id: `f${n}`, s, p: "evaluatesOn", o, claims, origin }],
})

const onAnswer: Answer = {
  concept_sha256: Q01_SHA,
  kind: "graph",
  rows: [
    graphRow(1, "p1", "Spider", ["claim-000001"], "research"),
    graphRow(2, "p1", "BIRD", ["claim-000002"], "research"),
    graphRow(3, "p5", "GSM8K", ["claim-000003"], "research"),
    graphRow(4, "p6", "HotpotQA", ["claim-000005"], "research", "F1"),
    graphRow(5, "p3", "HellaSwag", [], "research"),
  ],
  notes: "Datasets found by full-text search for RAG papers. The HellaSwag result of p3 could not be quoted (claim rejected: not_found).",
}

// RUN.off: claim off, then the attach step (agent/tests/runs.py baseline_run).
const offClaims: Claim[] = [
  accepted("claim-000001", "p1", "evaluatesOn", "Spider", PASSAGES.spider, 5, { origin: "attach" }),
  accepted("claim-000002", "p5", "evaluatesOn", "GSM8K", PASSAGES.gsm8k, 6, { origin: "attach" }),
  accepted("claim-000003", "p6", "evaluatesOn", "HotpotQA", PASSAGES.hotpotqa, 7, { origin: "attach" }),
]
const [a1, a2, a3] = offClaims
const attachStep = (n: number, s: Partial<Step>) => step(n, { phase: "attach", origin: "attach", ...s })

const offSteps: Step[] = [
  step(1, { model_call: call(8_640, 3.8), command: `rg -n -i 'spider|bird' "$CORPUS/p1.md" | head -5`, output_head: "9:and supervised fine-tuning (SFT) methods … deployable LLMs using benchmark datasets like Spider and Bird. …", output_bytes: 1_402 }),
  step(2, { model_call: call(9_311, 4.6), command: `rg -n 'GSM8K' "$CORPUS/p5.md"`, output_head: "23:… math reasoning using GSM8K (Cobbe et al., 2021) and MathQA (Amini et al., 2019) …", output_bytes: 988 }),
  step(3, { model_call: call(10_052, 5.1), command: `rg -n 'HotpotQA' "$CORPUS/p6.md" "$CORPUS/p3.md"`, output_head: "p6.md:61:… NQ (Kwiatkowski et al., 2019), and HotpotQA (Yang et al., 2018) datasets for the downstream tasks. …", output_bytes: 1_150 }),
  step(4, { phase: "conclude", model_call: call(2_147, 9.6, "answer", "answer_json_block", true), exit_code: null }),
  attachStep(5, { fact_id: "f1", model_call: call(4_410, 2.2), command: claimCmd("p1.md", "deployable LLMs using benchmark datasets like Spider and Bird", [["p1", "evaluatesOn", "Spider"]]), output_head: ok("claim-000001"), output_bytes: 42, claims: [ref(a1)] }),
  attachStep(6, { fact_id: "f2", model_call: call(4_380, 2.0), command: claimCmd("p5.md", "math reasoning using GSM8K", [["p5", "evaluatesOn", "GSM8K"]]), output_head: ok("claim-000002"), output_bytes: 42, claims: [ref(a2)] }),
  attachStep(7, { fact_id: "f3", model_call: call(4_560, 2.4), command: claimCmd("p6.md", "and HotpotQA \\(Yang et al", [["p6", "evaluatesOn", "HotpotQA"]]), output_head: ok("claim-000003"), output_bytes: 42, claims: [ref(a3)] }),
  attachStep(8, { fact_id: "f4", model_call: call(5_400, 3.1, "answer"), command: `rg -n -i 'hellaswag' "$CORPUS/p3.md"`, exit_code: 1, output_head: "", output_bytes: 0, coverage: ["no_source_found"] }),
]

const offAnswer: Answer = {
  concept_sha256: Q01_SHA,
  kind: "graph",
  rows: [
    graphRow(1, "p1", "Spider", ["claim-000001"], "attach"),
    graphRow(2, "p5", "GSM8K", ["claim-000002"], "attach"),
    graphRow(3, "p6", "HotpotQA", ["claim-000003"], "attach", "F1"),
    graphRow(4, "p3", "HellaSwag", [], "attach"),
  ],
  notes: "Baseline answer; sources attached afterwards. f4: the attach step answered 'no source found'.",
}

// RUN.live: claim on, still running; the mock stream (handlers.ts) plays steps 4-6 and the answer.
const liveSteps: Step[] = [
  step(1, { model_call: call(8_870, 4.0), command: `rg -l -i 'retrieval-augmented|retrieval augmented' "$CORPUS" | sort | head -40`, output_head: "p1.md\np3.md\np4.md\np6.md\np9.md", output_bytes: 29 }),
  step(2, { model_call: call(9_502, 5.0), command: `rg -n -i 'benchmark|dataset' "$CORPUS/p6.md" | head -20`, output_head: "61:… NQ (Kwiatkowski et al., 2019), and HotpotQA (Yang et al., 2018) datasets for the downstream tasks. …", output_bytes: 3_310 }),
  step(3, { model_call: call(1_210, 2.0, "none", "unparsed"), command: null, exit_code: null, coverage: ["unparsed"] }),
]

// --- knowledge graphs (agent/kg.py output) --------------------------------------------------------

const PRED = {
  evaluatesOn: { text: "evaluatesOn", curie: "ours:evaluatesOn", iri: "urn:thesis-agent:vocab#evaluatesOn", vocabulary: "ours" },
  evaluatesOnText: { text: "evaluates on", curie: "ours:evaluatesOn", iri: "urn:thesis-agent:vocab#evaluatesOn", vocabulary: "ours" },
  authoredBy: { text: "authored by", curie: "dblp:authoredBy", iri: "https://dblp.org/rdf/schema#authoredBy", vocabulary: "dblp" },
  proposes: { text: "proposes", curie: "cskg:proposes", iri: "https://w3id.org/cskg/ontology#proposes", vocabulary: "cskg" },
  title: { text: "title", curie: "dblp:title", iri: "https://dblp.org/rdf/schema#title", vocabulary: "dblp" },
}

function edgeOf(c: Claim, predicate: GraphEdge["predicate"], target: string | null, literal: unknown = null): GraphEdge {
  return {
    id: `edge-${c.claim_id!.slice("claim-".length)}`, claim: c.claim_id!, origin: c.origin, step_id: c.step, agent_id: c.agent_id,
    source: `paper:${String(c.s)}`, predicate, target, literal,
    evidence: { file: c.file!, paper: c.paper_id ?? null, start: c.anchor!.start, end: c.anchor!.end },
  }
}

const paper = (id: string) => ({ id: `paper:${id}`, kind: "paper" as const, label: id, paper: id })
const entity = (slug: string, label: string) => ({ id: `entity:${slug}`, kind: "entity" as const, label })

const NAMESPACES = { cskg: "https://w3id.org/cskg/ontology#", dblp: "https://dblp.org/rdf/schema#", ours: "urn:thesis-agent:vocab#" }

const onGraph: KnowledgeGraph = {
  schema_version: 1, run_id: RUN.on, namespaces: NAMESPACES,
  nodes: [
    entity("bird", "BIRD"), entity("gsm8k", "GSM8K"), entity("hanbing-liu", "Hanbing Liu"), entity("hotpotqa", "HotpotQA"),
    entity("megapairs", "MegaPairs"), entity("spider", "Spider"), paper("p1"), paper("p4"), paper("p5"), paper("p6"),
  ],
  edges: [
    edgeOf(c1, PRED.evaluatesOn, "entity:spider"),
    edgeOf(c2, PRED.evaluatesOn, "entity:bird"),
    edgeOf(c3, PRED.evaluatesOnText, "entity:gsm8k"),
    edgeOf(c4, PRED.authoredBy, "entity:hanbing-liu"),
    edgeOf(c5, PRED.evaluatesOn, "entity:hotpotqa"),
    edgeOf(c6, PRED.proposes, "entity:megapairs"),
    edgeOf(c7, PRED.title, null, "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval"),
  ],
}

const offGraph: KnowledgeGraph = {
  schema_version: 1, run_id: RUN.off, namespaces: NAMESPACES,
  nodes: [entity("gsm8k", "GSM8K"), entity("hotpotqa", "HotpotQA"), entity("spider", "Spider"), paper("p1"), paper("p5"), paper("p6")],
  edges: [edgeOf(a1, PRED.evaluatesOn, "entity:spider"), edgeOf(a2, PRED.evaluatesOn, "entity:gsm8k"), edgeOf(a3, PRED.evaluatesOn, "entity:hotpotqa")],
}

// --- scores (score.json, scoring/run_score.py) ------------------------------------------------------

const prf = (tp: number, fp: number, fn: number) => {
  const precision = tp + fp ? tp / (tp + fp) : null
  const recall = tp + fn ? tp / (tp + fn) : null
  const f1 = precision !== null && recall !== null && precision + recall ? (2 * precision * recall) / (precision + recall) : null
  return { tp, fp, fn, precision, recall, f1 }
}

const JUDGE = { model: "sub-model-1", prompt_sha256: "71c0de5a9b8e7f6d5c4b3a2918f7e6d5c4b3a29180f7e6d5c4b3a2918f7e6d5c", cached: true }

/** score.json detail.support: per fact its label and its claims' verdicts. */
const support = (rowId: string, factId: string, origin: string, label: FactLabel, claims: [string, string, Verdict["label"], string][]): SupportDetail => ({
  row_id: rowId, fact_id: factId, origin, label, first_claim_label: label,
  claims: claims.map(([claim_id, file, l, rationale]) => ({ claim_id, file, label: l, rationale, ...JUDGE })),
})

const k = (row: string) => ({ row, fact: `q01-${row.replace("r", "k")}-f1` })
const fr = (n: number) => ({ row: `r${n}`, fact: `f${n}` })

export const SCORES: Record<string, Score> = {
  [RUN.on]: {
    schema_version: 2, run_id: RUN.on, qid: "q01", condition: "claim_on", seed: 1, exit_status: "submitted", answer_from: "final",
    verify_ok: true, verify_errors: [], key_version: "v1", key_reviewed: true, provisional: false, key_problems: [],
    rows: { ...prf(4, 1, 1), asked: 0, pending: 0 }, rows_by_level: { normalised: prf(4, 1, 1), soft: prf(4, 1, 1) },
    facts: {
      strict: { ...prf(3, 2, 2), vital: 4, vital_tp: 3, vital_recall: 0.75 },
      normalised: { ...prf(4, 1, 1), vital: 4, vital_tp: 3, vital_recall: 0.75 },
      soft: { ...prf(4, 1, 1), vital: 4, vital_tp: 3, vital_recall: 0.75, asked: 1, pending: 0 },
    },
    vital_recall: 0.75,
    judged_precision: { correct: 4, wrong: 0, precision: 1, coverage: 0.8 },
    support: {
      facts: 5, with_claims: 4, supports: 3, partial: 1, no: 0, unsourced: 1, pending: 0, partial_counts_as: "no",
      support_share: 0.6, support_share_partial_no: 0.6, support_share_partial_yes: 0.8, support_share_first_claim: 0.6,
      claims_per_fact: 1, unsourced_share: 0.2, context: "calibrated",
    },
    pending: { support: 0, same_fact: 0, same_row: 0 },
    cost: { steps: 8, model_calls: 8, tokens: 71_420, tokens_without_attach: 71_420, seconds: 412.6, seconds_without_attach: 412.6, wall_seconds: 431.0, claim_steps: 4, claim_step_tokens: 40_109, attach_tokens: 0, attach_seconds: 0 },
    detail: {
      rows: { pairs: [{ run: "r1", key: "r1", level: "strict" }, { run: "r2", key: "r2", level: "strict" }, { run: "r3", key: "r4", level: "normalised" }, { run: "r4", key: "r5", level: "strict" }], missed: ["r6"], extra: ["r5"], duplicates: 0 },
      facts: {
        pairs: [
          { run: fr(1), key: k("r1"), level: "strict", vital: true },
          { run: fr(2), key: k("r2"), level: "strict", vital: true },
          { run: fr(3), key: k("r4"), level: "normalised", vital: false },
          { run: fr(4), key: k("r5"), level: "strict", vital: true },
        ],
        missed: [{ key: k("r6"), spo: { s: "p6", p: "evaluatesOn", o: "NQ" }, vital: true }],
        extra: [{ run: fr(5), same: [], spo: { s: "p3", p: "evaluatesOn", o: "HellaSwag" }, wrong: false }],
        duplicates: 0,
      },
      support: [
        support("r1", "f1", "research", "supports", [["claim-000001", "p1.md", "supports", "The quote names Spider as a benchmark dataset the paper's text-to-SQL models are trained and evaluated with."]]),
        support("r2", "f2", "research", "supports", [["claim-000002", "p1.md", "supports", "Bird (BIRD) is named in the same sentence as a benchmark dataset of the paper."]]),
        support("r3", "f3", "research", "supports", [["claim-000003", "p5.md", "supports", "The quote lists GSM8K as the dataset used for math reasoning in the paper's evaluation."]]),
        support("r4", "f4", "research", "partial", [["claim-000005", "p6.md", "partial", "The quote only cites HotpotQA; the surrounding sentence, not the quote itself, says it is used for the downstream evaluation."]]),
        support("r5", "f5", "research", "unsourced", []),
      ],
    },
    scored_at: "2026-10-12T10:02:13Z",
  },
  [RUN.off]: {
    schema_version: 2, run_id: RUN.off, qid: "q01", condition: "claim_off", seed: 1, exit_status: "submitted", answer_from: "final",
    verify_ok: true, verify_errors: [], key_version: "v1", key_reviewed: true, provisional: false, key_problems: [],
    rows: { ...prf(3, 1, 2), asked: 0, pending: 0 }, rows_by_level: { normalised: prf(3, 1, 2), soft: prf(3, 1, 2) },
    facts: {
      strict: { ...prf(3, 1, 2), vital: 4, vital_tp: 2, vital_recall: 0.5 },
      normalised: { ...prf(3, 1, 2), vital: 4, vital_tp: 2, vital_recall: 0.5 },
      soft: { ...prf(3, 1, 2), vital: 4, vital_tp: 2, vital_recall: 0.5, asked: 0, pending: 0 },
    },
    vital_recall: 0.5,
    judged_precision: { correct: 3, wrong: 0, precision: 1, coverage: 0.75 },
    support: {
      facts: 4, with_claims: 3, supports: 2, partial: 1, no: 0, unsourced: 1, pending: 0, partial_counts_as: "no",
      support_share: 0.5, support_share_partial_no: 0.5, support_share_partial_yes: 0.75, support_share_first_claim: 0.5,
      claims_per_fact: 1, unsourced_share: 0.25, context: "calibrated",
    },
    pending: { support: 0, same_fact: 0, same_row: 0 },
    cost: { steps: 8, model_calls: 8, tokens: 48_900, tokens_without_attach: 30_150, seconds: 365.2, seconds_without_attach: 238.9, wall_seconds: 402.7, claim_steps: 3, claim_step_tokens: 13_350, attach_tokens: 18_750, attach_seconds: 126.3 },
    detail: {
      rows: { pairs: [{ run: "r1", key: "r1", level: "strict" }, { run: "r2", key: "r4", level: "strict" }, { run: "r3", key: "r5", level: "strict" }], missed: ["r2", "r6"], extra: ["r4"], duplicates: 0 },
      facts: {
        pairs: [
          { run: fr(1), key: k("r1"), level: "strict", vital: true },
          { run: fr(2), key: k("r4"), level: "strict", vital: false },
          { run: fr(3), key: k("r5"), level: "strict", vital: true },
        ],
        missed: [
          { key: k("r2"), spo: { s: "p1", p: "evaluatesOn", o: "BIRD" }, vital: true },
          { key: k("r6"), spo: { s: "p6", p: "evaluatesOn", o: "NQ" }, vital: true },
        ],
        extra: [{ run: fr(4), same: [], spo: { s: "p3", p: "evaluatesOn", o: "HellaSwag" }, wrong: false }],
        duplicates: 0,
      },
      support: [
        support("r1", "f1", "attach", "supports", [["claim-000001", "p1.md", "supports", "The quote names Spider as a benchmark dataset of the paper."]]),
        support("r2", "f2", "attach", "supports", [["claim-000002", "p5.md", "supports", "GSM8K is the paper's dataset for math reasoning."]]),
        support("r3", "f3", "attach", "partial", [["claim-000003", "p6.md", "partial", "HotpotQA is cited; that it is an evaluation dataset follows from the surrounding sentence only."]]),
        support("r4", "f4", "attach", "unsourced", []),
      ],
    },
    scored_at: "2026-10-12T10:09:40Z",
  },
}

// --- run summaries and details ----------------------------------------------------------------------

const summary = (s: Partial<RunSummary> & Pick<RunSummary, "run_id" | "qid" | "condition" | "seed" | "created_at">): RunSummary => ({
  batch: s.run_id.includes("~") ? s.run_id.split("~")[0] : null, concept_sha256: null, concept_current: true,
  temperature: 0.7, exit_status: "submitted", answer_from: "final", steps: 0, model_calls: 0, tokens: 0, seconds: 0,
  tokens_without_attach: null, seconds_without_attach: null, rows: 0, facts: 0, claims_accepted: 0, claims_rejected: 0,
  attach: s.condition === "claim_off" ? "done" : "not_applicable", verify: "ok", score: null, live: false, post_processing: false, ...s,
})

export const RUNS: RunSummary[] = [
  summary({
    run_id: RUN.live, qid: "q01", condition: "claim_on", seed: 2, created_at: "2026-10-13T08:02:11Z", exit_status: "running", answer_from: null,
    concept_sha256: Q01_SHA, steps: 3, model_calls: 3, tokens: 19_582, seconds: 11.0, rows: null, facts: null, verify: "unknown", live: true,
  }),
  summary({
    run_id: RUN.on, qid: "q01", condition: "claim_on", seed: 1, created_at: "2026-10-12T09:14:03Z", concept_sha256: Q01_SHA, steps: 8, model_calls: 8,
    tokens: 71_420, seconds: 412.6, tokens_without_attach: 71_420, seconds_without_attach: 412.6, rows: 5, facts: 5, claims_accepted: 7, claims_rejected: 1,
    score: { support_share: 0.6, fact_f1: 0.8, row_f1: 0.8, key_version: "v1", provisional: false },
  }),
  summary({
    run_id: RUN.off, qid: "q01", condition: "claim_off", seed: 1, created_at: "2026-10-12T09:31:47Z", concept_sha256: Q01_SHA, steps: 8, model_calls: 8,
    tokens: 48_900, seconds: 365.2, tokens_without_attach: 30_150, seconds_without_attach: 238.9, rows: 4, facts: 4, claims_accepted: 3, claims_rejected: 0,
    score: { support_share: 0.5, fact_f1: 0.667, row_f1: 0.667, key_version: "v1", provisional: false },
  }),
  summary({
    run_id: RUN.q02on, qid: "q02", condition: "claim_on", seed: 1, created_at: "2026-10-11T21:40:00Z", exit_status: "budget", answer_from: "none",
    steps: 60, model_calls: 62, tokens: 2_004_118, seconds: 5_410.2, claims_accepted: 2, claims_rejected: 1,
    score: { support_share: null, fact_f1: 0, row_f1: 0, key_version: "v1-draft", provisional: true },
  }),
  summary({
    run_id: RUN.q02off, qid: "q02", condition: "claim_off", seed: 1, created_at: "2026-10-11T23:12:00Z", exit_status: "budget", answer_from: "none",
    steps: 60, model_calls: 62, tokens: 2_011_377, seconds: 5_233.7, attach: "done",
    score: { support_share: null, fact_f1: 0, row_f1: 0, key_version: "v1-draft", provisional: true },
  }),
  summary({
    run_id: RUN.q07, qid: "q07", condition: "claim_on", seed: 1, created_at: "2026-10-12T14:05:00Z", exit_status: "context_full", answer_from: "none",
    concept_current: null, steps: 41, model_calls: 44, tokens: 1_310_902, seconds: 3_901.5, claims_accepted: 5, claims_rejected: 3, verify: "failed",
  }),
]

const EMPTY_STEPS: Step[] = [
  step(1, { model_call: call(8_701, 4.2), command: `rg -l -i 'jailbreak|red[- ]teaming|safety' "$CORPUS" | wc -l`, output_head: "61", output_bytes: 3 }),
  step(2, { model_call: call(9_920, 5.8), command: `rg -n -i 'jailbreak' "$CORPUS" | head -40`, output_head: "p40.md:12:… a jailbreak attack that …", output_bytes: 8_192 }),
  step(60, { phase: "conclude", model_call: call(61_022, 41.2, "none", "unparsed"), coverage: ["unparsed", "no_final_answer"] }),
]

function detail(s: RunSummary, concept: ConceptBrief, answer: Answer | null): RunDetail {
  const failed = s.verify === "failed"
  return {
    summary: s,
    config: configFor(s.run_id, s.condition, s.seed ?? 1, s.created_at ?? ""),
    concept,
    answer,
    verify: s.verify === "unknown" ? null : {
      ok: !failed,
      errors: failed ? ["events.jsonl: chain broken at record 188 (hash mismatch)"] : [],
      stats: {
        steps: s.steps, model_calls: s.model_calls, claims_accepted: s.claims_accepted, claims_rejected: s.claims_rejected, tokens: s.tokens, seconds: s.seconds,
        ...(s.run_id === RUN.off ? { attach: { steps: 4, tokens: 18_750, claims_accepted: 3 }, without_attach: { steps: 4, tokens: 30_150 } } : {}),
      },
    },
  }
}

export function initialRunDetails(): Record<string, RunDetail> {
  const byId = Object.fromEntries(RUNS.map((r) => [r.run_id, structuredClone(r)]))
  const emptyAnswer = (kind: Answer["kind"], notes: string): Answer => ({ concept_sha256: "0".repeat(64), kind, rows: [], notes })
  return {
    [RUN.on]: detail(byId[RUN.on], Q01_CONCEPT, onAnswer),
    [RUN.off]: detail(byId[RUN.off], Q01_CONCEPT, offAnswer),
    [RUN.live]: detail(byId[RUN.live], Q01_CONCEPT, null),
    [RUN.q02on]: detail(byId[RUN.q02on], BRIEFS.q02[0], emptyAnswer("table", "exit status budget")),
    [RUN.q02off]: detail(byId[RUN.q02off], BRIEFS.q02[0], emptyAnswer("table", "exit status budget")),
    [RUN.q07]: detail(byId[RUN.q07], BRIEFS.q07[0], emptyAnswer("table", "exit status context_full")),
  }
}

export const STEPS: Record<string, Step[]> = {
  [RUN.on]: onSteps, [RUN.off]: offSteps, [RUN.live]: liveSteps,
  [RUN.q02on]: EMPTY_STEPS, [RUN.q02off]: EMPTY_STEPS, [RUN.q07]: EMPTY_STEPS,
}
export const CLAIMS: Record<string, Claim[]> = { [RUN.on]: onClaims, [RUN.off]: offClaims, [RUN.live]: [] }
export const GRAPHS: Record<string, KnowledgeGraph> = {
  [RUN.on]: onGraph, [RUN.off]: offGraph, [RUN.live]: { schema_version: 1, run_id: RUN.live, nodes: [], edges: [] },
}

/** The passage the backend resolves a claim's anchor to (WALK_CONTEXT around it). */
export const passageOf = (claim: Pick<Claim, "paper_id" | "anchor">) =>
  Object.values(PASSAGES).find((p) => p.paper_id === claim.paper_id && claim.anchor && anchorOf(p).start === claim.anchor.start)

/**
 * The claim walk of one fact, assembled the way the backend does (webapp/runs.py walk): claims ->
 * step -> passage, with the verdicts score.json counted (webapp/judge.py add_scored). `judge`: the
 * live judge answers for quotes the score has no verdict for.
 */
export function walkFor(runId: string, answer: Answer | null, factId: string, judge = false): FactWalk | null {
  const row = answer?.rows.find((r) => r.facts.some((f) => f.id === factId))
  const fact = row?.facts.find((f) => f.id === factId)
  if (!row || !fact) return null
  const claims = CLAIMS[runId] ?? []
  const steps = STEPS[runId] ?? []
  const scored = SCORES[runId]?.detail?.support?.find((s) => s.fact_id === factId && s.row_id === row.id)
  const items = fact.claims.map((id) => {
    const claim = claims.find((c) => c.claim_id === id && c.status === "accepted") ?? null
    const verdict = scored?.claims?.find((c) => c.claim_id === id)
    const support: Verdict | null = verdict?.label
      ? { label: verdict.label, rationale: verdict.rationale, model: verdict.model, prompt_sha256: JUDGE.prompt_sha256, cached: true, source: "score" }
      : judge && claim
        ? { label: "supports", rationale: "(mock judge) The quote states the fact.", model: "sub-model-2", prompt_sha256: JUDGE.prompt_sha256, cached: false, source: "judge" }
        : null
    return {
      claim_id: id, claim,
      step: claim ? steps.find((s) => s.step === claim.step && s.agent_id === claim.agent_id) ?? null : null,
      passage: claim ? passageOf(claim) ?? null : null,
      anchor_status: claim ? "ok" : "missing",
      support,
    }
  })
  const verdicts = items.filter((i) => i.claim).map((i) => i.support)
  const rank = { supports: 2, partial: 1, no: 0 }
  const best = verdicts.filter((v): v is Verdict => !!v).sort((a, b) => rank[b.label] - rank[a.label])[0] ?? null
  const label: FactLabel | null = scored ? scored.label
    : verdicts.length === 0 ? "unsourced"
      : best && (best.label === "supports" || verdicts.every(Boolean)) ? best.label
        : judge ? "pending" : null
  return { run_id: runId, fact, row_id: row.id, row, claims: items, support: best, label }
}

// --- the live run's remaining records (played by the mock stream) ---------------------------------------

const rec = (r: Omit<EventRecord, "task_id" | "agent_id" | "status"> & Partial<EventRecord>): EventRecord => ({
  task_id: nextTask(), agent_id: "main", status: "finished", ...r,
})
const usage = (total: number) => ({ prompt_tokens: total - 120, completion_tokens: 120, total_tokens: total })

export const LIVE_RECORDS: EventRecord[] = [
  rec({ subtype: "ai_model_invocation", step_id: 4, generated: { usage: usage(10_090), parse: "strict", reply: "command", finish_reason: "stop" }, custom_metadata: { phase: "research", seconds: 5.6, final_answer: false, origin: "research" } }),
  rec({ subtype: "claim", step_id: 4, status: "accepted", generated: { claim_id: "claim-000001" }, used: { anchor: { file: "p6.md", ...anchorOf(PASSAGES.hotpotqa), exact: quoteOf(PASSAGES.hotpotqa) } }, custom_metadata: { s: "p6", p: "evaluatesOn", o: "HotpotQA", origin: "research" } }),
  rec({ subtype: "agent_tool", step_id: 4, used: { command: claimCmd("p6.md", "and HotpotQA \\(Yang et al", [["p6", "evaluatesOn", "HotpotQA"]]) }, generated: { exit_code: 0, timed_out: false, output_bytes: 42 }, custom_metadata: { claim_step: true, claims: 1, origin: "research", phase: "research" } }),
  rec({ subtype: "ai_model_invocation", step_id: 5, generated: { usage: usage(10_802), parse: "strict", reply: "command", finish_reason: "stop" }, custom_metadata: { phase: "research", seconds: 6.1, final_answer: false, origin: "research" } }),
  rec({ subtype: "claim", step_id: 5, status: "rejected", generated: {}, used: { file: "p9.md", quote: "evaluated on Natural Questions" }, custom_metadata: { s: "p9", p: "evaluatesOn", o: "Natural Questions", reason: "not_found", origin: "research" } }),
  rec({ subtype: "agent_tool", step_id: 5, used: { command: `jq -n '{s: "p9", p: "evaluatesOn", o: "Natural Questions", file: "p9.md", quote: "evaluated on Natural Questions"}' | claim` }, generated: { exit_code: 1, timed_out: false, output_bytes: 38 }, custom_metadata: { claim_step: false, claims: 0, repeat: 1, origin: "research", phase: "research" } }),
  rec({ subtype: "ai_model_invocation", step_id: 6, generated: { usage: usage(1_840), parse: "answer_json_block", reply: "answer", finish_reason: "stop" }, custom_metadata: { phase: "conclude", seconds: 11.9, final_answer: true, origin: "research" } }),
]

export const LIVE_ANSWER: Answer = {
  concept_sha256: Q01_SHA,
  kind: "graph",
  rows: [graphRow(1, "p6", "HotpotQA", ["claim-000001"], "research", "F1")],
  notes: "Stopped early in the mock: one dataset found and claimed.",
}

// --- gold (GET /api/gold: doc.json coverage and counts, the review's report.json) ----------------------

export const GOLD: GoldEntry[] = [
  {
    qid: "q01", status: "reviewed", stage: "done", key_version: "v1", rows: 5, facts: 5,
    coverage: { papers: 336, relevant: 41, not_relevant: 291, no_text: 3, error: 1, papers_in_corpus: 336, partial: false },
    counts: {
      chunks: 4_812, chunks_relevant: 233, chunks_error: 0, extraction_errors: 0, candidates: 212, anchored: 198,
      rejected: { not_found: 11, ambiguous: 3 }, rows: 58, papers_with_candidates: 39,
      model_calls: { made: 5_120, cached: 0, failed: 0, total: 5_120 },
      cost: { invocations: 2, seconds: 9_812.4, calls_made: 5_120, input_tokens: 21_400_118, output_tokens: 611_002 },
    },
    report: {
      qid: "q01", generated_at: "2026-10-12T18:20:00Z",
      review: { records: 155, decided: 155, kept: 131, unreviewed: 0, disagreements: 0, stale: 0 },
      kappa: {
        reviewers: ["aditya", "reviewer-2"], items: 31,
        label: { items: 31, kappa: 0.78, raw_agreement: 0.9 }, keep: { items: 31, kappa: 0.81, raw_agreement: 0.94 },
        vital: { items: 24, kappa: 0.66, raw_agreement: 0.83 }, bar: 0.61, keep_kappa_meets_bar: true, independent: true,
      },
      triage: { estimated_missed: 2.4, estimated_missed_95: [0.6, 8.9], estimated_recall: 0.98, estimated_recall_95: [0.94, 0.99], sample_reviewed: 24, sampled: 24 },
      screening: { not_relevant: 291, checked: 30, found_relevant: 1, false_negative_rate: 0.033, false_negative_rate_95: [0.006, 0.167] },
    },
  },
  {
    qid: "q02", status: "draft", stage: "done", key_version: "v1-draft", rows: 22, facts: 74,
    coverage: { papers: 336, relevant: 27, not_relevant: 305, no_text: 3, error: 1, papers_in_corpus: 336, partial: false },
    counts: { candidates: 140, anchored: 131, rows: 22, model_calls: { made: 4_903, total: 4_903 } },
    report: { qid: "q02", review: { records: 98, decided: 37, kept: 30, unreviewed: 61, disagreements: 2, stale: 0 }, kappa: null, triage: null, screening: null },
  },
  {
    qid: "q04", status: "building", stage: "building", key_version: null, rows: 12, facts: null,
    coverage: { papers: 110, relevant: 12, not_relevant: 98, no_text: 0, error: 0, papers_in_corpus: 336, partial: true },
    counts: { candidates: 33, anchored: 30, rows: 12 }, report: null,
  },
  ...QUESTIONS.filter((q) => !["q01", "q02", "q04"].includes(q.id)).map((q): GoldEntry => ({ qid: q.id, status: "none", stage: null, coverage: null, counts: null, key_version: null, report: null, rows: null, facts: null })),
]

const keyRow = (id: string, s: string, o: string, metric: string, p: Passage | null, vital: boolean, cand: string, quoteText?: string): KeyRow => ({
  id, source: s, source_type: "Paper", predicate: "evaluatesOn", target: o, target_type: "Dataset", attributes: { metric },
  facts: [{ id: `q01-${id.replace("r", "k")}-f1`, s, p: "evaluatesOn", o, claims: [], origin: "research", paper_id: s, quote: quoteText ?? (p ? quoteOf(p) : ""), vital, candidate_id: cand }],
})

export const GOLD_KEYS: Record<string, AnswerKey> = {
  q01: {
    qid: "q01", concept_sha256: Q01_SHA, kind: "graph", version: "v1", reviewed: true,
    rows: [
      keyRow("r1", "p1", "Spider", "execution accuracy", PASSAGES.spider, true, "q01-c000014"),
      keyRow("r2", "p1", "BIRD", "execution accuracy", PASSAGES.spider, true, "q01-c000015"),
      keyRow("r4", "p5", "GSM8K", "accuracy", PASSAGES.gsm8k, false, "q01-c000052"),
      keyRow("r5", "p6", "HotpotQA", "F1", PASSAGES.hotpotqa, true, "q01-c000071"),
      keyRow("r6", "p6", "NQ", "F1", null, true, "q01-c000070", "NQ (Kwiatkowski et al., 2019)"),
    ],
    notes: "Reviewed in Argilla (31 records double-annotated).",
  },
}

// --- results ($RUNS/report/report.json, scoring/report.py) -------------------------------------------

const iv = (mean: number, low: number, high: number, n = 12) => ({ n, mean, low, high, method: "BCa", runs: n * 3, runs_without_value: 0 })
const outcome = (label: string, on: [number, number, number], off: [number, number, number], diff: [number, number, number]) => ({
  label, claim_on: iv(...on), claim_off: iv(...off), difference: { n: 12, mean: diff[0], low: diff[1], high: diff[2], method: "BCa" },
})

type PQ = [support: number, f1: number, row: number, unsourced: number, tokens: number, tokensWithout: number]
const QR: [string, PQ, PQ][] = [
  ["q01", [0.74, 0.61, 0.55, 0.08, 1_120_000, 1_120_000], [0.55, 0.6, 0.52, 0.21, 1_260_000, 990_000]],
  ["q02", [0.69, 0.48, 0.41, 0.15, 1_530_000, 1_530_000], [0.49, 0.5, 0.43, 0.3, 1_610_000, 1_290_000]],
  ["q03", [0.77, 0.58, 0.5, 0.06, 1_210_000, 1_210_000], [0.58, 0.55, 0.47, 0.22, 1_320_000, 1_050_000]],
  ["q04", [0.66, 0.52, 0.44, 0.14, 1_350_000, 1_350_000], [0.5, 0.54, 0.46, 0.29, 1_480_000, 1_170_000]],
  ["q05", [0.72, 0.6, 0.53, 0.1, 1_190_000, 1_190_000], [0.57, 0.58, 0.5, 0.24, 1_300_000, 1_010_000]],
  ["q06", [0.7, 0.55, 0.49, 0.11, 1_420_000, 1_420_000], [0.53, 0.52, 0.47, 0.25, 1_520_000, 1_210_000]],
  ["q07", [0.68, 0.49, 0.42, 0.16, 1_310_000, 1_310_000], [0.46, 0.5, 0.4, 0.33, 1_430_000, 1_120_000]],
  ["q08", [0.75, 0.57, 0.48, 0.09, 1_090_000, 1_090_000], [0.54, 0.55, 0.45, 0.26, 1_210_000, 960_000]],
  ["q09", [0.71, 0.53, 0.46, 0.12, 1_270_000, 1_270_000], [0.51, 0.51, 0.44, 0.28, 1_380_000, 1_100_000]],
  ["q10", [0.73, 0.56, 0.47, 0.1, 1_240_000, 1_240_000], [0.53, 0.53, 0.44, 0.27, 1_350_000, 1_070_000]],
  ["q11", [0.64, 0.47, 0.4, 0.18, 1_400_000, 1_400_000], [0.48, 0.49, 0.42, 0.31, 1_520_000, 1_220_000]],
  ["q12", [0.72, 0.55, 0.48, 0.11, 1_280_000, 1_280_000], [0.5, 0.54, 0.46, 0.28, 1_400_000, 1_120_000]],
]

const perQuestion = (qid: string, condition: string, v: PQ): QuestionResult => ({
  qid, condition, runs: 3, answered: 3, primary_runs: 3, pending_runs: 0,
  support_share: v[0], fact_f1: v[1], row_f1: v[2], unsourced_share: v[3], tokens: v[4], tokens_without_attach: v[5],
})

const test = (outcomeName: string, mean: number, low: number, high: number, p: number, statistic: number) => ({
  outcome: outcomeName, test: "wilcoxon signed-rank", alternative: "two-sided", zero_method: "wilcox", alpha: 0.05, n_pairs: 12, n_nonzero: 12,
  computed: true, reason: null, statistic, p_value: p, significant: p < 0.05, t_plus: 78, t_minus: 0, rank_biserial: 1,
  mean_difference: mean, ci_low: low, ci_high: high, ci_method: "BCa", questions: QR.map(([q]) => q), excluded_questions: [],
})

export const RESULTS: ResultsReport = {
  schema_version: 2,
  generated_at: "2026-10-13T06:00:00Z",
  runs_root: "/scratch/thesis/runs/m4-72",
  provisional: false, provisional_runs: 0, complete: true,
  completeness: { pending_support_runs: [], pending_soft_runs: [], unverified_runs: [], verify_failed_runs: [] },
  settings: { interval: "BCa bootstrap over questions", confidence: 0.95, resamples: 2000, alpha: 0.05, min_pairs: 6 },
  runs: { scored: 72, by_condition: { claim_on: 36, claim_off: 36 }, by_exit_status: { claim_on: { submitted: 33, budget: 3 }, claim_off: { submitted: 34, budget: 2 } } },
  coverage: {
    claim_on: { scored: 36, answered: 33, answered_share: 33 / 36, not_scored: 0 },
    claim_off: { scored: 36, answered: 34, answered_share: 34 / 36, not_scored: 0 },
  },
  questions: QR.map(([q]) => q),
  per_question: QR.flatMap(([qid, on, off]) => [perQuestion(qid, "claim_off", off), perQuestion(qid, "claim_on", on)]),
  paired: QR.map(([qid, on, off]) => ({
    qid,
    support_share: { claim_on: on[0], claim_off: off[0], difference: on[0] - off[0] },
    fact_f1: { claim_on: on[1], claim_off: off[1], difference: on[1] - off[1] },
  })),
  summary: {
    support_share: outcome("Support share (judge)", [0.71, 0.63, 0.78], [0.52, 0.44, 0.6], [0.19, 0.16, 0.21]),
    fact_precision: outcome("Fact precision (soft)", [0.64, 0.55, 0.72], [0.6, 0.51, 0.69], [0.04, 0.0, 0.08]),
    fact_recall: outcome("Fact recall (soft)", [0.48, 0.39, 0.57], [0.5, 0.41, 0.58], [-0.02, -0.05, 0.01]),
    fact_f1: outcome("Fact F1 (soft)", [0.54, 0.46, 0.62], [0.53, 0.45, 0.61], [0.01, -0.01, 0.03]),
    row_f1: outcome("Row F1 (soft)", [0.47, 0.38, 0.55], [0.45, 0.37, 0.54], [0.02, -0.01, 0.04]),
    vital_recall: outcome("Vital recall (soft)", [0.58, 0.47, 0.68], [0.6, 0.49, 0.7], [-0.02, -0.06, 0.02]),
    unsourced_share: outcome("Unsourced share", [0.12, 0.07, 0.18], [0.27, 0.19, 0.35], [-0.15, -0.17, -0.13]),
    tokens: outcome("Tokens", [1_284_000, 1_102_000, 1_466_000], [1_398_000, 1_201_000, 1_590_000], [-114_000, -128_000, -101_000]),
    tokens_without_attach: outcome("Tokens without attach", [1_284_000, 1_102_000, 1_466_000], [1_102_000, 948_000, 1_260_000], [182_000, 150_000, 214_000]),
    seconds: outcome("Time (s, active)", [3_410, 2_960, 3_870], [3_720, 3_240, 4_190], [-310, -390, -240]),
    seconds_without_attach: outcome("Time without attach (s)", [3_410, 2_960, 3_870], [2_890, 2_500, 3_300], [520, 430, 610]),
  },
  primary: {
    ...test("support_share", 0.19, 0.16, 0.21, 0.00049, 0),
    sensitivity_empty_as_zero: { ...test("support_share_empty_as_zero", 0.18, 0.14, 0.21, 0.00049, 0), label: "answers without facts count as support share 0" },
    sensitivity_other_mapping: { ...test("support_share_other_mapping", 0.12, 0.08, 0.15, 0.0015, 2), label: "`partial` under the other mapping than the calibrated one" },
    sensitivity_first_claim: { ...test("support_share_first_claim", 0.19, 0.16, 0.21, 0.00049, 0), label: "each fact judged by its first cited claim only" },
  },
  secondary: ["fact_precision", "fact_recall", "fact_f1", "row_f1", "vital_recall", "unsourced_share", "tokens", "tokens_without_attach", "seconds", "seconds_without_attach"],
}

// --- jobs -----------------------------------------------------------------------------------------------

const jobStep = (name: string, command: string, state: JobStep["state"], exit_code: number | null = state === "done" ? 0 : null, required = true): JobStep => ({
  name, argv: command.split(" "), command, required, needs: [], state, exit_code, started_at: null, ended_at: null,
})

const runSteps = (name: string, condition: string, states: JobStep["state"][]): JobStep[] => {
  const dir = `/scratch/thesis/runs/web/${name}`
  const names = ["run", ...(condition === "claim_off" ? ["attach"] : []), "verify", "pairs", "graph", "export-prov", "score"]
  const commands: Record<string, string> = {
    run: `python -m agent.cli run --concept concepts/q01/concept.json --run-id ${name} --condition ${condition} --seed 1 --temperature 0.7`,
    attach: `python -m agent.cli attach ${dir} --corpus /scratch/thesis/corpus-md`,
    verify: `python -m agent.cli verify ${dir} --corpus /scratch/thesis/corpus-md`,
    pairs: `python -m agent.cli pairs ${dir}`,
    graph: `python -m agent.cli graph ${dir}`,
    "export-prov": `python -m agent.cli export-prov ${dir}`,
    score: `python -m scoring.cli run ${dir} --key gold-data/q01/key.json`,
  }
  return names.map((n, i) => jobStep(n, commands[n], states[i] ?? "pending", undefined, !["verify", "pairs", "score"].includes(n)))
}

export const JOBS: Job[] = [
  {
    id: "job-0007", kind: "run", args: { qid: "q01", concept_path: null, condition: "claim_on", seed: 2, temperature: 0.7, steps: null, tokens: null, sandbox: "landlock", attach: true, force: false },
    state: "running", created_at: "2026-10-13T08:02:09Z", started_at: "2026-10-13T08:02:09Z", ended_at: null, run_id: RUN.live, qid: "q01", exit_code: null,
    error: null, warnings: [], steps: runSteps(RUN.live.split("~")[1], "claim_on", ["running"]),
  },
  {
    id: "job-0006", kind: "run", args: { qid: "q01", condition: "claim_off", seed: 1, temperature: 0.7, attach: true },
    state: "done", created_at: "2026-10-12T09:31:45Z", started_at: "2026-10-12T09:31:45Z", ended_at: "2026-10-12T09:38:12Z", run_id: RUN.off, qid: "q01", exit_code: 0,
    error: null, warnings: [], steps: runSteps("q01-claim_off-r1-a1", "claim_off", ["done", "done", "done", "done", "done", "done", "done"]),
  },
  {
    id: "job-0005", kind: "gold", args: { qid: "q02" },
    state: "done", created_at: "2026-10-12T09:00:00Z", started_at: "2026-10-12T09:00:01Z", ended_at: "2026-10-12T11:42:10Z", qid: "q02", exit_code: 0,
    error: null, warnings: [], steps: [jobStep("gold build", "python -m gold.cli build q02", "done"), jobStep("gold triage", "python -m gold.cli triage q02", "done"), jobStep("gold pool", "python -m gold.cli pool q02", "done"), jobStep("gold draft", "python -m gold.cli draft q02", "done")],
  },
  {
    id: "job-0004", kind: "concepts", args: { qid: "q07", temperature: 0.7, seed: 7 },
    state: "done", created_at: "2026-10-12T08:50:00Z", started_at: "2026-10-12T08:50:00Z", ended_at: "2026-10-12T08:50:41Z", qid: "q07", exit_code: 0,
    error: null, warnings: [], steps: [jobStep("propose", "python -m agent.cli concepts propose q07 --temperature 0.7 --seed 7", "done")],
  },
  {
    id: "job-0003", kind: "run", args: { qid: "q07", condition: "claim_on", seed: 1, temperature: 0.7 },
    state: "failed", created_at: "2026-10-12T14:04:58Z", started_at: "2026-10-12T14:04:58Z", ended_at: "2026-10-12T15:10:03Z", run_id: RUN.q07, qid: "q07", exit_code: 3,
    error: "run failed (exit 3)", warnings: ["verify failed (exit 1); see the log"],
    steps: runSteps(RUN.q07.split("~")[1], "claim_on", ["failed", "failed", "skipped", "skipped", "skipped", "skipped"]),
  },
]

export const JOB_LOGS: Record<string, string[]> = {
  "job-0007": [
    "$ python -m agent.cli run --concept concepts/q01/concept.json --condition claim_on --seed 2 --temperature 0.7",
    "broker: start records=0 head=0000000000000000",
    "step 1: model call 8,870 tokens (4.0 s), command exit 0",
    "step 2: model call 9,502 tokens (5.0 s), command exit 0",
    "step 3: model call 1,210 tokens (2.0 s): no bash block, coverage unparsed",
  ],
  "job-0006": [
    "$ python -m agent.cli run --concept concepts/q01/concept.json --condition claim_off --seed 1 --temperature 0.7",
    "broker: start records=0 head=0000000000000000",
    "step 4: final answer, 4 rows",
    "$ python -m agent.cli attach runs/web/q01-claim_off-r1-a1",
    "attach f1: claim-000001", "attach f2: claim-000002", "attach f3: claim-000003", "attach f4: no source found",
    "$ python -m agent.cli verify runs/web/q01-claim_off-r1-a1", "verify: ok (31 records, 3 claims)",
    "$ python -m scoring.cli run runs/web/q01-claim_off-r1-a1", "score: support share 0.50, fact F1 0.67",
    "exit 0",
  ],
  "job-0003": [
    "$ python -m agent.cli run --concept concepts/q07/concept.json --condition claim_on --seed 1",
    "step 41: HTTP 400 ContextWindowExceededError (context 65,536, prompt 66,102)",
    "step 41: third context-full reply, run ends: exit status context_full",
    "$ python -m agent.cli verify runs/web/q07-claim_on-s1", "verify: FAILED events.jsonl: chain broken at record 188 (hash mismatch)",
    "exit 3",
  ],
}
