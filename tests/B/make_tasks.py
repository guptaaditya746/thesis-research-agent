import json
from pathlib import Path

concepts = [
    "papers that compare dense and sparse retrieval",
    "which datasets papers use for passage retrieval",
    "first authors who publish on question answering",
    "methods that use contrastive learning for reranking",
    "papers reporting recall at 100",
    "authors who introduce a multilingual benchmark",
    "papers with a table comparing five or more systems",
    "which studies evaluate on MS MARCO",
    "work that reports zero-shot results",
    "papers discussing retrieval augmented generation",
    "methods that use hard negative mining",
    "datasets containing scientific abstracts",
    "papers that report nDCG@10",
    "systems that combine lexical and dense retrieval",
    "authors of papers that cite DPR",
    "papers with an ablation study on query expansion",
    "datasets used for conversational search",
    "papers reporting results on BEIR",
    "methods that use pseudo relevance feedback",
    "papers with a reported human evaluation",
    "which paper describes a cross encoder",
    "authors who work on entity retrieval",
    "papers that evaluate domain adaptation",
    "systems using reciprocal rank fusion",
    "papers reporting MAP scores",
    "benchmarks for long document retrieval",
    "papers that use BM25 as a baseline",
    "methods for retrieval over tables",
    "papers that compare exact and approximate nearest neighbors",
    "authors of work on passage attribution",
    "datasets used for legal search",
    "papers with multilingual query evaluation",
    "systems that rerank top 100 candidates",
    "papers reporting latency measurements",
    "work on retrieval from knowledge graphs",
    "which papers evaluate on Natural Questions",
    "methods that use synthetic training data",
    "papers with human relevance judgments",
    "datasets used for code search",
    "authors who study zero-shot retrieval",
    "papers with a discussion of evaluation leakage",
    "systems that use late interaction",
    "papers reporting precision at 10",
    "which studies use query logs",
    "methods for robust retrieval",
    "papers that use dense passage retrieval",
    "datasets for biomedical search",
    "papers comparing cross encoders and bi encoders",
    "authors of papers that study search intent",
    "systems that combine multiple retrievers",
]
commands = [
    ("grep -Rni 'retrieval' /corpus | head -20", "Found 12 candidate paragraphs across 4 papers."),
    ("grep -Rni 'dataset' /corpus | head -20", "Found several dataset mentions; output abbreviated."),
    ("python3 - <<'PY'\nimport json\nprint('papers', 337)\nPY", "papers 337"),
    ("grep -Rni 'Table 1' /corpus | head", "No matches"),
    ("find /corpus -maxdepth 1 -name '*.md' | head", "/corpus/p1.md\n/corpus/p2.md"),
    ("grep -Rni 'BM25' /corpus | head -5", "Matched p14.md and p26.md"),
]
out = Path(__file__).with_name("tasks.jsonl")
with out.open("w", encoding="utf-8") as f:
    for i, concept in enumerate(concepts):
        n = i % 6
        steps = commands[:n]
        history = "\n".join(f"$ {cmd}\n{result}" for cmd, result in steps) or "(none)"
        prompt = f"Research concept: {concept}.\nPrevious steps:\n{history}\nWhat is your next command?"
        f.write(json.dumps({"id": f"t{i+1:02d}", "prompt": prompt}, ensure_ascii=False) + "\n")
print(f"wrote {len(concepts)} prompts to {out}")
