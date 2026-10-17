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

# Papers with no treatment/control experiment (`synth build --irrelevant N`, our addition; docs/evidence-system.md
# F2): a survey of the question's topic (names retrieval, so a term screen lets it through and the screening
# question must say no) and a paper on another topic (none of the protocol's screen terms). Rules on top of
# the ones above: no digits at all, and no sentence that names retrieval and states an effect in the words of
# evidence/extractors/terms.CLAIMS (the fidelity check `added_claims` fails such a sentence); the other-topic
# paper never says retrieval, RAG, closed-book, accuracy or hallucination, not even as a substring of a word
# ("average" holds "rag"), so a screen that matches without word boundaries finds nothing either.
IRRELEVANT = {
    "survey": {
        "titles": (
            "Retrieval-Augmented Generation: A Survey of Architectures and Open Problems",
            "A Taxonomy of Retrieval-Augmented Language Models",
            "Where Do the Passages Go? A Survey of Retrieval in Text Generation",
        ),
        "abstract": (
            "We survey the literature on retrieval-augmented generation and organise it by where the retrieved "
            "passages enter the generation process.",
            "This survey reports no experiments of its own; it summarises the design space and lists the "
            "questions the surveyed papers leave open.",
            "We close with a list of evaluation practices that would make future comparisons easier to interpret.",
        ),
        "sections": ("Scope and method", "Taxonomy", "Evaluation practices", "Open problems"),
        "body": (
            "We collected papers that describe a retrieval component feeding a text generator and read each one "
            "for its architecture, its training recipe and its evaluation setup.",
            "Papers that only mention retrieval in passing, or that evaluate a retriever alone, were left out of "
            "the survey.",
            "The first family passes retrieved passages to the generator as part of the prompt and leaves the "
            "generator weights untouched.",
            "The second family trains the retriever and the generator jointly, so the retriever learns which "
            "passages the generator can use.",
            "A third family retrieves at the token level during decoding, which ties the retrieval frequency to "
            "the length of the output.",
            "Most surveyed papers index an encyclopedic corpus split into short passages, and a few use the web "
            "through a search interface.",
            "Evaluation setups vary widely in the datasets, the judging procedure and the reported measures, "
            "which makes a direct comparison across papers hard.",
            "Several papers judge answers with a single annotator, and only a minority report agreement between "
            "annotators.",
            "We refrain from aggregating the reported numbers, because the setups differ too much for an "
            "aggregate to mean anything.",
            "Open problems include the treatment of conflicting passages, the cost of retrieval at inference time "
            "and the evaluation of long-form answers.",
            "How a generator should behave when the retrieved passages contradict each other is rarely addressed.",
            "We hope the taxonomy helps readers place new work and choose comparable evaluation settings.",
            "The survey is limited to papers written in English and to work published before our cut-off date.",
            "Retrieval latency is reported in only a handful of papers, and never together with the generation cost.",
        ),
        "conclusion": (
            "We presented a taxonomy of retrieval-augmented generation and a list of open problems; the empirical "
            "questions remain for controlled studies to settle.",
        ),
    },
    "other": {
        "titles": (
            "Subword Tokenisation for Source Code: A Comparison of Vocabulary Construction Methods",
            "Byte-Level versus Subword Vocabularies for Code Completion Models",
            "How Vocabulary Size Shapes Code Completion Quality",
        ),
        "abstract": (
            "We study how the vocabulary of a code language model is built and how that choice shows up in "
            "completion quality and inference cost.",
            "This paper describes the construction methods and the properties of the token sequences they "
            "produce, and discusses what the choice means for training and serving.",
        ),
        "sections": ("Vocabulary construction", "Properties of the token sequences", "Cost of training and serving"),
        "body": (
            "Byte-pair encoding merges frequent character pairs until the vocabulary reaches a chosen size, and "
            "the merges are learned on a sample of the training corpus.",
            "A unigram model instead starts from a large candidate vocabulary and prunes it to the tokens that "
            "explain the corpus best.",
            "Source code has long identifiers, repeated operators and strict whitespace, so the choices made for "
            "natural language transfer poorly.",
            "Identifiers written in camel case or snake case are split differently by the two methods, which "
            "changes the number of tokens per line.",
            "Whitespace tokens dominate the sequences of indentation-sensitive languages unless runs of spaces "
            "are merged into single tokens.",
            "A larger vocabulary shortens the token sequences but enlarges the embedding table and the output "
            "layer of the model.",
            "We record the mean number of tokens per line and the share of identifiers that are split into "
            "more than one token.",
            "Serving cost grows with the sequence length, so a vocabulary that shortens sequences also shortens "
            "the time per completion.",
            "The training corpus is a deduplicated snapshot of permissively licensed repositories in several "
            "programming languages.",
            "We leave the interaction between the vocabulary and the positional encoding to future work.",
            "Our scripts for building each vocabulary are released with the paper.",
            "Rare tokens that occur in a single repository are pruned before training to keep the embedding "
            "table compact.",
        ),
        "conclusion": (
            "We described the trade-offs between vocabulary construction methods for code models and the "
            "properties of the sequences they produce.",
        ),
    },
}
