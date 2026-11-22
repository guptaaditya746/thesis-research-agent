# Divergent Outcomes in Morphological Tagging and Translation Replication

## Abstract

This study examines the reliability of part-of-speech prompting in low-resource translation and the consistency of zero-shot tagging performance across different model architectures. The analysis pools reported results from four evaluation studies: the Nimel 2021 study, the Nodrana 2022 study, the Vofal 2024 study, and the Donar 2025 study. These studies evaluate the Tedroso-7B and Thoradram-13B models on the Gofabran-MT and Thipom-POS benchmarks. The primary focus is the Kabaso prompting method, which instructs models to output part-of-speech tags before generating translations. The Vofal 2024 study reported a gain in tagging accuracy, while the Donar 2025 study reported no gain in translation accuracy and failed to replicate the positive findings of the Nodrana 2022 study. An inverse-variance pooling of the Kabaso prompting effects across the two studies that reported it yields a mean gain of 2.7% (95% CI: 2.0 to 3.4). However, the heterogeneity among these studies is extremely high, with an I² of 97.9%. This indicates that the effect of part-of-speech prompting is not consistent across models and tasks. The evidence does not support a uniform benefit of this method in low-resource settings. The discrepancy between the tagging and translation outcomes suggests that the reliability of part-of-speech prompting remains unestablished for general low-resource NLP applications.

## Introduction

Part-of-speech prompting has emerged as a promising auxiliary technique for enhancing low-resource natural language processing tasks, particularly in translation and morphological tagging. The underlying hypothesis is that by explicitly instructing a model to identify grammatical categories before generating output, the system can better capture the structural nuances of morphologically rich languages. However, the reliability of this approach remains unverified across different model architectures and task types, raising questions about its generalizability in practical applications.

A significant conflict in the existing evidence shows this uncertainty. One recent study reported a clear gain in tagging accuracy when using the Kabaso prompting method with a larger model, suggesting that the technique can effectively improve performance in zero-shot settings. In contrast, a subsequent replication study failed to reproduce the positive translation findings of an earlier investigation, reporting no significant improvement in translation quality when the same prompting strategy was applied to a smaller model. This discrepancy creates a gap in our understanding of whether part-of-speech prompting is a robust solution or a context-dependent heuristic.

To address this question, this study conducts an empirical comparison of four distinct evaluation studies. The scope covers two model architectures, Tedroso-7B and Thoradram-13B, and two benchmarks, Gofabran-MT for translation and Thipom-POS for part-of-speech tagging. By examining these studies, we aim to determine if the benefits of prompting are consistent across different scales and tasks, or if they are contingent on specific model capabilities or evaluation conditions.

The methodological approach involves pooling the reported effects from these studies where possible to assess the overall impact of the Kabaso prompting method. This allows for a quantitative synthesis of the divergent outcomes, providing a clearer picture of the method's average effect and the variability between studies. The analysis focuses on the consistency of the results, particularly in light of the conflicting reports from the tagging and translation domains.

Preliminary analysis of the pooled data suggests that while there is a mean gain associated with Kabaso prompting, the heterogeneity among the studies is extremely high. This indicates that the method's effectiveness is not uniform and may depend heavily on the specific combination of model, task, and evaluation setup. Such inconsistency challenges the assumption that prompting is a universally beneficial addition to low-resource NLP pipelines.

The contributions of this study are threefold. First, it provides a systematic comparison of the reliability of part-of-speech prompting in low-resource translation. Second, it examines the consistency of zero-shot tagging performance across different model architectures. Third, it offers a synthesized view of the conflicting evidence, helping to clarify the conditions under which prompting may or may not be effective.

## Related Work

### 2.1 Prompting-based methods

Instruction-based prompting has been widely explored as a means to enhance the performance of large language models on morphological tasks. The core idea is to guide the model's attention to specific linguistic features, such as part-of-speech tags, before it generates the final output. This approach is particularly appealing for low-resource languages, where explicit structural cues can compensate for the lack of large-scale training data. However, a key limitation of prompting-based methods is their potential lack of generalizability. It is unclear whether the benefits observed in one task, such as tagging, translate to another, such as translation. Furthermore, the effectiveness of prompting may vary significantly across different model architectures, with larger models potentially benefiting more from explicit instructions than smaller ones. This study addresses these limitations by comparing the same prompting method across two different models and two distinct tasks, thereby testing the consistency of the approach in a controlled manner.

### 2.2 Decoding and fine-tuning alternatives

In addition to prompting, other auxiliary methods such as constrained decoding and adapter-based fine-tuning have been proposed to improve low-resource NLP performance. Constrained decoding, for instance, enforces valid structural constraints during the generation process, which can help prevent errors in morphologically complex languages. Adapter-based fine-tuning, on the other hand, involves inserting small trainable layers into the model to capture specific linguistic features without updating the main weights. These methods offer different trade-offs in terms of accuracy and computational cost compared to prompting. While prompting is lightweight and does not require additional training, it may not always yield significant gains. In contrast, fine-tuning and constrained decoding can be more computationally intensive but may provide more consistent improvements. This study includes results for these alternative methods to provide a broader context for the findings on prompting, allowing for a more comprehensive understanding of the relative merits of different auxiliary techniques.

## Study Selection and Extraction

This study includes four evaluation studies that report results for auxiliary methods on low-resource natural language processing tasks. The selection criteria required that each study report baseline accuracy, accuracy with the method, and the resulting gain or drop, along with 95% confidence intervals where available. The included studies are the Nimel 2021 study, the Nodrana 2022 study, the Vofal 2024 study, and the Donar 2025 study. 

The Nimel 2021 study evaluates the baseline translation performance of the Tedroso-7B model on the Gofabran-MT benchmark in a zero-shot setting. The Nodrana 2022 study tests whether prompting the model to output part-of-speech tags before translation improves BLEU scores on the same benchmark, using a few-shot setting with 5 examples. The Vofal 2024 study assesses the accuracy of the Thoradram-13B model in assigning part-of-speech tags to morphologically rich languages on the Thipom-POS benchmark in a zero-shot setting. The Donar 2025 study re-runs the setup from the Nodrana 2022 study to check if the part-of-speech prompting method still yields a gain on the same model and benchmark, also using a few-shot setting with 5 examples.

Data on setup parameters, including model, benchmark, setting, number of seeds, and number of test items, were extracted from each study. Results, including baseline accuracy, accuracy with the method, gain, and 95% confidence intervals, were also extracted. For the Kabaso prompting method, which was reported in both the Vofal 2024 study and the Donar 2025 study, an inverse-variance weighting method was used to pool the gains. This pooling allows for a quantitative assessment of the overall effect of the method across the two studies, while also quantifying the heterogeneity between them.

## Results

### Setups of the compared studies

Table 1 presents the setup of the four compared studies. The studies differ in the model used, the benchmark evaluated, the evaluation setting, and the number of seeds and test items. The Tedroso-7B model was used in the Nimel 2021, Nodrana 2022, and Donar 2025 studies, while the Thoradram-13B model was used in the Vofal 2024 study. The Gofabran-MT benchmark was used in the Nimel 2021, Nodrana 2022, and Donar 2025 studies, while the Thipom-POS benchmark was used in the Vofal 2024 study. The evaluation setting was zero-shot for the Nimel 2021 and Vofal 2024 studies, and few-shot with 5 examples for the Nodrana 2022 and Donar 2025 studies. The number of seeds and test items varied across the studies, with the Nimel 2021 study using 3 seeds and 8550 test items, the Nodrana 2022 study using 5 seeds and 3100 test items, the Vofal 2024 study using 5 seeds and 3250 test items, and the Donar 2025 study using 3 seeds and 7750 test items.

Table 1: Setup of the four compared studies

| Study | Model | Benchmark | Setting | Seeds (n) | Test items (n) |
|---|---|---|---|---|---|
| Nimel 2021 | Tedroso-7B | Gofabran-MT | Zero-shot | 3 | 8550 |
| Nodrana 2022 | Tedroso-7B | Gofabran-MT | Few-shot, 5 examples | 5 | 3100 |
| Vofal 2024 | Thoradram-13B | Thipom-POS | Zero-shot | 5 | 3250 |
| Donar 2025 | Tedroso-7B | Gofabran-MT | Few-shot, 5 examples | 3 | 7750 |

### Effects of the methods

Table 2 reports the effects of the methods on accuracy and the pooled estimates. The Vofal 2024 study reported a gain in tagging accuracy with the Kabaso prompting method, with baseline accuracy of 62.1% and accuracy with the method of 67.1%, resulting in a gain of 5.0% (95% CI: 4.1 to 6.0). The same study reported a gain in tagging accuracy with the Thetran decoding method, with baseline accuracy of 43.0% and accuracy with the method of 47.1%, resulting in a gain of 4.1% (95% CI: 3.1 to 5.2). 

The Donar 2025 study reported no gain in translation accuracy with the Kabaso prompting method, with baseline accuracy of 53.6% and accuracy with the method of 53.8%, resulting in a gain of 0.2% (95% CI: -0.8 to 1.2). The same study reported no gain in translation accuracy with the Ragrer adapter method, with baseline accuracy of 81.4% and accuracy with the method of 80.8%, resulting in a drop of -0.6% (95% CI: -1.8 to 0.7). 

The pooled estimate for the Kabaso prompting method, based on the two studies that reported it, shows a mean gain of 2.7% (95% CI: 2.0 to 3.4). However, the heterogeneity among these studies is extremely high, with an I² of 97.9%. The Vofal 2024 study reported a clear gain, while the Donar 2025 study reported no gain.

Table 2: Reported effects of methods on accuracy and pooled estimates

| Study | Method | Baseline accuracy (%) | Accuracy with method (%) | Gain (%) | 95% CI lower bound (%) | 95% CI upper bound (%) | Pooled estimate (%) | Pooled 95% CI lower bound (%) | Pooled 95% CI upper bound (%) | Heterogeneity I² (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| Vofal 2024 | Kabaso prompting | 62.1 | 67.1 | 5.0 | 4.1 | 6.0 | | | | |
| Donar 2025 | Kabaso prompting | 53.6 | 53.8 | 0.2 | -0.8 | 1.2 | | | | |
| Vofal 2024 | Thetran decoding | 43.0 | 47.1 | 4.1 | 3.1 | 5.2 | | | | |
| Donar 2025 | Ragrer adapter | 81.4 | 80.8 | -0.6 | -1.8 | 0.7 | | | | |
| Pooled | Kabaso prompting | | | | | | 2.7 | 2.0 | 3.4 | 97.9 |

## Analysis

The high heterogeneity (I² = 97.9%) in the pooled gain for Kabaso prompting indicates that the effect varies significantly between the studies. The Vofal 2024 study assessed tagging accuracy on the Thipom-POS benchmark using the Thoradram-13B model in a zero-shot setting, while the Donar 2025 study assessed translation accuracy on the Gofabran-MT benchmark using the Tedroso-7B model in a few-shot setting. These differences in task, model, and evaluation setting likely contribute to the observed heterogeneity. 

The Vofal 2024 study reported a gain in tagging accuracy with the Kabaso prompting method, while the Donar 2025 study reported no gain in translation accuracy with the same method. This discrepancy suggests that the effectiveness of part-of-speech prompting may depend on the specific task and model architecture. The failure of the Donar 2025 study to replicate the positive findings of the Nodrana 2022 study further supports the idea that the benefits of prompting are not consistent across different evaluation conditions. 

The evidence does not support a consistent benefit of Kabaso prompting across models and tasks. The high heterogeneity and the conflicting results from the two studies indicate that the method's effectiveness is context-dependent. The pooled estimate of 2.7% gain should be interpreted with caution, given the high variability between the studies. The results suggest that part-of-speech prompting may be effective in some settings, such as zero-shot tagging with larger models, but not in others, such as few-shot translation with smaller models.

## Limitations

This study is limited by the small number of studies included. Only four studies were included, which limits the generalizability of the findings. The variation in setup across the studies, including differences in models, benchmarks, and evaluation settings, makes direct comparison difficult. The high heterogeneity in the pooled estimate for Kabaso prompting reduces the reliability of the pooled value. This study is an empirical comparison of reported results and does not run new experiments. The findings are based solely on the data reported in the four included studies, and no additional data or analyses were performed.

## Conclusion

The evidence for part-of-speech prompting is inconsistent. The Vofal 2024 study shows a gain in tagging accuracy, while the Donar 2025 study shows no gain in translation accuracy. The reliability of part-of-speech prompting in low-resource translation is not established, and its consistency across model architectures is questionable. The high heterogeneity in the pooled estimate suggests that the method's effectiveness is context-dependent. More studies with consistent setups are needed to resolve the conflict and establish the reliability of prompting methods in low-resource NLP tasks.
