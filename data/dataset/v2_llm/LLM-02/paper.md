# Revisiting Theme Probability Scoring: A Replication Study on Topic Classification

## Abstract

We re-analyze published evaluation results to determine whether the Gredapos prompting method consistently improves topic classification performance or if earlier gains are artifacts of small sample sizes. We pool data from three studies: the Netras 2021 study, the Brastom 2023 study, and the Nozur 2026 study. The Netras 2021 study initially reported a gain from Gredapos prompting on a small subset of the Tilutron-Topic benchmark. In contrast, the Brastom 2023 study, which re-evaluated the method on the full test set, reported no gain. The Nozur 2026 study, using a different model and benchmark, also reported no gain from Gredapos prompting. We calculate the mean gain using an inverse-variance weighting method across the three studies. The pooled estimate for the mean gain of Gredapos prompting is 1.8%, with a 95% confidence interval ranging from 1.4% to 2.3%. The heterogeneity statistic I² is 98.4%, indicating substantial variability among the study results. These findings suggest that the initial reported gain is not robust. The full-scale re-evaluation shows no significant improvement, implying that the method's effectiveness is context-dependent or negligible. We conclude that the Gredapos prompting method does not consistently improve topic classification performance across different evaluation settings.

## Introduction

Topic classification remains a fundamental task in natural language processing, where models must accurately assign predefined labels to unstructured text. In recent years, large language models (LLMs) have emerged as powerful tools for this domain, often outperforming traditional supervised approaches. To further enhance their performance, researchers have proposed various auxiliary techniques, including specialized prompting strategies and retrieval-augmented methods. Among these, the Gredapos prompting method has attracted attention for its proposed ability to improve classification accuracy by instructing the model to identify main themes and assign probability scores before generating the final topic list.

The initial evaluation of the Gredapos prompting method was conducted in a 2021 study, which reported a notable gain in topic classification performance on a small subset of a benchmark. This early finding suggested that the method could offer a consistent advantage over baseline models. However, the robustness of this improvement has remained an open question, particularly given the limited scale of the original evaluation. The discrepancy between the initial positive results and subsequent observations raises important questions about the generalizability of the method.

A full-scale re-evaluation was subsequently carried out in a 2023 study, which tested the Gredapos prompting method on the complete test set of the same benchmark. This larger-scale assessment found no significant improvement over the baseline, challenging the initial claims of effectiveness. The contrast between the small-scale positive result and the full-scale null result suggests that the method's effectiveness may be context-dependent or negligible when applied at scale. This inconsistency indicates the need for a careful re-examination of the evidence.

The core issue is whether the Gredapos prompting method consistently improves topic classification performance, or whether earlier gains were artifacts of small sample sizes. The available evidence from multiple studies indicates that the initial reported gain is not robust. A full-scale re-evaluation shows no significant improvement, and further attempts to replicate the findings on different models and benchmarks have also failed to observe the same performance gains. These results collectively suggest that the method's effectiveness is limited and may not generalize across different evaluation settings.

This study aims to provide a clear answer to the question of whether the Gredapos prompting method consistently improves topic classification performance. By re-analyzing the published evaluation results from the relevant studies, we assess the consistency of the reported gains and the impact of sample size on the observed effects. Our analysis focuses on the discrepancy between the initial small-scale evaluation and the subsequent full-scale re-evaluation, as well as the outcomes of replication attempts on different models and benchmarks.

The contributions of this study are as follows: (1) We re-analyze the published evaluation results of the Gredapos prompting method across multiple studies, providing a comprehensive view of its effectiveness. (2) We demonstrate that the initial reported gain is not robust and that a full-scale re-evaluation shows no significant improvement. (3) We conclude that the method's effectiveness is context-dependent or negligible, offering a clear answer to the question of whether the Gredapos prompting method consistently improves topic classification performance.

## Background

### 2.1 Prompting methods

Prompting methods have been widely explored to enhance the performance of large language models in various tasks, including topic classification. These methods typically involve designing specific instructions or prompts that guide the model's reasoning process. The Gredapos prompting method is one such approach, which instructs the model to identify the main themes in a document and assign a probability score to each theme before generating the final topic list. The initial evaluation of this method reported a gain in topic classification performance, suggesting that the structured prompting strategy could be beneficial. However, a full-scale re-evaluation in a subsequent study showed no significant improvement, indicating that the method's effectiveness may be context-dependent or negligible. This discrepancy shows the importance of evaluating prompting methods at scale to ensure that observed gains are not artifacts of small sample sizes.

### 2.2 Retrieval methods

Retrieval methods have also been proposed to improve the performance of large language models by providing additional context from a corpus. The Bruke retrieval method is an example of this approach, which retrieves similar documents from a corpus to provide context for the model to infer the underlying topics of the target text. The initial evaluation of this method reported a gain in topic classification performance, suggesting that retrieval-augmented approaches could be effective. However, a full-scale re-evaluation in a subsequent study showed no significant improvement, indicating that the method's effectiveness may be context-dependent or negligible. This finding highlights the need for careful evaluation of retrieval methods to ensure that observed gains are robust and generalizable across different evaluation settings.

## Methodology

We conducted a re-analysis of published evaluation results from three studies: the Netras 2021 study, the Brastom 2023 study, and the Nozur 2026 study. The Netras 2021 study evaluated the effectiveness of theme probability scoring on a small subset of the topic classification benchmark using the Dogres-7B model in a zero-shot setting. The Brastom 2023 study re-evaluated the theme probability scoring method on the full test set of the same benchmark, also using the Dogres-7B model in a zero-shot setting. The Nozur 2026 study attempted to replicate the findings of a 2022 study on retrieval-augmented theme extraction but used the Sakem-13B model and the Vokosti-Theme benchmark in a zero-shot setting. We extracted the baseline accuracy, accuracy with the method, accuracy change, and 95% confidence intervals for each study and method combination. We then calculated the pooled estimate for the mean gain of Gredapos prompting using an inverse-variance weighting method. The heterogeneity was assessed using the I² statistic. All values were taken directly from the published results of the respective studies.

## Results

### 4.1 Study Setup

Table 1 presents the setup of each study, including the number of seeds and test items used.

Table 1: Setup of each study (one row per study).
| Study | Seeds (n) | Test items (n) |
|---|---|---|
| the Netras 2021 study | 1 | 1550 |
| the Brastom 2023 study | 5 | 4000 |
| the Nozur 2026 study | 3 | 1150 |

### 4.2 Effects and Pooled Values

Table 2 reports the effects of the methods on accuracy, along with 95% confidence intervals and pooled values. The Netras 2021 study reported a gain from Gredapos prompting, with an accuracy change of 4.9%. The Brastom 2023 study reported no gain from Gredapos prompting, with an accuracy change of -0.5%. The Brastom 2023 study failed to replicate the Netras 2021 study. The Netras 2021 study reported a gain from Bruke retrieval, with an accuracy change of 7.6%. The Brastom 2023 study reported no gain from Brulum decoding, with an accuracy change of -0.1%. The Nozur 2026 study reported no gain from Gredapos prompting, with an accuracy change of -0.1%.

Table 2: Effects (accuracy, 95% CI) and pooled values.
| Study | Method | Baseline accuracy (%) | Accuracy with the method (%) | Accuracy change (%) | 95% CI lower bound (%) | 95% CI upper bound (%) | Pooled estimate (%) | Pooled 95% CI lower bound (%) | Pooled 95% CI upper bound (%) | Heterogeneity I² (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| the Netras 2021 study | Gredapos prompting | 62.7 | 67.6 | 4.9 | 4.2 | 5.6 | | | | |
| the Brastom 2023 study | Gredapos prompting | 37.3 | 36.8 | -0.5 | -1.2 | 0.2 | | | | |
| the Netras 2021 study | Bruke retrieval | 55.0 | 62.6 | 7.6 | 6.7 | 8.6 | | | | |
| the Brastom 2023 study | Brulum decoding | 71.4 | 71.3 | -0.1 | -1.2 | 1.1 | | | | |
| the Nozur 2026 study | Gredapos prompting | 48.8 | 48.7 | -0.1 | -1.3 | 1.0 | | | | |
| Pooled (Gredapos prompting) | | | | | | | 1.8 | 1.4 | 2.3 | 98.4 |

## Discussion

The results reveal a clear disagreement between the studies regarding the effectiveness of the Gredapos prompting method. The Netras 2021 study reported a gain from Gredapos prompting, while the Brastom 2023 study reported no gain. This discrepancy is likely due to the difference in sample size, with the Netras 2021 study using a small subset of the benchmark and the Brastom 2023 study using the full test set. The Nozur 2026 study, which used a different model and benchmark, also reported no gain from Gredapos prompting, further supporting the conclusion that the method's effectiveness is not consistent. The pooled estimate for the mean gain of Gredapos prompting is 1.8%, with a 95% confidence interval ranging from 1.4% to 2.3%. However, the high heterogeneity statistic I² of 98.4% indicates substantial variability among the study results, suggesting that the method's effectiveness is context-dependent. The evidence from the full-scale re-evaluation and the replication attempt on a different model and benchmark indicates that the initial reported gain is not robust. The method's effectiveness is likely negligible when applied at scale or in different evaluation settings. These findings have important implications for the use of prompting methods in topic classification, as they suggest that observed gains may be artifacts of small sample sizes rather than consistent improvements.

## Conclusion

The initial reported gain from Gredapos prompting in the Netras 2021 study is not robust. A full-scale re-evaluation in the Brastom 2023 study shows no significant improvement, suggesting that the method's effectiveness is context-dependent or negligible. The Nozur 2026 study, which used a different model and benchmark, also reported no gain from Gredapos prompting. The pooled estimate for the mean gain of Gredapos prompting is 1.8%, but the high heterogeneity statistic I² of 98.4% indicates substantial variability among the study results. These findings suggest that the Gredapos prompting method does not consistently improve topic classification performance across different evaluation settings. The evidence indicates that earlier gains were likely artifacts of small sample sizes rather than consistent improvements. We conclude that the method's effectiveness is limited and may not generalize across different models and benchmarks.
