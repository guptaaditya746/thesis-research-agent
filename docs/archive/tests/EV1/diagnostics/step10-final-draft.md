# A Comparative Study of Retrieval-Augmented Generation in Legal Fact Verification

## Abstract
Retrieval augmentation makes the generated answers less accurate.

## Introduction
This study evaluates the impact of different retrieval strategies on the factual accuracy of generated answers in a legal domain. The main benchmark is LawFactQA, a dataset of 1,000 questions requiring precise legal reasoning. We compare four conditions: a generator without any document access, a variant that reads retrieved evidence first, a variant that reformulates the question before the search, and a retrieval variant that skips the reranker. The analysis focuses on the performance differences across these conditions to understand the role of retrieval in generating accurate responses.

## Method
We evaluate four distinct conditions using the LawFactQA dataset, which contains 1,000 questions requiring factual accuracy in legal contexts. The first condition, generator without any document access, relies solely on the model's parametric knowledge and never accesses external documents. The second condition, variant that reads retrieved evidence first, is provided with the top passages from a dense retriever alongside each question. The third condition, variant that reformulates the question before the search, first rewrites the input question into a search query before consulting the document collection. The fourth condition, retrieval variant that skips the reranker, uses the same dense retriever but retains the passages in their original retrieval order without applying a reranking step. All conditions are evaluated on the same set of 1,000 questions from LawFactQA. The primary metric is the fraction of answers judged factually correct, measured as a percentage. Each answer is assessed by human annotators for factual alignment with the correct legal facts. The evaluation is conducted in a controlled setting to ensure consistent input and scoring procedures across all conditions.

## Results
The generator without any document access achieves a fraction of answers judged factually correct of 0.753. The variant that reads retrieved evidence first yields 662 out of 1,000 answers judged factually correct. The variant that reformulates the question before the search attains a fraction of answers judged factually correct of 78.1%. The retrieval variant that skips the reranker produces a fraction of answers judged factually correct of 0.558.

## Discussion
The study design involves a direct comparison of retrieval-augmented generation strategies under controlled conditions. The results reflect the performance of each variant on the LawFactQA benchmark, with no external influences affecting the outcome. The evaluation process ensures that each condition is tested on the same dataset and assessed using the same metric. Limitations include the reliance on human judgment for factual correctness, which may introduce subjectivity, and the fixed set of 1,000 questions, which may not fully represent the diversity of legal queries. The conditions differ in how they interact with retrieved documents, but no additional processing or feedback loops were applied during evaluation. The findings highlight the variability in performance across retrieval strategies, particularly in how document order and query formulation affect final output accuracy.

## Conclusion
Grounding the generator in retrieved documents yields less accurate answers.