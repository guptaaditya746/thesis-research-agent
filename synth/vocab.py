"""Fixed vocabularies for the synthetic studies and their papers.

Everything a paper says comes from here or from the ground truth, so a corpus is a pure function of the
seed. Rules the lists obey (the fidelity checks rely on them): no digits anywhere (so no filler number can
be read as a measured value), and no filler or claim sentence contains a condition or metric name, so
every rendering of a fact is one the renderer recorded as a placement.
"""
from __future__ import annotations

QUESTION = "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"

# Conditions: (label, synonym, description). Labels and synonyms take an article in the text ("the ...").
BASELINES = (
    ("closed-book model", "model that answers from its own parameters",
     "answers each question from what it learned in pre-training, without access to any documents"),
    ("parametric-only model", "generator without any document access",
     "relies on its parametric knowledge alone and never sees an external source"),
    ("no-retrieval baseline", "language model used on its own",
     "receives only the question and produces an answer directly"),
    ("vanilla LLM", "plain generator with no lookup step",
     "is prompted with the question and nothing else"),
)
RAGS = (
    ("retrieval-augmented model", "model that consults the document index before answering",
     "retrieves passages from the reference collection and conditions its answer on them"),
    ("RAG pipeline", "system grounded in retrieved passages",
     "first searches the reference collection and then writes an answer from the passages it found"),
    ("retrieval-augmented generator", "variant that reads retrieved evidence first",
     "is given the top passages of a dense retriever together with the question"),
    ("retrieve-then-read model", "configuration that looks up supporting documents",
     "looks up supporting documents for each question and reads them before it answers"),
)
OTHERS = (
    ("RAG without reranking", "retrieval variant that skips the reranker",
     "uses the same retriever but keeps the passages in their original order"),
    ("RAG with random passages", "variant fed with randomly drawn passages",
     "receives passages drawn at random from the collection instead of retrieved ones"),
    ("fine-tuned model", "generator adapted to the domain by further training",
     "was trained further on in-domain question and answer pairs"),
    ("chain-of-thought prompting", "model prompted to reason step by step",
     "is asked to write out its reasoning before giving the final answer"),
    ("self-consistency decoding", "model that samples several answers and votes",
     "samples several answers and returns the most frequent one"),
    ("query-rewriting variant", "variant that reformulates the question before the search",
     "rewrites each question into a search query before it consults the collection"),
)
# Codes for the distributed level, by role; distractor conditions get A1, A2.
CODES = {"baseline": "B", "rag": "R"}
OTHER_CODES = ("A1", "A2")

# Metrics: canonical -> [(name, abbreviation, description)]. Units: fraction values are written as percent
# (one decimal) or as a fraction; seconds as written.
QUESTION_METRICS = {
    "factual_accuracy": (
        ("factual accuracy", "FA", "share of answers whose facts are all correct"),
        ("answer accuracy", "AA", "proportion of questions answered with correct facts"),
        ("fact-level accuracy", "FLA", "fraction of answers judged factually correct"),
    ),
    "hallucination_rate": (
        ("hallucination rate", "HR", "share of answers that contain at least one unsupported statement"),
        ("unsupported-answer rate", "UAR", "proportion of answers with a statement not backed by any source"),
        ("hallucination frequency", "HF", "fraction of answers judged to contain invented facts"),
    ),
}
# Distractor metrics: (key, name, abbreviation, description, higher_is_better, unit).
OTHER_METRICS = (
    ("bleu", "BLEU", "BLEU", "n-gram overlap with the reference answer", True, "fraction"),
    ("rouge_l", "ROUGE-L", "RL", "longest common subsequence overlap with the reference answer", True, "fraction"),
    ("latency", "latency", "Lat.", "mean seconds needed to produce one answer", False, "seconds"),
)

DATASETS = ("OpenFactQA", "TriviaCheck", "BioClaimQA", "HistoryQuest", "SciFactBench", "NewsTruthQA",
            "GeoFacts", "MedAnswerSet", "LawFactQA", "PopCultureQA")

# Author claims: (claim direction, canonical metric) -> two wordings (abstract, conclusion).
CLAIMS = {
    ("improves", "factual_accuracy"): (
        "Retrieval augmentation makes the generated answers clearly more accurate.",
        "Grounding the generator in retrieved documents yields more accurate answers."),
    ("improves", "hallucination_rate"): (
        "Retrieval augmentation clearly reduces hallucinated content in the answers.",
        "Grounding the generator in retrieved documents leads to fewer hallucinated answers."),
    ("no_effect", "factual_accuracy"): (
        "Retrieval augmentation does not make the answers measurably more accurate.",
        "Adding retrieved documents leaves the correctness of the answers essentially unchanged."),
    ("no_effect", "hallucination_rate"): (
        "Retrieval augmentation does not measurably reduce hallucinated content.",
        "Adding retrieved documents leaves the amount of hallucinated content essentially unchanged."),
    ("worsens", "factual_accuracy"): (
        "Retrieval augmentation makes the generated answers less accurate.",
        "Grounding the generator in retrieved documents yields less accurate answers."),
    ("worsens", "hallucination_rate"): (
        "Retrieval augmentation increases hallucinated content in the answers.",
        "Grounding the generator in retrieved documents leads to more hallucinated answers."),
}

TITLES = (
    "Grounding Answers in Evidence: An Empirical Study on {dataset}",
    "When Does Retrieval Help? Revisiting Knowledge-Intensive Question Answering on {dataset}",
    "Looking It Up: Retrieval and Factuality in Open-Domain Answers on {dataset}",
    "Evidence In, Facts Out? A Controlled Evaluation on {dataset}",
    "Parametric Memory versus External Documents: Lessons from {dataset}",
    "On the Reliability of Generated Answers: A Study on {dataset}",
)
INTRO = (
    "Large language models answer many questions fluently, yet their answers are not always correct.",
    "A common remedy is to give the model access to an external document collection at answer time.",
    "Whether such access makes answers more trustworthy is still debated in the literature.",
    "Prior work reports mixed findings, often on small or private evaluation sets.",
    "Our study adds a controlled comparison on a public benchmark.",
    "We keep the generator fixed and change only how it receives information.",
    "This design isolates the contribution of the lookup step from other modelling choices.",
    "We release our prompts and evaluation scripts to support replication.",
)
METHOD = (
    "All systems share the same generator weights and the same decoding settings.",
    "Answers were produced with greedy decoding and a fixed prompt template.",
    "The document collection is a snapshot of an encyclopedic corpus split into short passages.",
    "Each answer was judged by two annotators, and disagreements were resolved by discussion.",
    "Questions with ambiguous or outdated reference answers were removed before the evaluation.",
    "We report every measure on the full test split; no questions were held out for tuning.",
)
PADDING = (
    "Passages were indexed with a standard dense encoder and stored in an approximate nearest neighbour index.",
    "Prompt templates were written once and not tuned on the test questions.",
    "Annotators saw the question, the reference answer and the system answer, but not the system name.",
    "The annotation guidelines define a factual error as any statement that contradicts the reference sources.",
    "Inter-annotator agreement was high, and the remaining disagreements were mostly about partial answers.",
    "Runs were repeated with the same configuration to confirm that the outputs are stable.",
    "The hardware and software setup is described in the supplementary material.",
    "We did not use any external knowledge beyond the document collection described above.",
)
DISCUSSION = (
    "The comparison suggests that the way information reaches the generator matters.",
    "Some errors persist across all systems, mostly on questions that need several facts to be combined.",
    "Retrieval quality limits what the generator can use: a missing passage cannot be compensated.",
    "Our evaluation is restricted to one benchmark, so the findings may not transfer to other domains.",
    "Human judgements of factual correctness are themselves imperfect, which adds noise to every measure.",
    "Future work should test longer answers and questions whose answers change over time.",
)
CONCLUSION = (
    "We presented a controlled comparison of answer generation with and without external documents.",
    "Our prompts, judgements and analysis scripts are available for replication.",
    "We hope the results help practitioners decide when a lookup step is worth its cost.",
)
