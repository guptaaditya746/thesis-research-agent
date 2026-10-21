# Fidelity review: rag-llm-s1-mixed (sample seed 1)

For each rendering: open the paper at the line, tick **present** if the exact text is there, **states_truth** if it says what the truth column says, **unambiguous** if a reader could not take it for another fact. Note anything else (a fact stated somewhere not listed, a wrong number).

## S002

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S002.a1 | claim | author claim: improves (data: supports) | 4 | `Retrieval augmentation makes the generated answers clearly more accurate.` | [ ] | [ ] | [ ] |
| S002.c1 | condition_label | condition, role baseline: 'generator without any document access' | 7 | `generator without any document access` | [ ] | [ ] | [ ] |
| S002.c2 | condition_label | condition, role rag: 'variant that reads retrieved evidence first' | 7 | `variant that reads retrieved evidence first` | [ ] | [ ] | [ ] |
| S002.c3 | condition_label | condition, role other: 'variant that reformulates the question before the search' | 7 | `variant that reformulates the question before the search` | [ ] | [ ] | [ ] |
| S002.c4 | condition_label | condition, role other: 'retrieval variant that skips the reranker' | 7 | `retrieval variant that skips the reranker` | [ ] | [ ] | [ ] |
| S002.c1 | condition_label | condition, role baseline: 'generator without any document access' | 10 | `generator without any document access` | [ ] | [ ] | [ ] |
| S002.c2 | condition_label | condition, role rag: 'variant that reads retrieved evidence first' | 10 | `variant that reads retrieved evidence first` | [ ] | [ ] | [ ] |
| S002.c3 | condition_label | condition, role other: 'variant that reformulates the question before the search' | 10 | `variant that reformulates the question before the search` | [ ] | [ ] | [ ] |
| S002.c4 | condition_label | condition, role other: 'retrieval variant that skips the reranker' | 10 | `retrieval variant that skips the reranker` | [ ] | [ ] | [ ] |
| S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 10 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S002.c1 | condition_label | condition, role baseline: 'generator without any document access' | 13 | `generator without any document access` | [ ] | [ ] | [ ] |
| S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 13 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S002.m1 | value | baseline 'generator without any document access' / 'fraction of answers judged factually correct' / LawFactQA = 0.505 | 13 | `0.505` | [ ] | [ ] | [ ] |
| S002.c2 | condition_label | condition, role rag: 'variant that reads retrieved evidence first' | 13 | `variant that reads retrieved evidence first` | [ ] | [ ] | [ ] |
| S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 13 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S002.m2 | value | rag 'variant that reads retrieved evidence first' / 'fraction of answers judged factually correct' / LawFactQA = 0.571 | 13 | `571 out of 1,000` | [ ] | [ ] | [ ] |
| S002.c3 | condition_label | condition, role other: 'variant that reformulates the question before the search' | 13 | `variant that reformulates the question before the search` | [ ] | [ ] | [ ] |
| S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 13 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S002.m3 | value | other 'variant that reformulates the question before the search' / 'fraction of answers judged factually correct' / LawFactQA = 0.781 | 13 | `78.1%` | [ ] | [ ] | [ ] |
| S002.c4 | condition_label | condition, role other: 'retrieval variant that skips the reranker' | 13 | `retrieval variant that skips the reranker` | [ ] | [ ] | [ ] |
| S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 13 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S002.m4 | value | other 'retrieval variant that skips the reranker' / 'fraction of answers judged factually correct' / LawFactQA = 0.558 | 13 | `0.558` | [ ] | [ ] | [ ] |
| S002.a1 | claim | author claim: improves (data: supports) | 19 | `Grounding the generator in retrieved documents yields more accurate answers.` | [ ] | [ ] | [ ] |
| S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 19 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |

## S003

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 4 | `parametric-only model` | [ ] | [ ] | [ ] |
| S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 4 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 4 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S003.a1 | claim | author claim: no_effect (data: neutral) | 4 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 10 | `parametric-only model` | [ ] | [ ] | [ ] |
| S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 10 | `B` | [ ] | [ ] | [ ] |
| S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 10 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 10 | `R` | [ ] | [ ] | [ ] |
| S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 10 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 10 | `FLA` | [ ] | [ ] | [ ] |
| S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 10 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 12 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 12 | `parametric-only model` | [ ] | [ ] | [ ] |
| S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 19 | `FLA` | [ ] | [ ] | [ ] |
| S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 21 | `B` | [ ] | [ ] | [ ] |
| S003.m1 | value | baseline 'parametric-only model' / 'fact-level accuracy' / LawFactQA = 0.783 | 21 | `78.3` | [ ] | [ ] | [ ] |
| S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 22 | `R` | [ ] | [ ] | [ ] |
| S003.m2 | value | rag 'retrieval-augmented model' / 'fact-level accuracy' / LawFactQA = 0.774 | 22 | `77.4` | [ ] | [ ] | [ ] |
| S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 25 | `parametric-only model` | [ ] | [ ] | [ ] |
| S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 25 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 28 | `parametric-only model` | [ ] | [ ] | [ ] |
| S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 28 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 28 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S003.a1 | claim | author claim: no_effect (data: neutral) | 28 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |

## S005

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S005.c1 | condition_label | condition, role baseline: 'closed-book model' | 4 | `closed-book model` | [ ] | [ ] | [ ] |
| S005.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 4 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S005.c3 | condition_label | condition, role other: 'fine-tuned model' | 4 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S005.c4 | condition_label | condition, role other: 'RAG without reranking' | 4 | `RAG without reranking` | [ ] | [ ] | [ ] |
| S005.a1 | claim | author claim: no_effect (data: supports) | 4 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| S005.c1 | condition_label | condition, role baseline: 'closed-book model' | 10 | `closed-book model` | [ ] | [ ] | [ ] |
| S005.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 10 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S005.c3 | condition_label | condition, role other: 'fine-tuned model' | 10 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S005.c4 | condition_label | condition, role other: 'RAG without reranking' | 10 | `RAG without reranking` | [ ] | [ ] | [ ] |
| S005.c1 | condition_label | condition, role baseline: 'closed-book model' | 10 | `closed-book model` | [ ] | [ ] | [ ] |
| S005.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 10 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S005.c3 | condition_label | condition, role other: 'fine-tuned model' | 10 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S005.c4 | condition_label | condition, role other: 'RAG without reranking' | 10 | `RAG without reranking` | [ ] | [ ] | [ ] |
| S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `answer accuracy` | [ ] | [ ] | [ ] |
| S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 13 | `answer accuracy` | [ ] | [ ] | [ ] |
| S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `answer accuracy` | [ ] | [ ] | [ ] |
| S005.c1 | condition_label | condition, role baseline: 'closed-book model' | 17 | `closed-book model` | [ ] | [ ] | [ ] |
| S005.m1 | value | baseline 'closed-book model' / 'answer accuracy' / HistoryQuest = 0.406 | 17 | `40.6` | [ ] | [ ] | [ ] |
| S005.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 18 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S005.m2 | value | rag 'retrieval-augmented model' / 'answer accuracy' / HistoryQuest = 0.538 | 18 | `53.8` | [ ] | [ ] | [ ] |
| S005.c3 | condition_label | condition, role other: 'fine-tuned model' | 19 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S005.m3 | value | other 'fine-tuned model' / 'answer accuracy' / HistoryQuest = 0.476 | 19 | `47.6` | [ ] | [ ] | [ ] |
| S005.c4 | condition_label | condition, role other: 'RAG without reranking' | 20 | `RAG without reranking` | [ ] | [ ] | [ ] |
| S005.m4 | value | other 'RAG without reranking' / 'answer accuracy' / HistoryQuest = 0.448 | 20 | `44.8` | [ ] | [ ] | [ ] |
| S005.c3 | condition_label | condition, role other: 'fine-tuned model' | 23 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S005.c4 | condition_label | condition, role other: 'RAG without reranking' | 23 | `RAG without reranking` | [ ] | [ ] | [ ] |
| S005.a1 | claim | author claim: no_effect (data: supports) | 26 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |

## S007

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 4 | `generator without any document access` | [ ] | [ ] | [ ] |
| S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 4 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 4 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 4 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.a1 | claim | author claim: no_effect (data: neutral) | 4 | `Retrieval augmentation does not measurably reduce hallucinated content.` | [ ] | [ ] | [ ] |
| S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 7 | `generator without any document access` | [ ] | [ ] | [ ] |
| S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 7 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 7 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 10 | `generator without any document access` | [ ] | [ ] | [ ] |
| S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 10 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 10 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 10 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 13 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 13 | `generator without any document access` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 13 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.m1 | value | baseline 'generator without any document access' / 'share of answers that contain at least one unsupported statement' / OpenFactQA = 0.391 | 13 | `391 out of 1,000` | [ ] | [ ] | [ ] |
| S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 13 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 13 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.m2 | value | rag 'configuration that looks up supporting documents' / 'share of answers that contain at least one unsupported statement' / OpenFactQA = 0.399 | 13 | `0.399` | [ ] | [ ] | [ ] |
| S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 13 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 13 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.m3 | value | other 'generator adapted to the domain by further training' / 'share of answers that contain at least one unsupported statement' / OpenFactQA = 0.182 | 13 | `18.2%` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 16 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 16 | `generator without any document access` | [ ] | [ ] | [ ] |
| S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 16 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 16 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 19 | `generator without any document access` | [ ] | [ ] | [ ] |
| S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 19 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 19 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 19 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S007.a1 | claim | author claim: no_effect (data: neutral) | 19 | `Adding retrieved documents leaves the amount of hallucinated content essentially unchanged.` | [ ] | [ ] | [ ] |

## S008

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S008.a1 | claim | author claim: improves (data: supports) | 4 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 10 | `vanilla LLM` | [ ] | [ ] | [ ] |
| S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 10 | `B` | [ ] | [ ] | [ ] |
| S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 10 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 10 | `R` | [ ] | [ ] | [ ] |
| S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 10 | `hallucination rate` | [ ] | [ ] | [ ] |
| S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 10 | `HR` | [ ] | [ ] | [ ] |
| S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 10 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 12 | `vanilla LLM` | [ ] | [ ] | [ ] |
| S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 12 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `hallucination rate` | [ ] | [ ] | [ ] |
| S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 17 | `HR` | [ ] | [ ] | [ ] |
| S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 19 | `B` | [ ] | [ ] | [ ] |
| S008.m1 | value | baseline 'vanilla LLM' / 'hallucination rate' / SciFactBench = 0.202 | 19 | `20.2` | [ ] | [ ] | [ ] |
| S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 20 | `R` | [ ] | [ ] | [ ] |
| S008.m2 | value | rag 'retrieval-augmented generator' / 'hallucination rate' / SciFactBench = 0.063 | 20 | `6.3` | [ ] | [ ] | [ ] |
| S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 26 | `vanilla LLM` | [ ] | [ ] | [ ] |
| S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 26 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| S008.a1 | claim | author claim: improves (data: supports) | 26 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |

## S009

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 4 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 4 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 4 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S009.k2 | metric_label | metric other: 'ROUGE-L' | 4 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S009.a1 | claim | author claim: worsens (data: contradicts) | 4 | `Retrieval augmentation makes the generated answers less accurate.` | [ ] | [ ] | [ ] |
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 7 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 7 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 7 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 7 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 10 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 10 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S009.k2 | metric_label | metric other: 'ROUGE-L' | 10 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S009.k2 | metric_label | metric other: 'ROUGE-L' | 10 | `longest common subsequence overlap with the reference answer` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 10 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 15 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S009.k2 | metric_label | metric other: 'ROUGE-L' | 15 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 17 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.m1 | value | baseline 'parametric-only model' / 'fact-level accuracy' / NewsTruthQA = 0.538 | 17 | `53.8` | [ ] | [ ] | [ ] |
| S009.m3 | value | baseline 'parametric-only model' / 'ROUGE-L' / NewsTruthQA = 0.169 | 17 | `16.9` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 18 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.m4 | value | rag 'RAG pipeline' / 'ROUGE-L' / NewsTruthQA = 0.396 | 18 | `39.6` | [ ] | [ ] | [ ] |
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 19 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.m5 | value | baseline 'parametric-only model' / 'fact-level accuracy' / LawFactQA = 0.499 | 19 | `49.9` | [ ] | [ ] | [ ] |
| S009.m7 | value | baseline 'parametric-only model' / 'ROUGE-L' / LawFactQA = 0.382 | 19 | `38.2` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 20 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.m6 | value | rag 'RAG pipeline' / 'fact-level accuracy' / LawFactQA = 0.407 | 20 | `40.7` | [ ] | [ ] | [ ] |
| S009.m8 | value | rag 'RAG pipeline' / 'ROUGE-L' / LawFactQA = 0.153 | 20 | `15.3` | [ ] | [ ] | [ ] |
| S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 22 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 22 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.m2 | value | rag 'RAG pipeline' / 'fact-level accuracy' / NewsTruthQA = 0.465 | 22 | `7.3 percentage points lower` | [ ] | [ ] | [ ] |
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 22 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 25 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 25 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 28 | `parametric-only model` | [ ] | [ ] | [ ] |
| S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 28 | `RAG pipeline` | [ ] | [ ] | [ ] |
| S009.a1 | claim | author claim: worsens (data: contradicts) | 28 | `Grounding the generator in retrieved documents yields less accurate answers.` | [ ] | [ ] | [ ] |

## S013

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S013.a1 | claim | author claim: worsens (data: contradicts) | 4 | `Retrieval augmentation makes the generated answers less accurate.` | [ ] | [ ] | [ ] |
| S013.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 10 | `vanilla LLM` | [ ] | [ ] | [ ] |
| S013.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 10 | `B` | [ ] | [ ] | [ ] |
| S013.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 10 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| S013.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 10 | `R` | [ ] | [ ] | [ ] |
| S013.c3 | condition_label | condition, role other: 'RAG with random passages' (also A1) | 10 | `RAG with random passages` | [ ] | [ ] | [ ] |
| S013.c3 | condition_label | condition, role other: 'RAG with random passages' (also A1) | 10 | `A1` | [ ] | [ ] | [ ] |
| S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `answer accuracy` | [ ] | [ ] | [ ] |
| S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `AA` | [ ] | [ ] | [ ] |
| S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| S013.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 12 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 17 | `answer accuracy` | [ ] | [ ] | [ ] |
| S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 19 | `AA` | [ ] | [ ] | [ ] |
| S013.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 21 | `B` | [ ] | [ ] | [ ] |
| S013.m1 | value | baseline 'vanilla LLM' / 'answer accuracy' / PopCultureQA = 0.475 | 21 | `47.5` | [ ] | [ ] | [ ] |
| S013.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 22 | `R` | [ ] | [ ] | [ ] |
| S013.m2 | value | rag 'retrieval-augmented generator' / 'answer accuracy' / PopCultureQA = 0.403 | 22 | `40.3` | [ ] | [ ] | [ ] |
| S013.c3 | condition_label | condition, role other: 'RAG with random passages' (also A1) | 23 | `A1` | [ ] | [ ] | [ ] |
| S013.m3 | value | other 'RAG with random passages' / 'answer accuracy' / PopCultureQA = 0.425 | 23 | `42.5` | [ ] | [ ] | [ ] |
| S013.a1 | claim | author claim: worsens (data: contradicts) | 29 | `Grounding the generator in retrieved documents yields less accurate answers.` | [ ] | [ ] | [ ] |

## S014

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 4 | `closed-book model` | [ ] | [ ] | [ ] |
| S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 4 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 4 | `answer accuracy` | [ ] | [ ] | [ ] |
| S014.k2 | metric_label | metric other: 'ROUGE-L' | 4 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S014.k3 | metric_label | metric other: 'latency' | 4 | `latency` | [ ] | [ ] | [ ] |
| S014.a1 | claim | author claim: worsens (data: contradicts) | 4 | `Retrieval augmentation makes the generated answers less accurate.` | [ ] | [ ] | [ ] |
| S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 7 | `closed-book model` | [ ] | [ ] | [ ] |
| S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 7 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 10 | `closed-book model` | [ ] | [ ] | [ ] |
| S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 10 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `answer accuracy` | [ ] | [ ] | [ ] |
| S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| S014.k2 | metric_label | metric other: 'ROUGE-L' | 10 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S014.k2 | metric_label | metric other: 'ROUGE-L' | 10 | `longest common subsequence overlap with the reference answer` | [ ] | [ ] | [ ] |
| S014.k3 | metric_label | metric other: 'latency' | 10 | `latency` | [ ] | [ ] | [ ] |
| S014.k3 | metric_label | metric other: 'latency' | 10 | `mean seconds needed to produce one answer` | [ ] | [ ] | [ ] |
| S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `answer accuracy` | [ ] | [ ] | [ ] |
| S014.k2 | metric_label | metric other: 'ROUGE-L' | 15 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S014.k3 | metric_label | metric other: 'latency' | 15 | `latency` | [ ] | [ ] | [ ] |
| S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 17 | `closed-book model` | [ ] | [ ] | [ ] |
| S014.m1 | value | baseline 'closed-book model' / 'answer accuracy' / BioClaimQA = 0.606 | 17 | `60.6` | [ ] | [ ] | [ ] |
| S014.m3 | value | baseline 'closed-book model' / 'ROUGE-L' / BioClaimQA = 0.188 | 17 | `18.8` | [ ] | [ ] | [ ] |
| S014.m5 | value | baseline 'closed-book model' / 'latency' / BioClaimQA = 1.16 | 17 | `1.16` | [ ] | [ ] | [ ] |
| S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 18 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S014.m4 | value | rag 'retrieval-augmented model' / 'ROUGE-L' / BioClaimQA = 0.497 | 18 | `49.7` | [ ] | [ ] | [ ] |
| S014.m6 | value | rag 'retrieval-augmented model' / 'latency' / BioClaimQA = 1.12 | 18 | `1.12` | [ ] | [ ] | [ ] |
| S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 19 | `closed-book model` | [ ] | [ ] | [ ] |
| S014.m7 | value | baseline 'closed-book model' / 'answer accuracy' / TriviaCheck = 0.389 | 19 | `38.9` | [ ] | [ ] | [ ] |
| S014.m9 | value | baseline 'closed-book model' / 'ROUGE-L' / TriviaCheck = 0.543 | 19 | `54.3` | [ ] | [ ] | [ ] |
| S014.m11 | value | baseline 'closed-book model' / 'latency' / TriviaCheck = 1.96 | 19 | `1.96` | [ ] | [ ] | [ ] |
| S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 20 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S014.m8 | value | rag 'retrieval-augmented model' / 'answer accuracy' / TriviaCheck = 0.294 | 20 | `29.4` | [ ] | [ ] | [ ] |
| S014.m10 | value | rag 'retrieval-augmented model' / 'ROUGE-L' / TriviaCheck = 0.263 | 20 | `26.3` | [ ] | [ ] | [ ] |
| S014.m12 | value | rag 'retrieval-augmented model' / 'latency' / TriviaCheck = 0.94 | 20 | `0.94` | [ ] | [ ] | [ ] |
| S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 22 | `answer accuracy` | [ ] | [ ] | [ ] |
| S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 22 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S014.m2 | value | rag 'retrieval-augmented model' / 'answer accuracy' / BioClaimQA = 0.535 | 22 | `7.1 percentage points lower` | [ ] | [ ] | [ ] |
| S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 22 | `closed-book model` | [ ] | [ ] | [ ] |
| S014.k3 | metric_label | metric other: 'latency' | 25 | `latency` | [ ] | [ ] | [ ] |
| S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 28 | `closed-book model` | [ ] | [ ] | [ ] |
| S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 28 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S014.a1 | claim | author claim: worsens (data: contradicts) | 28 | `Grounding the generator in retrieved documents yields less accurate answers.` | [ ] | [ ] | [ ] |

## S016

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 1 | `Hallucination Frequency` | [ ] | [ ] | [ ] |
| S016.a1 | claim | author claim: improves (data: supports) | 4 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 7 | `hallucination frequency` | [ ] | [ ] | [ ] |
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 7 | `fraction of answers judged to contain invented facts` | [ ] | [ ] | [ ] |
| S016.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 10 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S016.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' | 10 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| S016.c3 | condition_label | condition, role other: 'RAG with random passages' | 10 | `RAG with random passages` | [ ] | [ ] | [ ] |
| S016.c4 | condition_label | condition, role other: 'query-rewriting variant' | 10 | `query-rewriting variant` | [ ] | [ ] | [ ] |
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 10 | `hallucination frequency` | [ ] | [ ] | [ ] |
| S016.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 13 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 13 | `hallucination frequency` | [ ] | [ ] | [ ] |
| S016.m1 | value | baseline 'no-retrieval baseline' / 'hallucination frequency' / HistoryQuest = 0.103 | 13 | `10.3%` | [ ] | [ ] | [ ] |
| S016.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' | 13 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 13 | `hallucination frequency` | [ ] | [ ] | [ ] |
| S016.m2 | value | rag 'retrieval-augmented generator' / 'hallucination frequency' / HistoryQuest = 0.051 | 13 | `5.1%` | [ ] | [ ] | [ ] |
| S016.c3 | condition_label | condition, role other: 'RAG with random passages' | 13 | `RAG with random passages` | [ ] | [ ] | [ ] |
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 13 | `hallucination frequency` | [ ] | [ ] | [ ] |
| S016.m3 | value | other 'RAG with random passages' / 'hallucination frequency' / HistoryQuest = 0.412 | 13 | `41.2%` | [ ] | [ ] | [ ] |
| S016.c4 | condition_label | condition, role other: 'query-rewriting variant' | 13 | `query-rewriting variant` | [ ] | [ ] | [ ] |
| S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 13 | `hallucination frequency` | [ ] | [ ] | [ ] |
| S016.m4 | value | other 'query-rewriting variant' / 'hallucination frequency' / HistoryQuest = 0.304 | 13 | `30.4%` | [ ] | [ ] | [ ] |
| S016.c4 | condition_label | condition, role other: 'query-rewriting variant' | 16 | `query-rewriting variant` | [ ] | [ ] | [ ] |
| S016.a1 | claim | author claim: improves (data: supports) | 19 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |

## S019

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 4 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 4 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 4 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 4 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S019.k2 | metric_label | metric other: 'ROUGE-L' | 4 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S019.k3 | metric_label | metric other: 'latency' | 4 | `latency` | [ ] | [ ] | [ ] |
| S019.a1 | claim | author claim: no_effect (data: neutral) | 4 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 7 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 7 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 7 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 10 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 10 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 10 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 10 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 10 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| S019.k2 | metric_label | metric other: 'ROUGE-L' | 10 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S019.k2 | metric_label | metric other: 'ROUGE-L' | 10 | `longest common subsequence overlap with the reference answer` | [ ] | [ ] | [ ] |
| S019.k3 | metric_label | metric other: 'latency' | 10 | `latency` | [ ] | [ ] | [ ] |
| S019.k3 | metric_label | metric other: 'latency' | 10 | `mean seconds needed to produce one answer` | [ ] | [ ] | [ ] |
| S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 15 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S019.k2 | metric_label | metric other: 'ROUGE-L' | 15 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S019.k3 | metric_label | metric other: 'latency' | 15 | `latency` | [ ] | [ ] | [ ] |
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 17 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.m1 | value | baseline 'no-retrieval baseline' / 'fact-level accuracy' / TriviaCheck = 0.642 | 17 | `64.2` | [ ] | [ ] | [ ] |
| S019.m4 | value | baseline 'no-retrieval baseline' / 'ROUGE-L' / TriviaCheck = 0.482 | 17 | `48.2` | [ ] | [ ] | [ ] |
| S019.m7 | value | baseline 'no-retrieval baseline' / 'latency' / TriviaCheck = 1.91 | 17 | `1.91` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 18 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.m5 | value | rag 'retrieve-then-read model' / 'ROUGE-L' / TriviaCheck = 0.106 | 18 | `10.6` | [ ] | [ ] | [ ] |
| S019.m8 | value | rag 'retrieve-then-read model' / 'latency' / TriviaCheck = 1.09 | 18 | `1.09` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 19 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.m3 | value | other 'fine-tuned model' / 'fact-level accuracy' / TriviaCheck = 0.591 | 19 | `59.1` | [ ] | [ ] | [ ] |
| S019.m6 | value | other 'fine-tuned model' / 'ROUGE-L' / TriviaCheck = 0.379 | 19 | `37.9` | [ ] | [ ] | [ ] |
| S019.m9 | value | other 'fine-tuned model' / 'latency' / TriviaCheck = 0.78 | 19 | `0.78` | [ ] | [ ] | [ ] |
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 20 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.m10 | value | baseline 'no-retrieval baseline' / 'fact-level accuracy' / HistoryQuest = 0.495 | 20 | `49.5` | [ ] | [ ] | [ ] |
| S019.m13 | value | baseline 'no-retrieval baseline' / 'ROUGE-L' / HistoryQuest = 0.291 | 20 | `29.1` | [ ] | [ ] | [ ] |
| S019.m16 | value | baseline 'no-retrieval baseline' / 'latency' / HistoryQuest = 1.99 | 20 | `1.99` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 21 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.m11 | value | rag 'retrieve-then-read model' / 'fact-level accuracy' / HistoryQuest = 0.503 | 21 | `50.3` | [ ] | [ ] | [ ] |
| S019.m14 | value | rag 'retrieve-then-read model' / 'ROUGE-L' / HistoryQuest = 0.393 | 21 | `39.3` | [ ] | [ ] | [ ] |
| S019.m17 | value | rag 'retrieve-then-read model' / 'latency' / HistoryQuest = 2.63 | 21 | `2.63` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 22 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.m12 | value | other 'fine-tuned model' / 'fact-level accuracy' / HistoryQuest = 0.556 | 22 | `55.6` | [ ] | [ ] | [ ] |
| S019.m15 | value | other 'fine-tuned model' / 'ROUGE-L' / HistoryQuest = 0.512 | 22 | `51.2` | [ ] | [ ] | [ ] |
| S019.m18 | value | other 'fine-tuned model' / 'latency' / HistoryQuest = 2.97 | 22 | `2.97` | [ ] | [ ] | [ ] |
| S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 24 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 24 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.m2 | value | rag 'retrieve-then-read model' / 'fact-level accuracy' / TriviaCheck = 0.634 | 24 | `0.8 percentage points lower` | [ ] | [ ] | [ ] |
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 24 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 24 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.k2 | metric_label | metric other: 'ROUGE-L' | 24 | `ROUGE-L` | [ ] | [ ] | [ ] |
| S019.k3 | metric_label | metric other: 'latency' | 24 | `Latency` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 24 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 27 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 27 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 27 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 30 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 30 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 30 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S019.a1 | claim | author claim: no_effect (data: neutral) | 30 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |
| S019.k3 | metric_label | metric other: 'latency' | 30 | `latency` | [ ] | [ ] | [ ] |

## S020

| fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|
| S020.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 4 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 4 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 4 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 4 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 4 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 4 | `answer accuracy` | [ ] | [ ] | [ ] |
| S020.a1 | claim | author claim: no_effect (data: supports) | 4 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 7 | `answer accuracy` | [ ] | [ ] | [ ] |
| S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 7 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| S020.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 10 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 10 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 10 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 10 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 10 | `answer accuracy` | [ ] | [ ] | [ ] |
| S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 13 | `answer accuracy` | [ ] | [ ] | [ ] |
| S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `answer accuracy` | [ ] | [ ] | [ ] |
| S020.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 17 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S020.m1 | value | baseline 'no-retrieval baseline' / 'answer accuracy' / LawFactQA = 0.523 | 17 | `52.3` | [ ] | [ ] | [ ] |
| S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 18 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S020.m2 | value | rag 'retrieval-augmented model' / 'answer accuracy' / LawFactQA = 0.646 | 18 | `64.6` | [ ] | [ ] | [ ] |
| S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 19 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S020.m3 | value | other 'fine-tuned model' / 'answer accuracy' / LawFactQA = 0.552 | 19 | `55.2` | [ ] | [ ] | [ ] |
| S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 20 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| S020.m4 | value | other 'self-consistency decoding' / 'answer accuracy' / LawFactQA = 0.357 | 20 | `35.7` | [ ] | [ ] | [ ] |
| S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 22 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 25 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 25 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 25 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| S020.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 28 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 28 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 28 | `fine-tuned model` | [ ] | [ ] | [ ] |
| S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 28 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| S020.a1 | claim | author claim: no_effect (data: supports) | 28 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |

