# Fidelity review: rag-claude-s1-mixed (sample seed 1)

For each rendering: open the paper at the line, tick **present** if the exact text is there, **states_truth** if it says what the truth column says, **unambiguous** if a reader could not take it for another fact. Note anything else (a fact stated somewhere not listed, a wrong number).

In each paper, priority 1 (the numbers and the authors' claims) comes first; do those rows first.

## S001

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S001.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| 1 | S001.m1 | value | baseline 'parametric-only model' / 'hallucination rate' / LawFactQA = 0.295 | 21 | `29.5%` | [ ] | [ ] | [ ] |
| 1 | S001.m2 | value | rag 'retrieval-augmented model' / 'hallucination rate' / LawFactQA = 0.178 | 23 | `17.8%` | [ ] | [ ] | [ ] |
| 1 | S001.m3 | value | other 'chain-of-thought prompting' / 'hallucination rate' / LawFactQA = 0.094 | 25 | `9.4%` | [ ] | [ ] | [ ] |
| 1 | S001.m4 | value | other 'fine-tuned model' / 'hallucination rate' / LawFactQA = 0.471 | 27 | `47.1%` | [ ] | [ ] | [ ] |
| 1 | S001.a1 | claim | author claim: improves (data: supports) | 35 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 5 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 9 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S001.c1 | condition_label | condition, role baseline: 'parametric-only model' | 13 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S001.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 13 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S001.c3 | condition_label | condition, role other: 'chain-of-thought prompting' | 13 | `chain-of-thought prompting` | [ ] | [ ] | [ ] |
| 2 | S001.c4 | condition_label | condition, role other: 'fine-tuned model' | 13 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S001.c1 | condition_label | condition, role baseline: 'parametric-only model' | 21 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 21 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S001.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 23 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 23 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S001.c3 | condition_label | condition, role other: 'chain-of-thought prompting' | 25 | `chain-of-thought prompting` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 25 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S001.c4 | condition_label | condition, role other: 'fine-tuned model' | 27 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 27 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S001.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 35 | `hallucination rate` | [ ] | [ ] | [ ] |

## S002

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S002.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation makes the generated answers clearly more accurate.` | [ ] | [ ] | [ ] |
| 1 | S002.m1 | value | baseline 'generator without any document access' / 'fraction of answers judged factually correct' / LawFactQA = 0.505 | 21 | `0.505` | [ ] | [ ] | [ ] |
| 1 | S002.m2 | value | rag 'variant that reads retrieved evidence first' / 'fraction of answers judged factually correct' / LawFactQA = 0.571 | 23 | `571 out of 1,000` | [ ] | [ ] | [ ] |
| 1 | S002.m3 | value | other 'variant that reformulates the question before the search' / 'fraction of answers judged factually correct' / LawFactQA = 0.781 | 25 | `78.1%` | [ ] | [ ] | [ ] |
| 1 | S002.m4 | value | other 'retrieval variant that skips the reranker' / 'fraction of answers judged factually correct' / LawFactQA = 0.558 | 27 | `0.558` | [ ] | [ ] | [ ] |
| 1 | S002.a1 | claim | author claim: improves (data: supports) | 35 | `Grounding the generator in retrieved documents yields more accurate answers.` | [ ] | [ ] | [ ] |
| 2 | S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 5 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S002.c1 | condition_label | condition, role baseline: 'generator without any document access' | 13 | `generator without any document access` | [ ] | [ ] | [ ] |
| 2 | S002.c2 | condition_label | condition, role rag: 'variant that reads retrieved evidence first' | 13 | `variant that reads retrieved evidence first` | [ ] | [ ] | [ ] |
| 2 | S002.c3 | condition_label | condition, role other: 'variant that reformulates the question before the search' | 13 | `variant that reformulates the question before the search` | [ ] | [ ] | [ ] |
| 2 | S002.c4 | condition_label | condition, role other: 'retrieval variant that skips the reranker' | 13 | `retrieval variant that skips the reranker` | [ ] | [ ] | [ ] |
| 2 | S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 15 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S002.c1 | condition_label | condition, role baseline: 'generator without any document access' | 21 | `generator without any document access` | [ ] | [ ] | [ ] |
| 2 | S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 21 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S002.c2 | condition_label | condition, role rag: 'variant that reads retrieved evidence first' | 23 | `variant that reads retrieved evidence first` | [ ] | [ ] | [ ] |
| 2 | S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 23 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S002.c3 | condition_label | condition, role other: 'variant that reformulates the question before the search' | 25 | `variant that reformulates the question before the search` | [ ] | [ ] | [ ] |
| 2 | S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 25 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S002.c4 | condition_label | condition, role other: 'retrieval variant that skips the reranker' | 27 | `retrieval variant that skips the reranker` | [ ] | [ ] | [ ] |
| 2 | S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 27 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S002.k1 | metric_label | metric factual_accuracy: 'fraction of answers judged factually correct' | 35 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |

## S003

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S003.a1 | claim | author claim: no_effect (data: neutral) | 5 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| 1 | S003.m1 | value | baseline 'parametric-only model' / 'fact-level accuracy' / LawFactQA = 0.783 | 29 | `78.3` | [ ] | [ ] | [ ] |
| 1 | S003.m2 | value | rag 'retrieval-augmented model' / 'fact-level accuracy' / LawFactQA = 0.774 | 30 | `77.4` | [ ] | [ ] | [ ] |
| 1 | S003.a1 | claim | author claim: no_effect (data: neutral) | 38 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 1 | `Fact-Level Accuracy` | [ ] | [ ] | [ ] |
| 2 | S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 5 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 15 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 15 | `B` | [ ] | [ ] | [ ] |
| 2 | S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 15 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 15 | `R` | [ ] | [ ] | [ ] |
| 2 | S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `FLA` | [ ] | [ ] | [ ] |
| 2 | S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S003.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 27 | `FLA` | [ ] | [ ] | [ ] |
| 2 | S003.c1 | condition_label | condition, role baseline: 'parametric-only model' (also B) | 29 | `B` | [ ] | [ ] | [ ] |
| 2 | S003.c2 | condition_label | condition, role rag: 'retrieval-augmented model' (also R) | 30 | `R` | [ ] | [ ] | [ ] |

## S004

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S004.a1 | claim | author claim: no_effect (data: neutral) | 5 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| 1 | S004.m1 | value | baseline 'parametric-only model' / 'answer accuracy' / LawFactQA = 0.598 | 29 | `59.8` | [ ] | [ ] | [ ] |
| 1 | S004.m3 | value | baseline 'parametric-only model' / 'latency' / LawFactQA = 2.74 | 29 | `2.74` | [ ] | [ ] | [ ] |
| 1 | S004.m5 | value | baseline 'parametric-only model' / 'BLEU' / LawFactQA = 0.114 | 29 | `11.4` | [ ] | [ ] | [ ] |
| 1 | S004.m4 | value | rag 'retrieve-then-read model' / 'latency' / LawFactQA = 3.47 | 30 | `3.47` | [ ] | [ ] | [ ] |
| 1 | S004.m6 | value | rag 'retrieve-then-read model' / 'BLEU' / LawFactQA = 0.511 | 30 | `51.1` | [ ] | [ ] | [ ] |
| 1 | S004.m7 | value | baseline 'parametric-only model' / 'answer accuracy' / GeoFacts = 0.527 | 31 | `52.7` | [ ] | [ ] | [ ] |
| 1 | S004.m9 | value | baseline 'parametric-only model' / 'latency' / GeoFacts = 1.57 | 31 | `1.57` | [ ] | [ ] | [ ] |
| 1 | S004.m11 | value | baseline 'parametric-only model' / 'BLEU' / GeoFacts = 0.399 | 31 | `39.9` | [ ] | [ ] | [ ] |
| 1 | S004.m8 | value | rag 'retrieve-then-read model' / 'answer accuracy' / GeoFacts = 0.536 | 32 | `53.6` | [ ] | [ ] | [ ] |
| 1 | S004.m10 | value | rag 'retrieve-then-read model' / 'latency' / GeoFacts = 3.21 | 32 | `3.21` | [ ] | [ ] | [ ] |
| 1 | S004.m12 | value | rag 'retrieve-then-read model' / 'BLEU' / GeoFacts = 0.192 | 32 | `19.2` | [ ] | [ ] | [ ] |
| 1 | S004.m2 | value | rag 'retrieve-then-read model' / 'answer accuracy' / LawFactQA = 0.589 | 36 | `0.9 percentage points lower` | [ ] | [ ] | [ ] |
| 1 | S004.a1 | claim | author claim: no_effect (data: neutral) | 44 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S004.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 1 | `Answer Accuracy` | [ ] | [ ] | [ ] |
| 2 | S004.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 5 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S004.k2 | metric_label | metric other: 'latency' | 5 | `latency` | [ ] | [ ] | [ ] |
| 2 | S004.k3 | metric_label | metric other: 'BLEU' | 5 | `BLEU` | [ ] | [ ] | [ ] |
| 2 | S004.c1 | condition_label | condition, role baseline: 'parametric-only model' | 15 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S004.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 15 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S004.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 17 | `Answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S004.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 17 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| 2 | S004.k2 | metric_label | metric other: 'latency' | 17 | `Latency` | [ ] | [ ] | [ ] |
| 2 | S004.k2 | metric_label | metric other: 'latency' | 17 | `mean seconds needed to produce one answer` | [ ] | [ ] | [ ] |
| 2 | S004.k3 | metric_label | metric other: 'BLEU' | 17 | `BLEU` | [ ] | [ ] | [ ] |
| 2 | S004.k3 | metric_label | metric other: 'BLEU' | 17 | `n-gram overlap with the reference answer` | [ ] | [ ] | [ ] |
| 2 | S004.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 27 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S004.k2 | metric_label | metric other: 'latency' | 27 | `latency` | [ ] | [ ] | [ ] |
| 2 | S004.k3 | metric_label | metric other: 'BLEU' | 27 | `BLEU` | [ ] | [ ] | [ ] |
| 2 | S004.c1 | condition_label | condition, role baseline: 'parametric-only model' | 29 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S004.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 30 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S004.c1 | condition_label | condition, role baseline: 'parametric-only model' | 31 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S004.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 32 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S004.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 34 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S004.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 34 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S004.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 36 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S004.c1 | condition_label | condition, role baseline: 'parametric-only model' | 36 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S004.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 36 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S004.k2 | metric_label | metric other: 'latency' | 40 | `Latency` | [ ] | [ ] | [ ] |

## S005

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S005.a1 | claim | author claim: no_effect (data: supports) | 5 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| 1 | S005.m1 | value | baseline 'closed-book model' / 'answer accuracy' / HistoryQuest = 0.406 | 29 | `40.6` | [ ] | [ ] | [ ] |
| 1 | S005.m2 | value | rag 'retrieval-augmented model' / 'answer accuracy' / HistoryQuest = 0.538 | 30 | `53.8` | [ ] | [ ] | [ ] |
| 1 | S005.m3 | value | other 'fine-tuned model' / 'answer accuracy' / HistoryQuest = 0.476 | 31 | `47.6` | [ ] | [ ] | [ ] |
| 1 | S005.m4 | value | other 'RAG without reranking' / 'answer accuracy' / HistoryQuest = 0.448 | 32 | `44.8` | [ ] | [ ] | [ ] |
| 1 | S005.a1 | claim | author claim: no_effect (data: supports) | 40 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S005.c1 | condition_label | condition, role baseline: 'closed-book model' | 13 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S005.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 13 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S005.c3 | condition_label | condition, role other: 'fine-tuned model' | 13 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S005.c4 | condition_label | condition, role other: 'RAG without reranking' | 13 | `RAG without reranking` | [ ] | [ ] | [ ] |
| 2 | S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| 2 | S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 27 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S005.c1 | condition_label | condition, role baseline: 'closed-book model' | 29 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S005.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 30 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S005.c3 | condition_label | condition, role other: 'fine-tuned model' | 31 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S005.c4 | condition_label | condition, role other: 'RAG without reranking' | 32 | `RAG without reranking` | [ ] | [ ] | [ ] |
| 2 | S005.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 36 | `answer accuracy` | [ ] | [ ] | [ ] |

## S006

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S006.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| 1 | S006.m1 | value | baseline 'vanilla LLM' / 'hallucination rate' / PopCultureQA = 0.215 | 19 | `21.5%` | [ ] | [ ] | [ ] |
| 1 | S006.m2 | value | rag 'RAG pipeline' / 'hallucination rate' / PopCultureQA = 0.183 | 21 | `18.3%` | [ ] | [ ] | [ ] |
| 1 | S006.m3 | value | other 'fine-tuned model' / 'hallucination rate' / PopCultureQA = 0.098 | 23 | `9.8%` | [ ] | [ ] | [ ] |
| 1 | S006.a1 | claim | author claim: improves (data: supports) | 31 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |
| 2 | S006.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 1 | `Hallucination Rate` | [ ] | [ ] | [ ] |
| 2 | S006.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 5 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S006.c1 | condition_label | condition, role baseline: 'vanilla LLM' | 13 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S006.c2 | condition_label | condition, role rag: 'RAG pipeline' | 13 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S006.c3 | condition_label | condition, role other: 'fine-tuned model' | 13 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S006.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 13 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S006.c1 | condition_label | condition, role baseline: 'vanilla LLM' | 19 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S006.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 19 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S006.c2 | condition_label | condition, role rag: 'RAG pipeline' | 21 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S006.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 21 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S006.c3 | condition_label | condition, role other: 'fine-tuned model' | 23 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S006.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 23 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S006.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 31 | `hallucination rate` | [ ] | [ ] | [ ] |

## S007

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S007.a1 | claim | author claim: no_effect (data: neutral) | 5 | `Retrieval augmentation does not measurably reduce hallucinated content.` | [ ] | [ ] | [ ] |
| 1 | S007.m1 | value | baseline 'generator without any document access' / 'share of answers that contain at least one unsupported statement' / OpenFactQA = 0.391 | 27 | `391 out of 1,000` | [ ] | [ ] | [ ] |
| 1 | S007.m2 | value | rag 'configuration that looks up supporting documents' / 'share of answers that contain at least one unsupported statement' / OpenFactQA = 0.399 | 29 | `0.399` | [ ] | [ ] | [ ] |
| 1 | S007.m3 | value | other 'generator adapted to the domain by further training' / 'share of answers that contain at least one unsupported statement' / OpenFactQA = 0.182 | 31 | `18.2%` | [ ] | [ ] | [ ] |
| 1 | S007.a1 | claim | author claim: no_effect (data: neutral) | 39 | `Adding retrieved documents leaves the amount of hallucinated content essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 5 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 15 | `generator without any document access` | [ ] | [ ] | [ ] |
| 2 | S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 15 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| 2 | S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 15 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| 2 | S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 17 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S007.c1 | condition_label | condition, role baseline: 'generator without any document access' | 27 | `generator without any document access` | [ ] | [ ] | [ ] |
| 2 | S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 27 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S007.c2 | condition_label | condition, role rag: 'configuration that looks up supporting documents' | 29 | `configuration that looks up supporting documents` | [ ] | [ ] | [ ] |
| 2 | S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 29 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S007.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 31 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| 2 | S007.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 31 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |

## S008

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S008.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| 1 | S008.m1 | value | baseline 'vanilla LLM' / 'hallucination rate' / SciFactBench = 0.202 | 27 | `20.2` | [ ] | [ ] | [ ] |
| 1 | S008.m2 | value | rag 'retrieval-augmented generator' / 'hallucination rate' / SciFactBench = 0.063 | 28 | `6.3` | [ ] | [ ] | [ ] |
| 1 | S008.a1 | claim | author claim: improves (data: supports) | 36 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |
| 2 | S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 5 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 5 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| 2 | S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 5 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 11 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 11 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| 2 | S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 15 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 15 | `B` | [ ] | [ ] | [ ] |
| 2 | S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 15 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| 2 | S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 15 | `R` | [ ] | [ ] | [ ] |
| 2 | S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `HR` | [ ] | [ ] | [ ] |
| 2 | S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 19 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| 2 | S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 23 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 25 | `HR` | [ ] | [ ] | [ ] |
| 2 | S008.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 27 | `B` | [ ] | [ ] | [ ] |
| 2 | S008.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 28 | `R` | [ ] | [ ] | [ ] |
| 2 | S008.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 36 | `hallucination rate` | [ ] | [ ] | [ ] |

## S009

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S009.a1 | claim | author claim: worsens (data: contradicts) | 5 | `Retrieval augmentation makes the generated answers less accurate.` | [ ] | [ ] | [ ] |
| 1 | S009.m1 | value | baseline 'parametric-only model' / 'fact-level accuracy' / NewsTruthQA = 0.538 | 25 | `53.8` | [ ] | [ ] | [ ] |
| 1 | S009.m3 | value | baseline 'parametric-only model' / 'ROUGE-L' / NewsTruthQA = 0.169 | 25 | `16.9` | [ ] | [ ] | [ ] |
| 1 | S009.m4 | value | rag 'RAG pipeline' / 'ROUGE-L' / NewsTruthQA = 0.396 | 26 | `39.6` | [ ] | [ ] | [ ] |
| 1 | S009.m5 | value | baseline 'parametric-only model' / 'fact-level accuracy' / LawFactQA = 0.499 | 27 | `49.9` | [ ] | [ ] | [ ] |
| 1 | S009.m7 | value | baseline 'parametric-only model' / 'ROUGE-L' / LawFactQA = 0.382 | 27 | `38.2` | [ ] | [ ] | [ ] |
| 1 | S009.m6 | value | rag 'RAG pipeline' / 'fact-level accuracy' / LawFactQA = 0.407 | 28 | `40.7` | [ ] | [ ] | [ ] |
| 1 | S009.m8 | value | rag 'RAG pipeline' / 'ROUGE-L' / LawFactQA = 0.153 | 28 | `15.3` | [ ] | [ ] | [ ] |
| 1 | S009.m2 | value | rag 'RAG pipeline' / 'fact-level accuracy' / NewsTruthQA = 0.465 | 30 | `7.3 percentage points lower` | [ ] | [ ] | [ ] |
| 1 | S009.a1 | claim | author claim: worsens (data: contradicts) | 38 | `Grounding the generator in retrieved documents yields less accurate answers.` | [ ] | [ ] | [ ] |
| 2 | S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 5 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 5 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 5 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S009.k2 | metric_label | metric other: 'ROUGE-L' | 5 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 9 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S009.k2 | metric_label | metric other: 'ROUGE-L' | 9 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 9 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 9 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 13 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 13 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `Fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S009.k2 | metric_label | metric other: 'ROUGE-L' | 17 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S009.k2 | metric_label | metric other: 'ROUGE-L' | 17 | `longest common subsequence overlap with the reference answer` | [ ] | [ ] | [ ] |
| 2 | S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 23 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S009.k2 | metric_label | metric other: 'ROUGE-L' | 23 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 25 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 26 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 27 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 28 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 30 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 30 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S009.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 30 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S009.c1 | condition_label | condition, role baseline: 'parametric-only model' | 38 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S009.c2 | condition_label | condition, role rag: 'RAG pipeline' | 38 | `RAG pipeline` | [ ] | [ ] | [ ] |

## S010

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S010.a1 | claim | author claim: no_effect (data: supports) | 5 | `Retrieval augmentation does not measurably reduce hallucinated content.` | [ ] | [ ] | [ ] |
| 1 | S010.m1 | value | baseline 'vanilla LLM' / 'hallucination rate' / TriviaCheck = 0.381 | 29 | `38.1` | [ ] | [ ] | [ ] |
| 1 | S010.m2 | value | rag 'retrieval-augmented model' / 'hallucination rate' / TriviaCheck = 0.323 | 30 | `32.3` | [ ] | [ ] | [ ] |
| 1 | S010.m3 | value | other 'RAG without reranking' / 'hallucination rate' / TriviaCheck = 0.231 | 31 | `23.1` | [ ] | [ ] | [ ] |
| 1 | S010.a1 | claim | author claim: no_effect (data: supports) | 39 | `Adding retrieved documents leaves the amount of hallucinated content essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S010.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 5 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S010.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 5 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S010.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 5 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S010.c1 | condition_label | condition, role baseline: 'vanilla LLM' | 11 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S010.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 11 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S010.c3 | condition_label | condition, role other: 'RAG without reranking' | 11 | `RAG without reranking` | [ ] | [ ] | [ ] |
| 2 | S010.c1 | condition_label | condition, role baseline: 'vanilla LLM' | 17 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S010.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 17 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S010.c3 | condition_label | condition, role other: 'RAG without reranking' | 17 | `RAG without reranking` | [ ] | [ ] | [ ] |
| 2 | S010.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 19 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S010.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 19 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S010.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 25 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S010.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 27 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S010.c1 | condition_label | condition, role baseline: 'vanilla LLM' | 29 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S010.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 30 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S010.c3 | condition_label | condition, role other: 'RAG without reranking' | 31 | `RAG without reranking` | [ ] | [ ] | [ ] |
| 2 | S010.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 39 | `hallucination rate` | [ ] | [ ] | [ ] |

## S011

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S011.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation makes the generated answers clearly more accurate.` | [ ] | [ ] | [ ] |
| 1 | S011.m1 | value | baseline 'closed-book model' / 'fact-level accuracy' / TriviaCheck = 0.543 | 23 | `54.3%` | [ ] | [ ] | [ ] |
| 1 | S011.m2 | value | rag 'retrieve-then-read model' / 'fact-level accuracy' / TriviaCheck = 0.676 | 25 | `67.6%` | [ ] | [ ] | [ ] |
| 1 | S011.m3 | value | other 'chain-of-thought prompting' / 'fact-level accuracy' / TriviaCheck = 0.718 | 27 | `71.8%` | [ ] | [ ] | [ ] |
| 1 | S011.m4 | value | other 'RAG with random passages' / 'fact-level accuracy' / TriviaCheck = 0.581 | 29 | `58.1%` | [ ] | [ ] | [ ] |
| 1 | S011.a1 | claim | author claim: improves (data: supports) | 37 | `Grounding the generator in retrieved documents yields more accurate answers.` | [ ] | [ ] | [ ] |
| 2 | S011.c1 | condition_label | condition, role baseline: 'closed-book model' | 5 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S011.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 5 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S011.c3 | condition_label | condition, role other: 'chain-of-thought prompting' | 5 | `chain-of-thought prompting` | [ ] | [ ] | [ ] |
| 2 | S011.c4 | condition_label | condition, role other: 'RAG with random passages' | 5 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S011.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 5 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S011.c1 | condition_label | condition, role baseline: 'closed-book model' | 13 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S011.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 13 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S011.c3 | condition_label | condition, role other: 'chain-of-thought prompting' | 13 | `Chain-of-thought prompting` | [ ] | [ ] | [ ] |
| 2 | S011.c4 | condition_label | condition, role other: 'RAG with random passages' | 13 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S011.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `Fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S011.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 17 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S011.c1 | condition_label | condition, role baseline: 'closed-book model' | 23 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S011.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 23 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S011.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 25 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S011.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 25 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S011.c3 | condition_label | condition, role other: 'chain-of-thought prompting' | 27 | `chain-of-thought prompting` | [ ] | [ ] | [ ] |
| 2 | S011.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 27 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S011.c4 | condition_label | condition, role other: 'RAG with random passages' | 29 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S011.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 29 | `fact-level accuracy` | [ ] | [ ] | [ ] |

## S012

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S012.a1 | claim | author claim: worsens (data: contradicts) | 5 | `Retrieval augmentation increases hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| 1 | S012.m1 | value | baseline 'model that answers from its own parameters' / 'share of answers that contain at least one unsupported statement' / NewsTruthQA = 0.193 | 27 | `0.193` | [ ] | [ ] | [ ] |
| 1 | S012.m2 | value | rag 'variant that reads retrieved evidence first' / 'share of answers that contain at least one unsupported statement' / NewsTruthQA = 0.292 | 29 | `29.2%` | [ ] | [ ] | [ ] |
| 1 | S012.a1 | claim | author claim: worsens (data: contradicts) | 37 | `Grounding the generator in retrieved documents leads to more hallucinated answers.` | [ ] | [ ] | [ ] |
| 2 | S012.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 5 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S012.c1 | condition_label | condition, role baseline: 'model that answers from its own parameters' | 15 | `model that answers from its own parameters` | [ ] | [ ] | [ ] |
| 2 | S012.c2 | condition_label | condition, role rag: 'variant that reads retrieved evidence first' | 15 | `variant that reads retrieved evidence first` | [ ] | [ ] | [ ] |
| 2 | S012.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 17 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S012.c1 | condition_label | condition, role baseline: 'model that answers from its own parameters' | 27 | `model that answers from its own parameters` | [ ] | [ ] | [ ] |
| 2 | S012.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 27 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S012.c2 | condition_label | condition, role rag: 'variant that reads retrieved evidence first' | 29 | `variant that reads retrieved evidence first` | [ ] | [ ] | [ ] |
| 2 | S012.k1 | metric_label | metric hallucination_rate: 'share of answers that contain at least one unsupported statement' | 29 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |

## S013

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S013.a1 | claim | author claim: worsens (data: contradicts) | 5 | `Retrieval augmentation makes the generated answers less accurate.` | [ ] | [ ] | [ ] |
| 1 | S013.m1 | value | baseline 'vanilla LLM' / 'answer accuracy' / PopCultureQA = 0.475 | 29 | `47.5` | [ ] | [ ] | [ ] |
| 1 | S013.m2 | value | rag 'retrieval-augmented generator' / 'answer accuracy' / PopCultureQA = 0.403 | 30 | `40.3` | [ ] | [ ] | [ ] |
| 1 | S013.m3 | value | other 'RAG with random passages' / 'answer accuracy' / PopCultureQA = 0.425 | 31 | `42.5` | [ ] | [ ] | [ ] |
| 1 | S013.a1 | claim | author claim: worsens (data: contradicts) | 39 | `Grounding the generator in retrieved documents yields less accurate answers.` | [ ] | [ ] | [ ] |
| 2 | S013.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 13 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S013.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 13 | `B` | [ ] | [ ] | [ ] |
| 2 | S013.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 13 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| 2 | S013.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 13 | `R` | [ ] | [ ] | [ ] |
| 2 | S013.c3 | condition_label | condition, role other: 'RAG with random passages' (also A1) | 13 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S013.c3 | condition_label | condition, role other: 'RAG with random passages' (also A1) | 13 | `A1` | [ ] | [ ] | [ ] |
| 2 | S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `AA` | [ ] | [ ] | [ ] |
| 2 | S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| 2 | S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 27 | `AA` | [ ] | [ ] | [ ] |
| 2 | S013.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 29 | `B` | [ ] | [ ] | [ ] |
| 2 | S013.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' (also R) | 30 | `R` | [ ] | [ ] | [ ] |
| 2 | S013.c3 | condition_label | condition, role other: 'RAG with random passages' (also A1) | 31 | `A1` | [ ] | [ ] | [ ] |
| 2 | S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 35 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S013.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 39 | `answer accuracy` | [ ] | [ ] | [ ] |

## S014

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S014.a1 | claim | author claim: worsens (data: contradicts) | 5 | `Retrieval augmentation makes the generated answers less accurate.` | [ ] | [ ] | [ ] |
| 1 | S014.m1 | value | baseline 'closed-book model' / 'answer accuracy' / BioClaimQA = 0.606 | 23 | `60.6` | [ ] | [ ] | [ ] |
| 1 | S014.m3 | value | baseline 'closed-book model' / 'ROUGE-L' / BioClaimQA = 0.188 | 23 | `18.8` | [ ] | [ ] | [ ] |
| 1 | S014.m5 | value | baseline 'closed-book model' / 'latency' / BioClaimQA = 1.16 | 23 | `1.16` | [ ] | [ ] | [ ] |
| 1 | S014.m4 | value | rag 'retrieval-augmented model' / 'ROUGE-L' / BioClaimQA = 0.497 | 24 | `49.7` | [ ] | [ ] | [ ] |
| 1 | S014.m6 | value | rag 'retrieval-augmented model' / 'latency' / BioClaimQA = 1.12 | 24 | `1.12` | [ ] | [ ] | [ ] |
| 1 | S014.m7 | value | baseline 'closed-book model' / 'answer accuracy' / TriviaCheck = 0.389 | 25 | `38.9` | [ ] | [ ] | [ ] |
| 1 | S014.m9 | value | baseline 'closed-book model' / 'ROUGE-L' / TriviaCheck = 0.543 | 25 | `54.3` | [ ] | [ ] | [ ] |
| 1 | S014.m11 | value | baseline 'closed-book model' / 'latency' / TriviaCheck = 1.96 | 25 | `1.96` | [ ] | [ ] | [ ] |
| 1 | S014.m8 | value | rag 'retrieval-augmented model' / 'answer accuracy' / TriviaCheck = 0.294 | 26 | `29.4` | [ ] | [ ] | [ ] |
| 1 | S014.m10 | value | rag 'retrieval-augmented model' / 'ROUGE-L' / TriviaCheck = 0.263 | 26 | `26.3` | [ ] | [ ] | [ ] |
| 1 | S014.m12 | value | rag 'retrieval-augmented model' / 'latency' / TriviaCheck = 0.94 | 26 | `0.94` | [ ] | [ ] | [ ] |
| 1 | S014.m2 | value | rag 'retrieval-augmented model' / 'answer accuracy' / BioClaimQA = 0.535 | 28 | `7.1 percentage points lower` | [ ] | [ ] | [ ] |
| 1 | S014.a1 | claim | author claim: worsens (data: contradicts) | 36 | `Grounding the generator in retrieved documents yields less accurate answers.` | [ ] | [ ] | [ ] |
| 2 | S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 5 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 5 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 5 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S014.k2 | metric_label | metric other: 'ROUGE-L' | 5 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S014.k3 | metric_label | metric other: 'latency' | 5 | `latency` | [ ] | [ ] | [ ] |
| 2 | S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 9 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 9 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 13 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 13 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 15 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| 2 | S014.k2 | metric_label | metric other: 'ROUGE-L' | 15 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S014.k2 | metric_label | metric other: 'ROUGE-L' | 15 | `longest common subsequence overlap with the reference answer` | [ ] | [ ] | [ ] |
| 2 | S014.k3 | metric_label | metric other: 'latency' | 15 | `latency` | [ ] | [ ] | [ ] |
| 2 | S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 21 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S014.k2 | metric_label | metric other: 'ROUGE-L' | 21 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S014.k3 | metric_label | metric other: 'latency' | 21 | `latency` | [ ] | [ ] | [ ] |
| 2 | S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 23 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 24 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 25 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 26 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S014.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 28 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S014.c1 | condition_label | condition, role baseline: 'closed-book model' | 28 | `closed-book model` | [ ] | [ ] | [ ] |
| 2 | S014.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 28 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S014.k3 | metric_label | metric other: 'latency' | 32 | `Latency` | [ ] | [ ] | [ ] |
| 2 | S014.k2 | metric_label | metric other: 'ROUGE-L' | 32 | `ROUGE-L` | [ ] | [ ] | [ ] |

## S015

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S015.a1 | claim | author claim: no_effect (data: supports) | 5 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| 1 | S015.m1 | value | baseline 'parametric-only model' / 'answer accuracy' / SciFactBench = 0.625 | 31 | `62.5` | [ ] | [ ] | [ ] |
| 1 | S015.m2 | value | rag 'RAG pipeline' / 'answer accuracy' / SciFactBench = 0.661 | 32 | `66.1` | [ ] | [ ] | [ ] |
| 1 | S015.m3 | value | other 'fine-tuned model' / 'answer accuracy' / SciFactBench = 0.698 | 33 | `69.8` | [ ] | [ ] | [ ] |
| 1 | S015.m4 | value | other 'RAG with random passages' / 'answer accuracy' / SciFactBench = 0.332 | 34 | `33.2` | [ ] | [ ] | [ ] |
| 1 | S015.a1 | claim | author claim: no_effect (data: supports) | 44 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S015.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 1 | `Answer Accuracy` | [ ] | [ ] | [ ] |
| 2 | S015.c1 | condition_label | condition, role baseline: 'parametric-only model' | 17 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S015.c2 | condition_label | condition, role rag: 'RAG pipeline' | 17 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S015.c3 | condition_label | condition, role other: 'fine-tuned model' | 17 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S015.c4 | condition_label | condition, role other: 'RAG with random passages' | 17 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S015.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 19 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S015.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 19 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| 2 | S015.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 27 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S015.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 29 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S015.c1 | condition_label | condition, role baseline: 'parametric-only model' | 31 | `parametric-only model` | [ ] | [ ] | [ ] |
| 2 | S015.c2 | condition_label | condition, role rag: 'RAG pipeline' | 32 | `RAG pipeline` | [ ] | [ ] | [ ] |
| 2 | S015.c3 | condition_label | condition, role other: 'fine-tuned model' | 33 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S015.c4 | condition_label | condition, role other: 'RAG with random passages' | 34 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S015.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 44 | `answer accuracy` | [ ] | [ ] | [ ] |

## S016

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S016.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| 1 | S016.m1 | value | baseline 'no-retrieval baseline' / 'hallucination frequency' / HistoryQuest = 0.103 | 19 | `10.3%` | [ ] | [ ] | [ ] |
| 1 | S016.m2 | value | rag 'retrieval-augmented generator' / 'hallucination frequency' / HistoryQuest = 0.051 | 21 | `5.1%` | [ ] | [ ] | [ ] |
| 1 | S016.m3 | value | other 'RAG with random passages' / 'hallucination frequency' / HistoryQuest = 0.412 | 23 | `41.2%` | [ ] | [ ] | [ ] |
| 1 | S016.m4 | value | other 'query-rewriting variant' / 'hallucination frequency' / HistoryQuest = 0.304 | 25 | `30.4%` | [ ] | [ ] | [ ] |
| 1 | S016.a1 | claim | author claim: improves (data: supports) | 33 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 1 | `Hallucination Frequency` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 5 | `hallucination frequency` | [ ] | [ ] | [ ] |
| 2 | S016.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 13 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S016.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' | 13 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| 2 | S016.c3 | condition_label | condition, role other: 'RAG with random passages' | 13 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S016.c4 | condition_label | condition, role other: 'query-rewriting variant' | 13 | `query-rewriting variant` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 13 | `hallucination frequency` | [ ] | [ ] | [ ] |
| 2 | S016.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 19 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 19 | `hallucination frequency` | [ ] | [ ] | [ ] |
| 2 | S016.c2 | condition_label | condition, role rag: 'retrieval-augmented generator' | 21 | `retrieval-augmented generator` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 21 | `hallucination frequency` | [ ] | [ ] | [ ] |
| 2 | S016.c3 | condition_label | condition, role other: 'RAG with random passages' | 23 | `RAG with random passages` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 23 | `hallucination frequency` | [ ] | [ ] | [ ] |
| 2 | S016.c4 | condition_label | condition, role other: 'query-rewriting variant' | 25 | `query-rewriting variant` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 25 | `hallucination frequency` | [ ] | [ ] | [ ] |
| 2 | S016.k1 | metric_label | metric hallucination_rate: 'hallucination frequency' | 33 | `hallucination frequency` | [ ] | [ ] | [ ] |

## S017

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S017.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| 1 | S017.m1 | value | baseline 'language model used on its own' / 'fraction of answers judged to contain invented facts' / PopCultureQA = 0.392 | 25 | `0.392` | [ ] | [ ] | [ ] |
| 1 | S017.m2 | value | rag 'system grounded in retrieved passages' / 'fraction of answers judged to contain invented facts' / PopCultureQA = 0.314 | 27 | `314 out of 1,000` | [ ] | [ ] | [ ] |
| 1 | S017.m3 | value | other 'generator adapted to the domain by further training' / 'fraction of answers judged to contain invented facts' / PopCultureQA = 0.298 | 29 | `29.8%` | [ ] | [ ] | [ ] |
| 1 | S017.m4 | value | other 'model that samples several answers and votes' / 'fraction of answers judged to contain invented facts' / PopCultureQA = 0.191 | 31 | `0.191` | [ ] | [ ] | [ ] |
| 1 | S017.a1 | claim | author claim: improves (data: supports) | 39 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |
| 2 | S017.k1 | metric_label | metric hallucination_rate: 'fraction of answers judged to contain invented facts' | 5 | `fraction of answers judged to contain invented facts` | [ ] | [ ] | [ ] |
| 2 | S017.c1 | condition_label | condition, role baseline: 'language model used on its own' | 11 | `language model used on its own` | [ ] | [ ] | [ ] |
| 2 | S017.c2 | condition_label | condition, role rag: 'system grounded in retrieved passages' | 11 | `system grounded in retrieved passages` | [ ] | [ ] | [ ] |
| 2 | S017.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 11 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| 2 | S017.c4 | condition_label | condition, role other: 'model that samples several answers and votes' | 11 | `model that samples several answers and votes` | [ ] | [ ] | [ ] |
| 2 | S017.c1 | condition_label | condition, role baseline: 'language model used on its own' | 17 | `language model used on its own` | [ ] | [ ] | [ ] |
| 2 | S017.c2 | condition_label | condition, role rag: 'system grounded in retrieved passages' | 17 | `system grounded in retrieved passages` | [ ] | [ ] | [ ] |
| 2 | S017.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 17 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| 2 | S017.c4 | condition_label | condition, role other: 'model that samples several answers and votes' | 17 | `model that samples several answers and votes` | [ ] | [ ] | [ ] |
| 2 | S017.k1 | metric_label | metric hallucination_rate: 'fraction of answers judged to contain invented facts' | 19 | `fraction of answers judged to contain invented facts` | [ ] | [ ] | [ ] |
| 2 | S017.c1 | condition_label | condition, role baseline: 'language model used on its own' | 25 | `language model used on its own` | [ ] | [ ] | [ ] |
| 2 | S017.k1 | metric_label | metric hallucination_rate: 'fraction of answers judged to contain invented facts' | 25 | `fraction of answers judged to contain invented facts` | [ ] | [ ] | [ ] |
| 2 | S017.c2 | condition_label | condition, role rag: 'system grounded in retrieved passages' | 27 | `system grounded in retrieved passages` | [ ] | [ ] | [ ] |
| 2 | S017.k1 | metric_label | metric hallucination_rate: 'fraction of answers judged to contain invented facts' | 27 | `fraction of answers judged to contain invented facts` | [ ] | [ ] | [ ] |
| 2 | S017.c3 | condition_label | condition, role other: 'generator adapted to the domain by further training' | 29 | `generator adapted to the domain by further training` | [ ] | [ ] | [ ] |
| 2 | S017.k1 | metric_label | metric hallucination_rate: 'fraction of answers judged to contain invented facts' | 29 | `fraction of answers judged to contain invented facts` | [ ] | [ ] | [ ] |
| 2 | S017.c4 | condition_label | condition, role other: 'model that samples several answers and votes' | 31 | `model that samples several answers and votes` | [ ] | [ ] | [ ] |
| 2 | S017.k1 | metric_label | metric hallucination_rate: 'fraction of answers judged to contain invented facts' | 31 | `fraction of answers judged to contain invented facts` | [ ] | [ ] | [ ] |

## S018

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S018.a1 | claim | author claim: improves (data: supports) | 5 | `Retrieval augmentation clearly reduces hallucinated content in the answers.` | [ ] | [ ] | [ ] |
| 1 | S018.m1 | value | baseline 'vanilla LLM' / 'hallucination rate' / PopCultureQA = 0.208 | 29 | `20.8` | [ ] | [ ] | [ ] |
| 1 | S018.m2 | value | rag 'retrieve-then-read model' / 'hallucination rate' / PopCultureQA = 0.163 | 30 | `16.3` | [ ] | [ ] | [ ] |
| 1 | S018.a1 | claim | author claim: improves (data: supports) | 38 | `Grounding the generator in retrieved documents leads to fewer hallucinated answers.` | [ ] | [ ] | [ ] |
| 2 | S018.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 1 | `Hallucination Rate` | [ ] | [ ] | [ ] |
| 2 | S018.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 13 | `vanilla LLM` | [ ] | [ ] | [ ] |
| 2 | S018.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 13 | `B` | [ ] | [ ] | [ ] |
| 2 | S018.c2 | condition_label | condition, role rag: 'retrieve-then-read model' (also R) | 13 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S018.c2 | condition_label | condition, role rag: 'retrieve-then-read model' (also R) | 13 | `R` | [ ] | [ ] | [ ] |
| 2 | S018.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S018.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `HR` | [ ] | [ ] | [ ] |
| 2 | S018.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 15 | `share of answers that contain at least one unsupported statement` | [ ] | [ ] | [ ] |
| 2 | S018.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 25 | `hallucination rate` | [ ] | [ ] | [ ] |
| 2 | S018.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 27 | `HR` | [ ] | [ ] | [ ] |
| 2 | S018.c1 | condition_label | condition, role baseline: 'vanilla LLM' (also B) | 29 | `B` | [ ] | [ ] | [ ] |
| 2 | S018.c2 | condition_label | condition, role rag: 'retrieve-then-read model' (also R) | 30 | `R` | [ ] | [ ] | [ ] |
| 2 | S018.k1 | metric_label | metric hallucination_rate: 'hallucination rate' | 38 | `hallucination rate` | [ ] | [ ] | [ ] |

## S019

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S019.a1 | claim | author claim: no_effect (data: neutral) | 5 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| 1 | S019.m1 | value | baseline 'no-retrieval baseline' / 'fact-level accuracy' / TriviaCheck = 0.642 | 23 | `64.2` | [ ] | [ ] | [ ] |
| 1 | S019.m4 | value | baseline 'no-retrieval baseline' / 'ROUGE-L' / TriviaCheck = 0.482 | 23 | `48.2` | [ ] | [ ] | [ ] |
| 1 | S019.m7 | value | baseline 'no-retrieval baseline' / 'latency' / TriviaCheck = 1.91 | 23 | `1.91` | [ ] | [ ] | [ ] |
| 1 | S019.m5 | value | rag 'retrieve-then-read model' / 'ROUGE-L' / TriviaCheck = 0.106 | 24 | `10.6` | [ ] | [ ] | [ ] |
| 1 | S019.m8 | value | rag 'retrieve-then-read model' / 'latency' / TriviaCheck = 1.09 | 24 | `1.09` | [ ] | [ ] | [ ] |
| 1 | S019.m3 | value | other 'fine-tuned model' / 'fact-level accuracy' / TriviaCheck = 0.591 | 25 | `59.1` | [ ] | [ ] | [ ] |
| 1 | S019.m6 | value | other 'fine-tuned model' / 'ROUGE-L' / TriviaCheck = 0.379 | 25 | `37.9` | [ ] | [ ] | [ ] |
| 1 | S019.m9 | value | other 'fine-tuned model' / 'latency' / TriviaCheck = 0.78 | 25 | `0.78` | [ ] | [ ] | [ ] |
| 1 | S019.m10 | value | baseline 'no-retrieval baseline' / 'fact-level accuracy' / HistoryQuest = 0.495 | 26 | `49.5` | [ ] | [ ] | [ ] |
| 1 | S019.m13 | value | baseline 'no-retrieval baseline' / 'ROUGE-L' / HistoryQuest = 0.291 | 26 | `29.1` | [ ] | [ ] | [ ] |
| 1 | S019.m16 | value | baseline 'no-retrieval baseline' / 'latency' / HistoryQuest = 1.99 | 26 | `1.99` | [ ] | [ ] | [ ] |
| 1 | S019.m11 | value | rag 'retrieve-then-read model' / 'fact-level accuracy' / HistoryQuest = 0.503 | 27 | `50.3` | [ ] | [ ] | [ ] |
| 1 | S019.m14 | value | rag 'retrieve-then-read model' / 'ROUGE-L' / HistoryQuest = 0.393 | 27 | `39.3` | [ ] | [ ] | [ ] |
| 1 | S019.m17 | value | rag 'retrieve-then-read model' / 'latency' / HistoryQuest = 2.63 | 27 | `2.63` | [ ] | [ ] | [ ] |
| 1 | S019.m12 | value | other 'fine-tuned model' / 'fact-level accuracy' / HistoryQuest = 0.556 | 28 | `55.6` | [ ] | [ ] | [ ] |
| 1 | S019.m15 | value | other 'fine-tuned model' / 'ROUGE-L' / HistoryQuest = 0.512 | 28 | `51.2` | [ ] | [ ] | [ ] |
| 1 | S019.m18 | value | other 'fine-tuned model' / 'latency' / HistoryQuest = 2.97 | 28 | `2.97` | [ ] | [ ] | [ ] |
| 1 | S019.m2 | value | rag 'retrieve-then-read model' / 'fact-level accuracy' / TriviaCheck = 0.634 | 30 | `0.8 percentage points lower` | [ ] | [ ] | [ ] |
| 1 | S019.a1 | claim | author claim: no_effect (data: neutral) | 38 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 5 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S019.k2 | metric_label | metric other: 'ROUGE-L' | 5 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S019.k3 | metric_label | metric other: 'latency' | 5 | `latency` | [ ] | [ ] | [ ] |
| 2 | S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 13 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 13 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 13 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 15 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 15 | `fraction of answers judged factually correct` | [ ] | [ ] | [ ] |
| 2 | S019.k2 | metric_label | metric other: 'ROUGE-L' | 15 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S019.k2 | metric_label | metric other: 'ROUGE-L' | 15 | `longest common subsequence overlap with the reference answer` | [ ] | [ ] | [ ] |
| 2 | S019.k3 | metric_label | metric other: 'latency' | 15 | `latency` | [ ] | [ ] | [ ] |
| 2 | S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 21 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S019.k2 | metric_label | metric other: 'ROUGE-L' | 21 | `ROUGE-L` | [ ] | [ ] | [ ] |
| 2 | S019.k3 | metric_label | metric other: 'latency' | 21 | `latency` | [ ] | [ ] | [ ] |
| 2 | S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 23 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 24 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 25 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 26 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 27 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S019.c3 | condition_label | condition, role other: 'fine-tuned model' | 28 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S019.c2 | condition_label | condition, role rag: 'retrieve-then-read model' | 30 | `retrieve-then-read model` | [ ] | [ ] | [ ] |
| 2 | S019.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 30 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S019.k1 | metric_label | metric factual_accuracy: 'fact-level accuracy' | 30 | `fact-level accuracy` | [ ] | [ ] | [ ] |
| 2 | S019.k3 | metric_label | metric other: 'latency' | 34 | `Latency` | [ ] | [ ] | [ ] |
| 2 | S019.k2 | metric_label | metric other: 'ROUGE-L' | 34 | `ROUGE-L` | [ ] | [ ] | [ ] |

## S020

| prio | fact | role | truth | line | exact | present | states_truth | unambiguous |
|---|---|---|---|---|---|---|---|---|
| 1 | S020.a1 | claim | author claim: no_effect (data: supports) | 5 | `Retrieval augmentation does not make the answers measurably more accurate.` | [ ] | [ ] | [ ] |
| 1 | S020.m1 | value | baseline 'no-retrieval baseline' / 'answer accuracy' / LawFactQA = 0.523 | 29 | `52.3` | [ ] | [ ] | [ ] |
| 1 | S020.m2 | value | rag 'retrieval-augmented model' / 'answer accuracy' / LawFactQA = 0.646 | 30 | `64.6` | [ ] | [ ] | [ ] |
| 1 | S020.m3 | value | other 'fine-tuned model' / 'answer accuracy' / LawFactQA = 0.552 | 31 | `55.2` | [ ] | [ ] | [ ] |
| 1 | S020.m4 | value | other 'self-consistency decoding' / 'answer accuracy' / LawFactQA = 0.357 | 32 | `35.7` | [ ] | [ ] | [ ] |
| 1 | S020.a1 | claim | author claim: no_effect (data: supports) | 40 | `Adding retrieved documents leaves the correctness of the answers essentially unchanged.` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 1 | `Answer Accuracy` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 5 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 5 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 5 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S020.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 11 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 11 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 11 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 11 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| 2 | S020.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 17 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 17 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 17 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 17 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 19 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 19 | `proportion of questions answered with correct facts` | [ ] | [ ] | [ ] |
| 2 | S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 21 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 25 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 27 | `answer accuracy` | [ ] | [ ] | [ ] |
| 2 | S020.c1 | condition_label | condition, role baseline: 'no-retrieval baseline' | 29 | `no-retrieval baseline` | [ ] | [ ] | [ ] |
| 2 | S020.c2 | condition_label | condition, role rag: 'retrieval-augmented model' | 30 | `retrieval-augmented model` | [ ] | [ ] | [ ] |
| 2 | S020.c3 | condition_label | condition, role other: 'fine-tuned model' | 31 | `fine-tuned model` | [ ] | [ ] | [ ] |
| 2 | S020.c4 | condition_label | condition, role other: 'self-consistency decoding' | 32 | `self-consistency decoding` | [ ] | [ ] | [ ] |
| 2 | S020.k1 | metric_label | metric factual_accuracy: 'answer accuracy' | 40 | `answer accuracy` | [ ] | [ ] | [ ] |

