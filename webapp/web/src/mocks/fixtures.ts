/**
 * Fixture data for the MSW handlers (dev with VITE_MOCK=1, and the tests).
 *
 * Modelled on the repo's own test runs (agent/tests/runs.py: research_run, baseline_run) and the
 * D1 fixture papers (tests/D1/docling, numbered p1..p10 as agent/tests/conftest.py write_corpus
 * does): every quote and passage below is real text from those papers at its real offsets.
 *
 * - q01 has a picked graph concept, a reviewed key and three runs: claim_on (q01-on-s1, done,
 *   with a sub-agent, a literal edge and a rejected claim), claim_off (q01-off-s1, done, with
 *   the attach step) and q01-on-s2, still running (the mock stream finishes it).
 * - q02 runs ended at the budget with no answer (as the M1-real runs did); q07 has three
 *   proposed briefs and no pick; most other questions have nothing yet.
 */
import type {
  Answer,
  AnswerKey,
  AppConfig,
  Claim,
  ConceptBrief,
  ConceptPick,
  EventRecord,
  FactWalk,
  GoldSummary,
  GraphEdge,
  Job,
  KnowledgeGraph,
  ModelCallStats,
  Passage,
  QuestionSummary,
  ResultsReport,
  RunConfig,
  RunDetail,
  RunSummary,
  Score,
  Step,
  Verdict,
} from "@/api/types"

// --- passages (real text of the D1 papers) -------------------------------------------------------

const P1_TITLE = "Uncovering the Impact of Chain-of-Thought Reasoning for Direct Preference Optimization: Lessons from Text-to-SQL"

export const PASSAGES: Record<string, Passage> = {
  spider: {
    paper_id: "p1",
    title: P1_TITLE,
    offset: 2770,
    text:
      "nhanced dataset (Orange). This shows that CoT reasoning is crucial for unlocking DPO's potential, ensuring its effectiveness and stability.\n\n<!-- image -->\n\nand supervised fine-tuning (SFT) methods (Pourreza and Rafiei, 2024b; Li et al., 2023, 2024a). Prompting-based methods often rely on powerful closed-source LLMs, making them costly and slow, and raising data privacy concerns. In contrast, SFT trains open-source, deployable LLMs using benchmark datasets like Spider and Bird. However, SFT performance is often limited by the scarcity of highquality training data, which is expensive and timeconsuming to create.\n\nRecent studies in complex reasoning tasks, such as math word problems (Xu et al., 2024) and code generation (Zhang et al., 2024), have demonstrated that preference optimization algorithms ( e.g. , DPO (Rafailov et al., 2024b), KTO (Ethayarajh et al., 2024), SimPO (Meng et al., 202",
    highlight: { start: 3190, end: 3251 },
  },
  author: {
    paper_id: "p1",
    title: P1_TITLE,
    offset: 0,
    text:
      "## Uncovering the Impact of Chain-of-Thought Reasoning for Direct Preference Optimization: Lessons from Text-to-SQL\n\nHanbing Liu 1 * , Haoyang Li 2,3 * , Xiaokang Zhang 2,3 , Ruotong Chen 2 , Haiyong Xu 5 , Tian Tian 5 , Qi Qi 1 , Jing Zhang 2,4 †\n\n2 School of Information, Renmin University of China, Beijing, China, 3 Key Laboratory of Data Engineering and Knowledge Engineering, Beijing, China, 4 Engineering Research Center of Database and Business Intelligence, Beijing, China, 5 China Mobile Information Technology Center\n\n1 Gaoling School of Artificial Intel",
    highlight: { start: 117, end: 145 },
  },
  gsm8k: {
    paper_id: "p5",
    title: "BIG5-CHAT: Shaping LLM Personalities Through Training on Human-Grounded Data",
    offset: 6124,
    text:
      " come at the cost of diminished cognitive performance. This aligns closely with our motivation by highlighting potential risks to authenticity and effectiveness in applications such as mental health platforms or conversational agents. To explore this, we evaluate our aligned models not only with traditional personality tests but also across five reasoning domains: social reasoning using SocialIQA (Sap et al., 2019), math reasoning using GSM8K (Cobbe et al., 2021) and MathQA (Amini et al., 2019), hallucination detection using TruthfulQA (Lin et al., 2021), commonsense reasoning using CommonsenseQA (Talmor et al., 2019) and PIQA (Bisk et al., 2020), and general reasoning using MMLU (Hendrycks et al., 2020) and GPQA (Rein et al., 2023). Our experiments show that models trained with higher levels of conscientiousness and agreeableness consistently outperform",
    highlight: { start: 6544, end: 6570 },
  },
  hotpotqa: {
    paper_id: "p6",
    title: "How Do Large Vision-Language Models See Text in Image? Unveiling the Distinctive Role of OCR Heads",
    offset: 19282,
    text:
      "vated.\"\n\n## 5 Unveiling the Functional Roles of OCR Heads in Downstream Applications\n\nTo compare the impact of OCR heads and retrieval heads on downstream tasks, we conduct three complementary analyses: CoT prompting, attention head masking, and sink token redistribution. We also use the OCR-VQA (Mishra et al., 2019), Multi-Page DocVQA (Tito et al., 2023), DocVQA (Mathew et al., 2021), NQ (Kwiatkowski et al., 2019), and HotpotQA (Yang et al., 2018) datasets for the downstream tasks. Furthermore, the evaluation metric for all the datasets in the downstream tasks is the F1 score.\n\nTable 2: The average scores of the top 10 OCR and Retrieval heads when CoT prompting is applied in the OCR-VQA task.\n\n| Qwen2-VL-7B    | Method              |   Score |\n|----------------|---------------------|---------|\n| Top10          | Avg OCR Score       |  0.4004 |\n| OCR H",
    highlight: { start: 19702, end: 19726 },
  },
  megapairs: {
    paper_id: "p4",
    title: "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval",
    offset: 0,
    text:
      "## MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval\n\nJunjie Zhou 1 , 2 * , Yongping Xiong 1 ∗ , Zheng Liu 2 , 5 † , Ze Liu 3 , 2 , Shitao Xiao 2 , Yueze Wang 2 , Bo Zhao 4 , Chen Jason Zhang 5 , Defu Lian 3 †\n\nBeijing University of Posts and Telecommunications\n\n1 State Key Laboratory of Networking and Switching Technology,\n\n2 Beijing Academy of Artificial Intelligence\n\n4 Shanghai Jiao Tong University, 5 The Hong Kong Polytechnic University {junjiebupt, zhengliu1026}@",
    highlight: { start: 3, end: 71 },
  },
}

/** The exact quote of a passage (what the claim's anchor covers). */
export const quoteOf = (p: Passage) => p.text.slice(p.highlight.start - p.offset, p.highlight.end - p.offset)

// --- config and questions ------------------------------------------------------------------------

export const config: AppConfig = {
  corpus: "/scratch/thesis/corpus-md",
  runs_root: "/scratch/thesis/runs",
  gold_root: "/scratch/thesis/gold-data",
  concepts_root: "/scratch/thesis/concepts",
  llm_base_url: "http://127.0.0.1:4000/v1",
  llm_key_set: true,
  argilla_url: "http://127.0.0.1:6900",
}

const Q = (id: string, category: QuestionSummary["category"], question: string, source: string): QuestionSummary => ({
  id, category, question, source,
  concept: { status: "none", title: null, picked_by: null },
  gold: { status: "none", rows: null, facts: null },
  runs: { claim_on: 0, claim_off: 0 },
})

export const QUESTIONS: QuestionSummary[] = [
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
  q01: { choice: 2, picked_by: "provisional-first", reason: "Graph shape keeps the metric per paper and dataset.", title: Q01_CONCEPT.title, concept_sha256: "c9ee5264652bee36c072408974aa3b46a0116f27372671768fed3a38b2e32284" },
  q02: { choice: 1, picked_by: "user", reason: "Only one brief; scope matches the question.", title: "Attack and risk types evaluated by safety papers" },
}

// --- runs ------------------------------------------------------------------------------------------

const call = (tokens: number, seconds: number, reply = "command", parse = "strict"): ModelCallStats => ({
  tokens, seconds, parse, reply, finish_reason: "stop",
})

const step = (n: number, s: Partial<Step>): Step => ({
  step: n, phase: "research", model_call: null, command: null, exit_code: 0, timed_out: false, output_head: null,
  output_bytes: null, claims: [], coverage: [], agent_id: "main", origin: "research", ...s,
})

const claimCmd = (file: string, pattern: string, triples: [string, string, string][]) =>
  `q=$(rg -o -N -m1 '${pattern}' "$CORPUS/${file}")\n` +
  triples.map(([s, p, o]) => `jq -n --arg q "$q" '{s: "${s}", p: "${p}", o: "${o}", file: "${file}", quote: $q}' | claim`).join("\n")

const ok = (...ids: string[]) => ids.map((id) => `{"ok": true, "claim_id": "${id}"}`).join("\n")

function accepted(id: string, s: string, p: string, o: string, passage: Passage, at: number, extra: Partial<Claim> = {}): Claim {
  return {
    claim_id: id, status: "accepted", reason: null, s, p, o, file: `${passage.paper_id}.md`, paper_id: passage.paper_id,
    quote: quoteOf(passage), step: at, agent_id: "main", origin: "research", anchor: passage.highlight, ...extra,
  }
}

const ref = (c: Claim) => ({ claim_id: c.claim_id, status: c.status, reason: c.reason, s: c.s, p: c.p, o: c.o })

const configFor = (runId: string, condition: RunConfig["condition"], seed: number, created: string): RunConfig => ({
  schema_version: 1, run_id: runId, created_at: created, condition,
  budget: { steps: 60, tokens: 2_000_000, announced: true },
  sampling: { temperature: 0.7, seed },
  prompt: { version: condition === "claim_on" ? "v2" : "v2-baseline", sha256: "4be1c3d0a8f2e7b96c51d3a0f4e2b8c7d6a5f4e3d2c1b0a9f8e7d6c5b4a39281" },
  models: { orchestrator: { alias: "orch-model", name: "Qwen/Qwen3.8-27B-FP8", revision: "017b9c7" } },
  git_commit: "bcbbb36",
  sandbox: { mode: "landlock", abi: 8 },
})

// q01-on-s1: claim on, finished (agent/tests/runs.py research_run, with real quotes).
const ON = "q01-on-s1"
const onClaims: Claim[] = [
  accepted("claim-000001", "p1", "evaluatesOn", "Spider", PASSAGES.spider, 3),
  accepted("claim-000002", "p1", "evaluatesOn", "BIRD", PASSAGES.spider, 3),
  accepted("claim-000003", "p5", "evaluates on", "GSM8K", PASSAGES.gsm8k, 4),
  accepted("claim-000004", "p1", "authored by", "Hanbing Liu", PASSAGES.author, 4),
  accepted("claim-000005", "p6", "evaluatesOn", "HotpotQA", PASSAGES.hotpotqa, 6, { agent_id: "sub-01" }),
  accepted("claim-000006", "p4", "proposes", "MegaPairs", PASSAGES.megapairs, 6, { agent_id: "sub-01" }),
  accepted("claim-000007", "p4", "title", "MegaPairs: Massive Data Synthesis for Universal Multimodal Retrieval", PASSAGES.megapairs, 6, { agent_id: "sub-01" }),
  {
    claim_id: null, status: "rejected", reason: "not_found", s: "p3", p: "evaluatesOn", o: "HellaSwag", file: "p3.md", paper_id: "p3",
    quote: "we evaluate on HellaSwag with exact match", step: 7, agent_id: "main", origin: "research", anchor: null,
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
    output_head: '{"agent_id": "sub-01", "status": "started"}', output_bytes: 44,
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
  step(8, { model_call: call(1_093, 12.4, "answer", "answer_json_block"), exit_code: null }),
]

const graphRow = (n: number, s: string, o: string, claims: string[], origin: "research" | "attach", metric: string | null = null) => ({
  id: `r${n}`, source: s, source_type: "Paper", predicate: "evaluatesOn", target: o, target_type: "Dataset",
  attributes: { metric }, facts: [{ id: `f${n}`, s, p: "evaluatesOn", o, claims, origin }],
})

const onAnswer: Answer = {
  concept_sha256: "c9ee5264652bee36c072408974aa3b46a0116f27372671768fed3a38b2e32284",
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

// q01-off-s1: claim off, then the attach step (agent/tests/runs.py baseline_run).
const OFF = "q01-off-s1"
const offClaims: Claim[] = [
  accepted("claim-000001", "p1", "evaluatesOn", "Spider", PASSAGES.spider, 5, { origin: "attach" }),
  accepted("claim-000002", "p5", "evaluatesOn", "GSM8K", PASSAGES.gsm8k, 6, { origin: "attach" }),
  accepted("claim-000003", "p6", "evaluatesOn", "HotpotQA", PASSAGES.hotpotqa, 7, { origin: "attach" }),
]
const [a1, a2, a3] = offClaims

const offSteps: Step[] = [
  step(1, { model_call: call(8_640, 3.8), command: `rg -n -i 'spider|bird' "$CORPUS/p1.md" | head -5`, output_head: "9:and supervised fine-tuning (SFT) methods … deployable LLMs using benchmark datasets like Spider and Bird. …", output_bytes: 1_402 }),
  step(2, { model_call: call(9_311, 4.6), command: `rg -n 'GSM8K' "$CORPUS/p5.md"`, output_head: "23:… math reasoning using GSM8K (Cobbe et al., 2021) and MathQA (Amini et al., 2019) …", output_bytes: 988 }),
  step(3, { model_call: call(10_052, 5.1), command: `rg -n 'HotpotQA' "$CORPUS/p6.md" "$CORPUS/p3.md"`, output_head: "p6.md:61:… NQ (Kwiatkowski et al., 2019), and HotpotQA (Yang et al., 2018) datasets for the downstream tasks. …", output_bytes: 1_150 }),
  step(4, { model_call: call(2_147, 9.6, "answer", "answer_json_block"), exit_code: null }),
  step(5, { phase: "attach", origin: "attach", model_call: call(4_410, 2.2), command: claimCmd("p1.md", "deployable LLMs using benchmark datasets like Spider and Bird", [["p1", "evaluatesOn", "Spider"]]), output_head: ok("claim-000001"), output_bytes: 42, claims: [ref(a1)] }),
  step(6, { phase: "attach", origin: "attach", model_call: call(4_380, 2.0), command: claimCmd("p5.md", "math reasoning using GSM8K", [["p5", "evaluatesOn", "GSM8K"]]), output_head: ok("claim-000002"), output_bytes: 42, claims: [ref(a2)] }),
  step(7, { phase: "attach", origin: "attach", model_call: call(4_560, 2.4), command: claimCmd("p6.md", "and HotpotQA \\(Yang et al", [["p6", "evaluatesOn", "HotpotQA"]]), output_head: ok("claim-000003"), output_bytes: 42, claims: [ref(a3)] }),
  step(8, { phase: "attach", origin: "attach", model_call: call(5_400, 3.1, "answer", "answer_json_block"), command: `rg -n -i 'hellaswag' "$CORPUS/p3.md"`, exit_code: 1, output_head: "", output_bytes: 0, coverage: [] }),
]

const offAnswer: Answer = {
  concept_sha256: "c9ee5264652bee36c072408974aa3b46a0116f27372671768fed3a38b2e32284",
  kind: "graph",
  rows: [
    graphRow(1, "p1", "Spider", ["claim-000001"], "attach"),
    graphRow(2, "p5", "GSM8K", ["claim-000002"], "attach"),
    graphRow(3, "p6", "HotpotQA", ["claim-000003"], "attach", "F1"),
    graphRow(4, "p3", "HellaSwag", [], "attach"),
  ],
  notes: "Baseline answer; sources attached afterwards. f4: the attach step answered 'no source found'.",
}

// q01-on-s2: claim on, still running; the mock stream (handlers.ts) plays steps 4-6 and the answer.
const LIVE = "q01-on-s2"
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

function edgeOf(c: Claim, predicate: GraphEdge["predicate"], target: string | null, literal: GraphEdge["literal"] = null): GraphEdge {
  return {
    id: `edge-${c.claim_id!.slice("claim-".length)}`, claim: c.claim_id!, origin: c.origin, step_id: c.step, agent_id: c.agent_id,
    source: `paper:${c.s}`, predicate, target, literal,
    evidence: { file: c.file!, paper: c.paper_id, start: c.anchor!.start, end: c.anchor!.end },
  }
}

const paper = (id: string) => ({ id: `paper:${id}`, kind: "paper" as const, label: id, paper: id })
const entity = (slug: string, label: string) => ({ id: `entity:${slug}`, kind: "entity" as const, label })

const NAMESPACES = { cskg: "https://w3id.org/cskg/ontology#", dblp: "https://dblp.org/rdf/schema#", ours: "urn:thesis-agent:vocab#" }

const onGraph: KnowledgeGraph = {
  schema_version: 1, run_id: ON, namespaces: NAMESPACES,
  sources: { claims_sha256: "9f2c4b1e0d8a7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b", corpus_manifest_sha256: "22e9471b6f0b3c1d2e5a4f7c8b9d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f70819" },
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
  schema_version: 1, run_id: OFF, namespaces: NAMESPACES,
  nodes: [entity("gsm8k", "GSM8K"), entity("hotpotqa", "HotpotQA"), entity("spider", "Spider"), paper("p1"), paper("p5"), paper("p6")],
  edges: [edgeOf(a1, PRED.evaluatesOn, "entity:spider"), edgeOf(a2, PRED.evaluatesOn, "entity:gsm8k"), edgeOf(a3, PRED.evaluatesOn, "entity:hotpotqa")],
}

// --- judge verdicts per fact (gold/judge.py support) ---------------------------------------------------

const verdict = (label: Verdict["label"], rationale: string): Verdict => ({
  label, rationale, model: "sub-model-1", prompt_sha256: "71c0de5a9b8e7f6d5c4b3a2918f7e6d5c4b3a29180f7e6d5c4b3a2918f7e6d5c", cached: true,
})

export const VERDICTS: Record<string, Record<string, Verdict>> = {
  [ON]: {
    f1: verdict("supports", "The quote names Spider as a benchmark dataset the paper's text-to-SQL models are trained and evaluated with."),
    f2: verdict("supports", "Bird (BIRD) is named in the same sentence as a benchmark dataset of the paper."),
    f3: verdict("supports", "The quote lists GSM8K as the dataset used for math reasoning in the paper's evaluation."),
    f4: verdict("partial", "The quote only cites HotpotQA; the surrounding sentence, not the quote itself, says it is used for the downstream evaluation."),
  },
  [OFF]: {
    f1: verdict("supports", "The quote names Spider as a benchmark dataset of the paper."),
    f2: verdict("supports", "GSM8K is the paper's dataset for math reasoning."),
    f3: verdict("partial", "HotpotQA is cited; that it is an evaluation dataset follows from the surrounding sentence only."),
  },
}

// --- scores ---------------------------------------------------------------------------------------------

const prf = (tp: number, fp: number, fn: number) => {
  const precision = tp + fp ? tp / (tp + fp) : null
  const recall = tp + fn ? tp / (tp + fn) : null
  const f1 = precision !== null && recall !== null && precision + recall ? (2 * precision * recall) / (precision + recall) : null
  return { tp, fp, fn, precision, recall, f1 }
}

export const SCORES: Record<string, Score> = {
  [ON]: {
    run_id: ON, qid: "q01", condition: "claim_on", seed: 1, exit_status: "submitted", verify_ok: true, key_version: "v1",
    rows: prf(3, 2, 2), facts: { strict: prf(2, 3, 3), normalised: prf(3, 2, 2), soft: prf(3, 2, 1) }, vital_recall: 0.67,
    support: { facts: 5, with_claims: 4, supports: 3, partial: 1, no: 0, unsourced: 1, support_share: 0.6 },
    cost: { steps: 8, model_calls: 8, tokens: 71_420, tokens_without_attach: 71_420, seconds: 412.6, seconds_without_attach: 412.6, claim_steps: 4, claim_step_tokens: 40_109 },
    matches: {
      matched: [{ fact_id: "f1", key_fact_id: "q01-k1-f1" }, { fact_id: "f3", key_fact_id: "q01-k4-f1" }, { fact_id: "f4", key_fact_id: "q01-k5-f1" }],
      missed: ["q01-k6-f1"],
      wrong: ["f2", "f5"],
    },
  },
  [OFF]: {
    run_id: OFF, qid: "q01", condition: "claim_off", seed: 1, exit_status: "submitted", verify_ok: true, key_version: "v1",
    rows: prf(2, 2, 3), facts: { strict: prf(2, 2, 3), normalised: prf(2, 2, 3), soft: prf(3, 1, 2) }, vital_recall: 0.5,
    support: { facts: 4, with_claims: 3, supports: 2, partial: 1, no: 0, unsourced: 1, support_share: 0.5 },
    cost: { steps: 8, model_calls: 8, tokens: 48_900, tokens_without_attach: 30_150, seconds: 365.2, seconds_without_attach: 238.9, claim_steps: 3, claim_step_tokens: 13_350 },
    matches: {
      matched: [{ fact_id: "f1", key_fact_id: "q01-k1-f1" }, { fact_id: "f2", key_fact_id: "q01-k4-f1" }, { fact_id: "f3", key_fact_id: "q01-k5-f1" }],
      missed: ["q01-k2-f1", "q01-k6-f1"],
      wrong: ["f4"],
    },
  },
}

// --- run summaries and details ----------------------------------------------------------------------

const summary = (s: Partial<RunSummary> & Pick<RunSummary, "run_id" | "qid" | "condition" | "seed" | "created_at">): RunSummary => ({
  temperature: 0.7, exit_status: "submitted", steps: 0, model_calls: 0, tokens: 0, seconds: 0, rows: 0, facts: 0,
  claims_accepted: 0, claims_rejected: 0, verify: "ok", score: null, live: false, ...s,
})

export const RUNS: RunSummary[] = [
  summary({
    run_id: LIVE, qid: "q01", condition: "claim_on", seed: 2, created_at: "2026-10-13T08:02:11Z", exit_status: null,
    steps: 3, model_calls: 3, tokens: 19_582, seconds: 11.0, verify: "unknown", live: true,
  }),
  summary({
    run_id: ON, qid: "q01", condition: "claim_on", seed: 1, created_at: "2026-10-12T09:14:03Z", steps: 8, model_calls: 8,
    tokens: 71_420, seconds: 412.6, rows: 5, facts: 5, claims_accepted: 7, claims_rejected: 1,
    score: { support_share: 0.6, fact_f1: 0.667, row_f1: 0.6 },
  }),
  summary({
    run_id: OFF, qid: "q01", condition: "claim_off", seed: 1, created_at: "2026-10-12T09:31:47Z", steps: 8, model_calls: 8,
    tokens: 48_900, seconds: 365.2, rows: 4, facts: 4, claims_accepted: 3, claims_rejected: 0,
    score: { support_share: 0.5, fact_f1: 0.667, row_f1: 0.444 },
  }),
  summary({
    run_id: "q02-on-s1", qid: "q02", condition: "claim_on", seed: 1, created_at: "2026-10-11T21:40:00Z", exit_status: "budget",
    steps: 60, model_calls: 62, tokens: 2_004_118, seconds: 5_410.2, claims_accepted: 2, claims_rejected: 1,
    score: { support_share: null, fact_f1: 0, row_f1: 0 },
  }),
  summary({
    run_id: "q02-off-s1", qid: "q02", condition: "claim_off", seed: 1, created_at: "2026-10-11T23:12:00Z", exit_status: "budget",
    steps: 60, model_calls: 62, tokens: 2_011_377, seconds: 5_233.7, score: { support_share: null, fact_f1: 0, row_f1: 0 },
  }),
  summary({
    run_id: "q07-on-s1", qid: "q07", condition: "claim_on", seed: 1, created_at: "2026-10-12T14:05:00Z", exit_status: "context_full",
    steps: 41, model_calls: 44, tokens: 1_310_902, seconds: 3_901.5, claims_accepted: 5, claims_rejected: 3, verify: "failed",
  }),
]

const EMPTY_STEPS: Step[] = [
  step(1, { model_call: call(8_701, 4.2), command: `rg -l -i 'jailbreak|red[- ]teaming|safety' "$CORPUS" | wc -l`, output_head: "61", output_bytes: 3 }),
  step(2, { model_call: call(9_920, 5.8), command: `rg -n -i 'jailbreak' "$CORPUS" | head -40`, output_head: "p40.md:12:… a jailbreak attack that …", output_bytes: 8_192 }),
  step(60, { phase: "conclude", model_call: call(61_022, 41.2, "none", "unparsed"), coverage: ["unparsed", "no_final_answer"] }),
]

function detail(s: RunSummary, concept: ConceptBrief, answer: Answer | null, verifyErrors: string[] = []): RunDetail {
  return {
    summary: s,
    config: configFor(s.run_id, s.condition, s.seed, s.created_at),
    concept,
    answer,
    verify: {
      ok: verifyErrors.length === 0 && s.verify !== "failed",
      errors: s.verify === "failed" ? ["events.jsonl: chain broken at record 188 (hash mismatch)", ...verifyErrors] : verifyErrors,
      stats: {
        steps: s.steps, model_calls: s.model_calls, commands: Math.max(0, s.steps - 1), claims: s.claims_accepted + s.claims_rejected,
        claims_accepted: s.claims_accepted, claims_rejected: s.claims_rejected, tokens: s.tokens, seconds: s.seconds,
        ...(s.condition === "claim_off" && s.run_id === OFF
          ? { attach: { steps: 4, tokens: 18_750, claims_accepted: 3 }, without_attach: { steps: 4, tokens: 30_150 } }
          : {}),
      },
    },
  }
}

const BRIEF_Q02 = BRIEFS.q02[0]
const BRIEF_Q07 = BRIEFS.q07[0]

export function initialRunDetails(): Record<string, RunDetail> {
  const byId = Object.fromEntries(RUNS.map((r) => [r.run_id, structuredClone(r)]))
  const emptyAnswer = (kind: Answer["kind"], notes: string): Answer => ({ concept_sha256: "0".repeat(64), kind, rows: [], notes })
  return {
    [ON]: detail(byId[ON], Q01_CONCEPT, onAnswer),
    [OFF]: detail(byId[OFF], Q01_CONCEPT, offAnswer),
    [LIVE]: detail(byId[LIVE], Q01_CONCEPT, null),
    "q02-on-s1": detail(byId["q02-on-s1"], BRIEF_Q02, emptyAnswer("table", "exit status budget")),
    "q02-off-s1": detail(byId["q02-off-s1"], BRIEF_Q02, emptyAnswer("table", "exit status budget")),
    "q07-on-s1": detail(byId["q07-on-s1"], BRIEF_Q07, emptyAnswer("table", "exit status context_full")),
  }
}

export const STEPS: Record<string, Step[]> = {
  [ON]: onSteps, [OFF]: offSteps, [LIVE]: liveSteps,
  "q02-on-s1": EMPTY_STEPS, "q02-off-s1": EMPTY_STEPS, "q07-on-s1": EMPTY_STEPS,
}
export const CLAIMS: Record<string, Claim[]> = { [ON]: onClaims, [OFF]: offClaims, [LIVE]: [] }
export const GRAPHS: Record<string, KnowledgeGraph> = {
  [ON]: onGraph, [OFF]: offGraph, [LIVE]: { schema_version: 1, run_id: LIVE, nodes: [], edges: [] },
}

/** The claim walk of one fact, assembled the way the backend does (claims -> step -> passage). */
export function walkFor(runId: string, answer: Answer | null, factId: string): FactWalk | null {
  const row = answer?.rows.find((r) => r.facts.some((f) => f.id === factId))
  const fact = row?.facts.find((f) => f.id === factId)
  if (!row || !fact) return null
  const claims = CLAIMS[runId] ?? []
  const steps = STEPS[runId] ?? []
  return {
    fact,
    row_id: row.id,
    claims: fact.claims.flatMap((id) => {
      const claim = claims.find((c) => c.claim_id === id)
      const at = claim && steps.find((s) => s.step === claim.step && s.agent_id === claim.agent_id)
      const passage = claim && Object.values(PASSAGES).find((p) => p.paper_id === claim.paper_id && p.highlight.start === claim.anchor?.start)
      return claim && at && passage ? [{ claim, step: at, passage }] : []
    }),
    support: VERDICTS[runId]?.[factId] ?? null,
  }
}

// --- the live run's remaining records (played by the mock stream) ---------------------------------------

let task = 40
const rec = (r: Omit<EventRecord, "task_id" | "agent_id" | "status"> & Partial<EventRecord>): EventRecord => ({
  task_id: `t${String(++task).padStart(6, "0")}`, agent_id: "main", status: "finished", ...r,
})
const usage = (total: number) => ({ prompt_tokens: total - 120, completion_tokens: 120, total_tokens: total })

export const LIVE_RECORDS: EventRecord[] = [
  rec({ subtype: "ai_model_invocation", step_id: 4, generated: { usage: usage(10_090), parse: "strict", reply: "command", finish_reason: "stop" }, custom_metadata: { phase: "research", seconds: 5.6, final_answer: false, origin: "research" } }),
  rec({ subtype: "claim", step_id: 4, status: "accepted", generated: { claim_id: "claim-000001" }, used: { anchor: { file: "p6.md", start: 19702, end: 19726, exact: quoteOf(PASSAGES.hotpotqa) } }, custom_metadata: { s: "p6", p: "evaluatesOn", o: "HotpotQA", origin: "research" } }),
  rec({ subtype: "agent_tool", step_id: 4, used: { command: claimCmd("p6.md", "and HotpotQA \\(Yang et al", [["p6", "evaluatesOn", "HotpotQA"]]) }, generated: { exit_code: 0, timed_out: false, output_bytes: 42 }, custom_metadata: { claim_step: true, claims: 1, origin: "research" } }),
  rec({ subtype: "ai_model_invocation", step_id: 5, generated: { usage: usage(10_802), parse: "strict", reply: "command", finish_reason: "stop" }, custom_metadata: { phase: "research", seconds: 6.1, final_answer: false, origin: "research" } }),
  rec({ subtype: "claim", step_id: 5, status: "rejected", generated: {}, used: { file: "p9.md", quote: "evaluated on Natural Questions" }, custom_metadata: { s: "p9", p: "evaluatesOn", o: "Natural Questions", reason: "not_found", origin: "research" } }),
  rec({ subtype: "agent_tool", step_id: 5, used: { command: `jq -n '{s: "p9", p: "evaluatesOn", o: "Natural Questions", file: "p9.md", quote: "evaluated on Natural Questions"}' | claim` }, generated: { exit_code: 1, timed_out: false, output_bytes: 38 }, custom_metadata: { claim_step: false, claims: 0, repeat: 1, origin: "research" } }),
  rec({ subtype: "ai_model_invocation", step_id: 6, generated: { usage: usage(1_840), parse: "answer_json_block", reply: "answer", finish_reason: "stop" }, custom_metadata: { phase: "conclude", seconds: 11.9, final_answer: true, origin: "research" } }),
]

export const LIVE_ANSWER: Answer = {
  concept_sha256: "c9ee5264652bee36c072408974aa3b46a0116f27372671768fed3a38b2e32284",
  kind: "graph",
  rows: [graphRow(1, "p6", "HotpotQA", ["claim-000001"], "research", "F1")],
  notes: "Stopped early in the mock: one dataset found and claimed.",
}

// --- gold --------------------------------------------------------------------------------------------

export const GOLD: GoldSummary[] = [
  {
    qid: "q01", status: "reviewed",
    coverage: { papers: 336, relevant: 41, not_relevant: 291, no_text: 3, error: 1 },
    counts: { candidates: 212, rows: 58, facts: 131, answers: 96, context: 35, irrelevant: 81, pool: 155, reviewed: 155, overlap: 31 },
    key_version: "v1",
    report: {
      kappa: { value: 0.81, low: 0.66, high: 0.92, n: 31 },
      triage_miss: { rate: 0.04, low: 0.01, high: 0.12, n: 49 },
      screening_false_negative: { rate: 0.02, low: 0.004, high: 0.09, n: 60 },
    },
  },
  {
    qid: "q02", status: "draft",
    coverage: { papers: 336, relevant: 27, not_relevant: 305, no_text: 3, error: 1 },
    counts: { candidates: 140, rows: 22, facts: 74, answers: 61, context: 13, irrelevant: 66, pool: 98, reviewed: 37, overlap: 0 },
    key_version: "v1-draft", report: null,
  },
  {
    qid: "q04", status: "building",
    coverage: { papers: 336, relevant: 12, not_relevant: 98, no_text: 1, error: 0 },
    counts: { candidates: 33 }, key_version: null, report: null,
  },
]

export const GOLD_KEYS: Record<string, AnswerKey> = {
  q01: {
    qid: "q01", concept_sha256: "c9ee5264652bee36c072408974aa3b46a0116f27372671768fed3a38b2e32284", kind: "graph",
    version: "v1", reviewed: true,
    rows: [
      { id: "r1", source: "p1", source_type: "Paper", predicate: "evaluatesOn", target: "Spider", target_type: "Dataset", attributes: { metric: "execution accuracy" }, facts: [{ id: "q01-k1-f1", s: "p1", p: "evaluatesOn", o: "Spider", paper_id: "p1", quote: quoteOf(PASSAGES.spider), vital: true, candidate_id: "q01-c000014" }] },
      { id: "r2", source: "p1", source_type: "Paper", predicate: "evaluatesOn", target: "BIRD", target_type: "Dataset", attributes: { metric: "execution accuracy" }, facts: [{ id: "q01-k2-f1", s: "p1", p: "evaluatesOn", o: "BIRD", paper_id: "p1", quote: quoteOf(PASSAGES.spider), vital: true, candidate_id: "q01-c000015" }] },
      { id: "r4", source: "p5", source_type: "Paper", predicate: "evaluatesOn", target: "GSM8K", target_type: "Dataset", attributes: { metric: "accuracy" }, facts: [{ id: "q01-k4-f1", s: "p5", p: "evaluatesOn", o: "GSM8K", paper_id: "p5", quote: quoteOf(PASSAGES.gsm8k), vital: false, candidate_id: "q01-c000052" }] },
      { id: "r5", source: "p6", source_type: "Paper", predicate: "evaluatesOn", target: "HotpotQA", target_type: "Dataset", attributes: { metric: "F1" }, facts: [{ id: "q01-k5-f1", s: "p6", p: "evaluatesOn", o: "HotpotQA", paper_id: "p6", quote: quoteOf(PASSAGES.hotpotqa), vital: true, candidate_id: "q01-c000071" }] },
      { id: "r6", source: "p6", source_type: "Paper", predicate: "evaluatesOn", target: "Natural Questions", target_type: "Dataset", attributes: { metric: "F1" }, facts: [{ id: "q01-k6-f1", s: "p6", p: "evaluatesOn", o: "NQ", paper_id: "p6", quote: "NQ (Kwiatkowski et al., 2019)", vital: true, candidate_id: "q01-c000070" }] },
    ],
    notes: "Reviewed in Argilla (31 records double-annotated).",
  },
}

// --- results ($RUNS/report/report.json) ---------------------------------------------------------------

const ci = (low: number, high: number) => ({ low, high, level: 0.95, method: "BCa" })

const QR = (qid: string, category: "corpus_wide" | "ambiguous", on: [number, number, number, number, number], off: [number, number, number, number, number, number]) => ({
  qid, category, runs: { claim_on: 3, claim_off: 3 },
  claim_on: { support_share: on[0], fact_f1: on[1], row_f1: on[2], unsourced_share: on[3], tokens: on[4], tokens_without_attach: on[4] },
  claim_off: { support_share: off[0], fact_f1: off[1], row_f1: off[2], unsourced_share: off[3], tokens: off[4], tokens_without_attach: off[5] },
})

export const RESULTS: ResultsReport = {
  generated_at: "2026-10-13T06:00:00Z",
  key_version: "v1",
  n_questions: 12,
  repeats: 3,
  conditions: {
    claim_on: {
      support_share: { mean: 0.71, ci: ci(0.63, 0.78), n: 12 },
      fact_precision: { mean: 0.64, ci: ci(0.55, 0.72), n: 12 },
      fact_recall: { mean: 0.48, ci: ci(0.39, 0.57), n: 12 },
      fact_f1: { mean: 0.54, ci: ci(0.46, 0.62), n: 12 },
      row_f1: { mean: 0.47, ci: ci(0.38, 0.55), n: 12 },
      vital_recall: { mean: 0.58, ci: ci(0.47, 0.68), n: 12 },
      unsourced_share: { mean: 0.12, ci: ci(0.07, 0.18), n: 12 },
      tokens: { mean: 1_284_000, ci: ci(1_102_000, 1_466_000), n: 12 },
      tokens_without_attach: { mean: 1_284_000, ci: ci(1_102_000, 1_466_000), n: 12 },
      seconds: { mean: 3_410, ci: ci(2_960, 3_870), n: 12 },
      seconds_without_attach: { mean: 3_410, ci: ci(2_960, 3_870), n: 12 },
    },
    claim_off: {
      support_share: { mean: 0.52, ci: ci(0.44, 0.6), n: 12 },
      fact_precision: { mean: 0.6, ci: ci(0.51, 0.69), n: 12 },
      fact_recall: { mean: 0.5, ci: ci(0.41, 0.58), n: 12 },
      fact_f1: { mean: 0.53, ci: ci(0.45, 0.61), n: 12 },
      row_f1: { mean: 0.45, ci: ci(0.37, 0.54), n: 12 },
      vital_recall: { mean: 0.6, ci: ci(0.49, 0.7), n: 12 },
      unsourced_share: { mean: 0.27, ci: ci(0.19, 0.35), n: 12 },
      tokens: { mean: 1_398_000, ci: ci(1_201_000, 1_590_000), n: 12 },
      tokens_without_attach: { mean: 1_102_000, ci: ci(948_000, 1_260_000), n: 12 },
      seconds: { mean: 3_720, ci: ci(3_240, 4_190), n: 12 },
      seconds_without_attach: { mean: 2_890, ci: ci(2_500, 3_300), n: 12 },
    },
  },
  per_question: [
    QR("q01", "corpus_wide", [0.74, 0.61, 0.55, 0.08, 1_120_000], [0.55, 0.6, 0.52, 0.21, 1_260_000, 990_000]),
    QR("q02", "corpus_wide", [0.69, 0.48, 0.41, 0.15, 1_530_000], [0.49, 0.5, 0.43, 0.3, 1_610_000, 1_290_000]),
    QR("q03", "corpus_wide", [0.77, 0.58, 0.5, 0.06, 1_210_000], [0.58, 0.55, 0.47, 0.22, 1_320_000, 1_050_000]),
    QR("q04", "corpus_wide", [0.66, 0.52, 0.44, 0.14, 1_350_000], [0.5, 0.54, 0.46, 0.29, 1_480_000, 1_170_000]),
    QR("q05", "corpus_wide", [0.72, 0.6, 0.53, 0.1, 1_190_000], [0.57, 0.58, 0.5, 0.24, 1_300_000, 1_010_000]),
    QR("q06", "corpus_wide", [0.7, 0.55, 0.49, 0.11, 1_420_000], [0.53, 0.52, 0.47, 0.25, 1_520_000, 1_210_000]),
    QR("q07", "ambiguous", [0.68, 0.49, 0.42, 0.16, 1_310_000], [0.46, 0.5, 0.4, 0.33, 1_430_000, 1_120_000]),
    QR("q08", "ambiguous", [0.75, 0.57, 0.48, 0.09, 1_090_000], [0.54, 0.55, 0.45, 0.26, 1_210_000, 960_000]),
    QR("q09", "ambiguous", [0.71, 0.53, 0.46, 0.12, 1_270_000], [0.51, 0.51, 0.44, 0.28, 1_380_000, 1_100_000]),
    QR("q10", "ambiguous", [0.73, 0.56, 0.47, 0.1, 1_240_000], [0.53, 0.53, 0.44, 0.27, 1_350_000, 1_070_000]),
    QR("q11", "ambiguous", [0.64, 0.47, 0.4, 0.18, 1_400_000], [0.48, 0.49, 0.42, 0.31, 1_520_000, 1_220_000]),
    QR("q12", "ambiguous", [0.72, 0.55, 0.48, 0.11, 1_280_000], [0.5, 0.54, 0.46, 0.28, 1_400_000, 1_120_000]),
  ],
  paired: {
    support_share: { metric: "support_share", n: 12, mean_difference: 0.19, ci: ci(0.16, 0.21), wilcoxon: { statistic: 0, p_value: 0.00049 } },
    fact_f1: { metric: "fact_f1", n: 12, mean_difference: 0.01, ci: ci(-0.01, 0.03), wilcoxon: { statistic: 24.5, p_value: 0.41 } },
    unsourced_share: { metric: "unsourced_share", n: 12, mean_difference: -0.15, ci: ci(-0.17, -0.13), wilcoxon: { statistic: 0, p_value: 0.00049 } },
    tokens: { metric: "tokens", n: 12, mean_difference: -114_000, ci: ci(-128_000, -101_000), wilcoxon: { statistic: 0, p_value: 0.00049 } },
  },
  primary: {
    metric: "support_share", n: 12, mean_difference: 0.19, ci: ci(0.16, 0.21), wilcoxon: { statistic: 0, p_value: 0.00049 },
    hypothesis: "The share of answer facts whose quote supports them differs between claim_on and claim_off after attach (paired over the 12 questions, mean of 3 repeats).",
    test: "Wilcoxon signed-rank", alternative: "two-sided", alpha: 0.05, significant: true,
  },
}

// --- jobs -----------------------------------------------------------------------------------------------

export const JOBS: Job[] = [
  { id: "job-0007", kind: "run", args: { qid: "q01", condition: "claim_on", seed: 2, temperature: 0.7 }, state: "running", started_at: "2026-10-13T08:02:09Z", ended_at: null, run_id: LIVE, exit_code: null },
  { id: "job-0006", kind: "run", args: { qid: "q01", condition: "claim_off", seed: 1, temperature: 0.7, attach: true }, state: "done", started_at: "2026-10-12T09:31:45Z", ended_at: "2026-10-12T09:38:12Z", run_id: OFF, exit_code: 0 },
  { id: "job-0005", kind: "run", args: { qid: "q01", condition: "claim_on", seed: 1, temperature: 0.7 }, state: "done", started_at: "2026-10-12T09:14:01Z", ended_at: "2026-10-12T09:21:09Z", run_id: ON, exit_code: 0 },
  { id: "job-0004", kind: "propose", args: { qid: "q07", temperature: 0.7, seed: 7 }, state: "done", started_at: "2026-10-12T08:50:00Z", ended_at: "2026-10-12T08:50:41Z", exit_code: 0 },
  { id: "job-0003", kind: "run", args: { qid: "q07", condition: "claim_on", seed: 1 }, state: "failed", started_at: "2026-10-12T14:04:58Z", ended_at: "2026-10-12T15:10:03Z", run_id: "q07-on-s1", exit_code: 3 },
]

export const JOB_LOGS: Record<string, string[]> = {
  "job-0007": [
    "$ agent run --concept concepts/q01/concept.json --condition claim_on --seed 2 --temperature 0.7 --steps 60 --tokens 2000000",
    "broker: start run=q01-on-s2 records=0 head=0000000000000000",
    "step 1: model call 8,870 tokens (4.0 s), command exit 0",
    "step 2: model call 9,502 tokens (5.0 s), command exit 0",
    "step 3: model call 1,210 tokens (2.0 s): no bash block, coverage unparsed",
  ],
  "job-0006": [
    "$ agent run --concept concepts/q01/concept.json --condition claim_off --seed 1 --temperature 0.7",
    "broker: start run=q01-off-s1 records=0 head=0000000000000000",
    "step 4: final answer, 4 rows",
    "$ agent attach runs/q01-off-s1",
    "attach f1: claim-000001", "attach f2: claim-000002", "attach f3: claim-000003", "attach f4: no source found",
    "$ agent verify runs/q01-off-s1", "verify: ok (31 records, 3 claims)",
    "$ score run runs/q01-off-s1", "score: support share 0.50, fact F1 0.67",
    "exit 0",
  ],
  "job-0003": [
    "$ agent run --concept concepts/q07/concept.json --condition claim_on --seed 1",
    "step 41: HTTP 400 ContextWindowExceededError (context 65,536, prompt 66,102)",
    "step 41: third context-full reply, run ends: exit status context_full",
    "$ agent verify runs/q07-on-s1", "verify: FAILED events.jsonl: chain broken at record 188 (hash mismatch)",
    "exit 3",
  ],
}
