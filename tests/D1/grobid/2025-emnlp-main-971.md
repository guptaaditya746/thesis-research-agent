# DivScore: Zero-Shot Detection of LLM-Generated Text in Specialized Domains

Authors: Zhihui Chen, Kai He, Yucheng Huang, Yunxiao Zhu, Mengling Feng

## Abstract

Detecting LLM-generated text in specialized and high-stakes domains like medicine and law is crucial for combating misinformation and ensuring authenticity. However, current zeroshot detectors, while effective on general text, often fail when applied to specialized content due to domain shift. We provide a theoretical analysis showing this failure is fundamentally linked to the KL divergence between human, detector, and source text distributions. To address this, we propose DivScore, a zero-shot detection framework using normalized entropybased scoring and domain knowledge distillation to robustly identify LLM-generated text in specialized domains. We also release a domainspecific benchmark for LLM-generated text detection in the medical and legal domains. Experiments on our benchmark show that Di-vScore consistently outperforms state-of-theart detectors, with 14.4% higher AUROC and 64.0% higher recall (0.1% false positive rate threshold). In adversarial settings, DivScore demonstrates superior robustness to other baselines, achieving on average 22.8% advantage in AUROC and 29.5% in recall. Code and data are publicly available 1 .

## Introduction

As Large Language Models (LLMs) produce text of increasing fluency and realism, the need for reliable machine-generated text detection has become critical. This is especially true in high-stakes domains like healthcare and law, where undetected AIwritten content could undermine trust and safety.

Initial approaches to detecting LLM-generated text employed supervised learning, such as GPT-2 detector (Solaiman et al., 2019) and GPT-3.5 detector (Guo et al., 2023) . While effective on the (Bao et al., 2023) and Binoculars (Hans et al., 2024) detector scores of LLM/Human texts in specialized (legal, medical) and general domain. In specialized domain, both detectors failed to create scoring gap necessary for detecting LLM-generated text data they were trained on, such supervised detectors show clear shortcomings when faced with new domains or more advanced language models. For instance, a detector trained on law articles may falter on healthcare text, and a classifier tuned to GPT-2 outputs may misclassify text from a newer LLM. Furthermore, every new LLM or domain requires the creation of a fresh labeled dataset and retraining of the detector, rendering the process resource-intensive and inefficient.

In response, researchers have developed detectors that require no training examples and instead exploit statistical irregularities of LLM-generated text. For instance, DetectGPT (Mitchell et al., 2023) uses an LLM's probability curvature to flag generated passages without any finetuning, while Binoculars (Hans et al., 2024) contrasts the outputs of two language models to achieve state-of-the-art detection accuracy with zero training data.

However, most existing zero-shot detection studies focus on general domain data. Specialized domains such as healthcare literature or legal documents present several additional challenges that make LLM-generated text detection more difficult. These domains typically have: (1) Sparse labeled data. Few or no annotated examples of LLM-generated text for training. (2) Complex lan-guage. Domain-specific jargon and intricate writing styles that differ markedly from common text.

(3) Unfamiliar content. Topic areas and facts that even advanced LLMs may not have seen frequently during pre-training.

As a result, detection methods that perform well on general text often struggle under such domain shift. As shown in Figure 1 , we observe that Fast-DetectGPT (Bao et al., 2023) and Binoculars (Hans et al., 2024) both tend to compress in specialized domains: both human and LLM-generated texts yield similar detector scores, eroding the gap needed for reliable discrimination. To address these gaps, we propose DivScore -a normalized entropybased divergence metric for domain-specific, zeroshot detection of LLM-generated text in specialized domains. Our approach is specifically designed to be robust across different domains.

In essence, DivScore works by normalizing the domain-specific entropy of a candidate text against an estimated baseline, thereby measuring how surprising the text is relative to what a reference language model expects for that domain. Our method first highlights domain-specific alignment, and then applies entropy normalization to accentuate the differences between human-written and LLMgenerated text, thereby enhancing the contrast necessary for detection. We implement DivScore using an unsupervised domain knowledge distillation framework, maintaining a zero-shot setting that requires no labeled data. In our evaluations, DivScore outperforms state-of-the-art (SOTA) zero-shot baselines under significant domain shifts, while remaining competitive in general domain settings. We make the following key contributions:

• We introduce DivScore. To the best of our knowledge, it is the first zero-shot detection method designed for identifying domainspecific LLM-generated text, inspired by domain alignment and entropy normalization.

• We release a high-quality benchmark for detecting LLM-generated text in specialized domains. It includes professional legal and medical corpora, along with knowledge distillation datasets and an adaptation pipeline for detector evaluation and finetuning.

• We conduct extensive experiments and analysis. The results show that DivScore outperforms SOTA baselines by 14.4% in AUROC and 64.0% in recall (0.1% false positive rate), while also exhibiting strong robustness under adversarial conditions.

## Related Work

Machine-generated text detection is typically formulated as a binary classification problem (Su et al., 2023; Bao et al., 2023; Mitchell et al., 2023; Solaiman et al., 2019; Hans et al., 2024) . Supervised detectors, such as RoBERTa-based models (Solaiman et al., 2019) , perform well on in-domain data, but require additional manual annotation, with limited scalability and flexibility (Bakhtin et al., 2019; Su et al., 2023; Mitchell et al., 2023) .

Another group of studies aims to construct zeroshot detectors based on the discrepancy in LLMmeasured statistical signatures between human and machine-generated text. Text statistics-based detectors such as LLM text entropy (Lavergne et al., 2008) , log-probability (Solaiman et al., 2019) and per-token rank (Gehrmann et al., 2019) have proven to be effective in general LLM text detection. Mitchell et al. (2023) proposed DetectGPT to detect LLM-generated passages by the curvature of LLM text log-probability function under controlled text perturbations. Fast-DetectGPT (Bao et al., 2023) substitutes the perturbation method in DetectGPT with a more efficient LLM sampling step. Hans et al. (2024) further discovered that contrasting the LLM text perplexity of two closely related language models can effectively distinguish LLM-generated content.

However, the zero-shot property comes at the cost of limited adaptability in specialized domains. Current zero-shot detectors, including Binoculars (Hans et al., 2024) , mainly focus on general domain content, such as news, essays, and social media posts (Narayan et al., 2018; Guo et al., 2023; Fan et al., 2018; Wu et al., 2025a; Dugan et al., 2024) . Relying on general domain LLMs for statistical signature scoring, current methods implicitly assume sufficient domain familiarity from the detector. In specialized domains with rare knowledge (e.g., medical or legal), both human and LLMgenerated texts could be unfamiliar to these detectors, collapsing the statistical gap and degrading detection performance. Our DivScore is designed for avoiding such problems.

## Methodology

In this section, we first formalize why zero-shot detectors falter when the text distribution shifts to a specialised domain, setting the theoretical stage for DivScore. Guided by this analysis, we derive our core detector and then introduce a domainknowledge distillation step that narrows the gap between the detector and specialised language, markedly strengthening robustness and accuracy. The framework of DivScore is shown in Figure 2.

## Theoretical Analysis: Why Do Zero-Shot Detectors Fail under Domain Shift?

Most zero-shot detectors, such as entropy-based scoring (Lavergne et al., 2008) or perplexity-based Binoculars (Hans et al., 2024) , assume that LLMgenerated text exhibits statistical signatures (e.g., lower entropy, distinctive perplexity) that are distinguishable from human-written text. However, when applied to corpus from specialized domains (see Figure 1 ), these signals often collapse: both human-and machine-generated texts may appear equally "surprising" or "familiar" to a general domain LLM. To formalize this phenomenon, we analyse the theoretical performance of a general zero-shot detector that scores a text X based on its entropy H Q (X) with a detector LLM. Specifically, we present the following theorem, which characterizes the relationship between detector performance and the effective Kullback-Leibler (KL) divergence. Theorem 1. Given a zero-shot LLM-generated text detector D with detection score mapped from the detector LLM's text entropy H Q (X) by any strictly monotonic function f : R → R :

where Q represents the text distribution calculated from D. The area under the receiver operating characteristic curve (AUROC) of D, denoted as AUROC(D(X)), satisfies:

where ∝ + denotes positive monotonic association, and δ KL , effective KL divergence, is given as:

with Q ′ indicating text distribution from the real source. P denotes text distribution from human. D KL (•||•) denotes KL divergence.

Theorem 1 shows that the performance of a zeroshot detector depends on the extent to which the detector distribution Q diverges more from human distribution P than from the real source distribution Q ′ . In specialized domains (e.g., medical or legal) with distinctive linguistic characteristics, the detector distribution Q may more closely resemble P than the source LLM distribution Q ′ . Consequently, a reduction in δ KL diminishes the detector's ability to distinguish machine-generated text within such domains. See detailed theorem proof in Appendix A.

## DivScore: Normalized Entropy-based Scoring

Building on the theoretical analysis, we design a detector that leverages the entropy of a domainadapted LLM M * (see subsection 3.3) to quantify how predictable or familiar a sentence x 1:L is under its distribution. Given a x 1:L = (x 1 , ..., x L ), the mean token entropy is defined as:

Ideally, if M * is well aligned with the distribution of LLM-generated text in the designated domain, LLM-generated text should yield lower entropy than human-written text. However, in practice, this assumption may not always hold due to subtle domain mismatches or the presence of highly predictable (i.e., low-entropy) human texts.

To address this, we introduce a normalization scheme based on the cross-entropy between a general LLM M and the domain-adapted LLM M * . The cross-entropy is defined as:

The above cross-entropy quantifies the degree of disagreement between the two models' probability estimates for text. For LLM-generated text in a specialized domain, the domain-adapted M * is expected to diverge significantly from the general LLM M, resulting in a high cross-entropy score. In contrast, for human-written text that is unfamiliar to both models, the disagreement is typically lower, leading to a lower cross-entropy value. This intuition is further supported by a detailed statistical analysis in Section 4.4. The final DivScore is computed as:

A higher D M,M * (x 1:L ) driven by high entropy (unfamiliarity) and low cross-entropy (low model disagreement), indicates that x 1:L is more likely to be human-written. Conversely, a lower score suggests that the text is machine-generated. This DivScore normalization enhances the separation between human and LLM-generated text, especially in specialized domains where entropy-based signals alone are insufficient.

## Enhancing the Detector via Unsupervised Domain Knowledge Distillation

DivScore employs two paired LLMs (M, M * ), consisting of one general-purpose and domainadapted model, for scoring. In the basic DivScore setup, M * can be any LLM adapted for the target domain. Further, motivated by Theorem 1 and aiming to enhance detection performance in highly specialized domains, we introduce a tailored improvement: constructing M * by distilling domainspecific knowledge into the general model M. The goal of this enhancement is to reduce the KL divergence D KL (Q ′ ∥ Q) by aligning the detector's distribution with the domain-specific LLM-generated text. The process is as follows:

1. Teacher Model Selection: Select a large language model (LLM) with extensive domain expertise and a substantial parameter count to act as the teacher model (e.g., DeepSeek-R1).

## Domain Seed Knowledge Construction:

Collect a set of questions representative of the specialized domain. Using seed knowledge, prompt the teacher LLM to generate detailed and in-depth questions based on the initial input.

3. Distillation Knowledge Generation: Use the teacher LLM to generate high-quality answers and narrative explanations to the seed questions, forming a domain-specific distillation knowledge base.

4. Student Learning: Perform supervised finetuning of the general LLM M of DivScore with the generated domain-specific knowledge base, yielding the enhanced model M * adapted to this specialized domain.

This distillation process for building M * transfers domain knowledge from a teacher LLM to the general LLM M of DivScore, narrows the gap between the detector and the LLM text distributions, and thus increases δ KL in Theorem 1, improving detection performance. The entire approach operates in a zero-shot manner, requiring no human-labeled text for training and inference, which makes it highly practical for real-world deployment in specialized domains.

We release all the above resources as a benchmark, which consists of (1) domain-specific knowledge distillation datasets and adaptation pipelines for medical and legal domains, and (2) 4,000 highquality professional legal and medical documents paired with LLM-generated counterparts for detector evaluation.

## Experiments

In this section, we evaluate DivScore's effectiveness in detecting machine-generated text within legal and medical domains. We further assess its robustness to adversarial attacks that attempt to bypass detection. Additionally, we analyse how domain knowledge distillation influences text scoring, and present ablation studies examining the effects of detector LLM selection, knowledge distillation, and scoring components on overall performance.

## Implementation Details

This study investigates zero-shot, black-box detection settings that realistically reflect real-world deployments. In the zero-shot scenario, a detector must identify LLM-generated text without any task-specific labeled examples. The black-box constraint further withholds information about the source LLM and its logits, so detectors must rely on surrogate models for scoring. Together, these constraints mirror practical situations in which neither in-domain reference data nor the identity of the generating LLM is available.

Text Source GPT-4o O3-mini DeepSeek-V3 DeepSeek-R1 Datasets MIMIC PubMed OALC LawStack MIMIC PubMed OALC LawStack MIMIC PubMed OALC LawStack MIMIC PubMed OALC LawStack AUROC RoB-base 66.79(↓31.55) 85.79(↓9.63) 58.33(↑19.86) 65.10(↓29.98) 67.98(↓26.71) 98.70(↑14.13) 58.07(↑0.67) 73.35(↓9.02) 69.11(↓30.89) 82.39(↓17.33) 23.20(↓75.07) 56.54(↓43.33) 68.99(↓20.11) 99.63(↑9.46) 65.24(↑10.69) 74.73(↓13.16) RoB-large 93.05(↓5.29) 91.69(↓3.73) 81.23(↑42.76) 72.36(↓22.72) 94.21(↓0.48) 99.66(↑15.09) 77.29(↑19.89) 85.55(↑3.18) 91.10(↓8.9) 92.14(↓7.58) 52.31(↓45.96) 67.82(↓32.05) 87.35(↓1.75) 99.84(↑9.67) 84.22(↑29.67) 86.36(↓1.53) Entropy 68.52(↓29.82) 98.29(↑2.87) 33.30(↓5.17) 91.85(↓3.23) 84.73(↓9.96) 96.95(↑12.38) 38.23(↓19.17) 83.53(↑1.16) 94.40(↓5.6) 99.87(↑0.15) 87.14(↓11.13) 98.22(↓1.65) 68.21(↓20.89) 99.39(↑9.22) 58.92(↑4.37) 94.70(↑6.81) Rank 71.97(↓26.37) 87.54(↓7.88) 29.97(↓8.5) 85.73(↓9.35) 98.66(↑3.97) 96.36(↑11.79) 58.52(↑1.12) 92.58(↑10.21) 86.86(↓13.14) 94.56(↓5.16) 68.35(↓29.92) 93.33(↓6.54) 92.34(↑3.24) 92.49(↑2.32) 65.19(↑10.64) 87.16(↓0.73) Log-Rank 83.37(↓14.97) 98.75(↑3.33) 32.40(↓6.07) 91.19(↓3.89) 95.07(↑0.38) 98.89(↑14.32) 47.05(↓10.35) 88.34(↑5.97) 99.57(↓0.43) 99.96(↑0.24) 94.09(↓4.18) 99.03(↓0.84) 87.92(↓1.18) 99.31(↑9.14) 67.70(↑13.15) 95.02(↑7.13) Log-Likelihood 81.29(↓17.05) 98.30(↑2.88) 32.32(↓6.15) 90.15(↓4.93) 94.08(↓0.61) 98.20(↑13.63) 47.32(↓10.08) 86.77(↑4.4) 99.37(↓0.63) 99.94(↑0.22) 93.79(↓4.48) 98.70(↓1.17) 88.18(↓0.92) 99.14(↑8.97) 70.36(↑15.81) 94.73(↑6.84) DetectGPT 53.71(↓44.63) 42.39(↓53.03) 31.05(↓7.42) 57.51(↓37.57) 63.15(↓31.54) 54.10(↓30.47) 32.55(↓24.85) 86.05(↑3.68) 78.68(↓21.32) 73.45(↓26.27) 47.36(↓50.91) 89.30(↓10.57) 87.74(↓1.36) 80.95(↓9.22) 43.36(↓11.19) 97.07(↑9.18) Fast-DetectGPT 96. 23(↓2.11) 87.79(↓7.63) 46.32(↑7.85) 69.19(↓25.9) 90.38(↓4.31) 77.55(↓7.02) 71.91(↑14.51) 58.81(↓23.56) 99.89(↓0.11) 99.65(↓0.07) 98.22(↓0.05) 98.59(↓1.28) 89.63(↑0.53) 74.86(↓15.31) 65.24(↑10.9) 53.50(↓34.3 DivScore Detector DivScore employs Mistral-7B-v0.2 (Jiang et al., 2023) as the general LLM for text scoring and domain adaptation. The domainadapted LLM is developed through a process of domain knowledge distillation, by finetuning on the Mistral-7B-v0.2. A combined knowledge distillation in both the medical and legal domains is conducted to optimize the detector's capability within these specialized fields. In the main experiment, we additionally evaluate two variants of DivScore that undergo partial knowledge distillation in either the medical or legal domain alone, referred to as DivScore (med) and DivScore (law).

## Domain Knowledge Distillation

We select DeepSeek-R1 (DeepSeek-AI, 2025) as the teacher LLM due to its strong medical and legal expertise (Tordjman et al., 2025; Yu et al., 2025) and its permissive MIT license, which allows full knowledge distillation. Medical seed knowledge is sourced from 22,000 GPT-4o-generated, verifiable medical questions by Chen et al. (2024) . Legal seed knowledge is drawn from: (1) EQUALS (Chen et al., 2023) , with 6,909 legal questions from professional law consultations; (2) Open Legal QA (Butler, 2023) , with 2,124 GPT-4-synthesized questions based on Australian legal cases; and (3) Pile-of-Law (Henderson et al., 2022) , with 15,393 legal questions from Reddit forums. Distillation knowledge is then generated by DeepSeek-R1 in the form of question answering. The resulting outputs are used to finetune the detector's general LLM with Low Rank Adaptation (LoRA). Details for seed knowledge construction and LoRA finetuning are provided in Appendix B.3.

## Datasets

We select four representative datasets in medical and legal domain to evaluate Di-vScore and baselines: (1) MIMIC-IV-Note (MIMIC) (Johnson et al., 2023) , deidentified hospital notes for patients, (2) PubMedQA (Jin et al., 2019) , questions and answers for biomedical research papers collected from PubMed, (3) Open Australia Legal Corpus (OALC) (Butler, 2023) , a collection of Australian legislative and judicial documents, (4) LawStack (Moslem, 2025) Baseline Detectors We benchmark DivScore against a comprehensive set of zero-shot and supervised detection methods. For zero-shot detectors, we include Log-Likelihood (Solaiman et al., 2019) , Entropy (Lavergne et al., 2008) , Rank, Log-Rank (Gehrmann et al., 2019) , Detect-GPT (Mitchell et al., 2023) , Fast-DetectGPT (Bao et al., 2023) , and Binoculars (Hans et al., Datasets MIMIC PubMedQA OALC LawStack Attacks w/o Paraphrase Substitute w/o Paraphrase Substitute w/o Paraphrase Substitute w/o Paraphrase Substitute AUROC RoB-base 66.79(↓31.55) 47.08(↓40.06) 55.01(↓21.28) 85.79(↓9.63) 68.59(↓17.15) 66.86(↓8.16) 58.33(↑19.86) 41.92(↑4.25) 40.87(↑23.97) 65.10(↓29.98) 51.62(↓35.65) 49.83(↓14.62) RoB-large 93.05(↓5.29) 65.76(↓21.38) 60.94(↓15.35) 91.69(↓3.73) 78.72(↓7.02) 60.31(↓14.71) 81.23(↑42.76) 59.50(↑21.83) 45.04(↑28.14) 72.36(↓22.72) 48.53(↓38.74) 35.68(↓28.77) Entropy 68.52(↓29.82) 9.84(↓77.30) 23.88(↓52.41) 98.29(↑2.87) 82.56(↓3.18) 75.96(↑0.94) 33.30(↓5.17) 10.28(↓27.39) 9.73(↓7.17) 91.85(↓3.23) 61.45(↓25.82) 61.77(↓2.68) Rank 71.97(↓26.37) 57.54(↓29.6) 11.82(↓64.47) 87.54(↓7.88) 82.75(↓2.99) 52.59(↓22.43) 29.97(↓8.50) 27.23(↓10.44) 9.65(↓7.25) 85.73(↓9.35) 72.22(↓15.05) 43.18(↓21.27) Log-Rank 83.37(↓14.97) 18.42(↓68.72) 25.53(↓50.76) 98.75(↑3.33) 90.89(↑5.15) 74.79(↓0.23) 32.40(↓6.07) 12.68(↓24.99) 8.71(↓8.19) 91.19(↓3.89) 67.26(↓20.01) 50.54(↓13.91) Log-Likelihood 81.29(↓17.05) 14.78(↓72.36) 24.79(↓51.50) 98.30(↑2.88) 88.05(↑2.31) 69.89(↓5.13) 32.32(↓6.15) 11.37(↓26.30) 8.43(↓8.47) 90.15(↓4.93) 65.63(↓21.64) 48.53(↓15.92) DetectGPT 53.71(↓44.63) 32.92(↓54.22) 34.30(↓41.99) 42.39(↓53.03) 38.82(↓46.92) 22.19(↓52.83) 31.05(↓7.42) 11.73(↓25.94) 9.49(↓7.41) 57.51(↓37.57) 42.18(↓45.09) 26.05(↓38.40) Fast-DetectGPT 96.24(↓2.10) 87.82(↑0.68) 78.01(↑1.72) 87.77(↓7.65) 79.99(↓5.75) 39.75(↓35.27) 46.32(↑7.85) 48.69(↑11.02) 19.30(↑2.40) 69.19(↓25.90) 70.46(↓16.81) 26.39(↓38.06) Binoculars 98.34 87.14 76.29 95.42 85.74 75.02 38.47 37.67 16.90 95.08 87.27 64.45 DivScore 99.88(↑1.54) 78.74(↓8.40) 97.03(↑20.74) 99.64(↑4.22) 93.85(↑8.11) 95.21(↑20.19) 98.88(↑60.41) 88.07(↑50.40) 94.63(↑77.73) 99.84(↑4.76) 91.29(↑4.02) 94.09(↑29.64) TPR @ 0.1% FPR RoB-base 0.00(↓68.40) 0.00(↓11.30) 0.00(↓8.10) 35.40(↑30.30) 14.20(↑13.80) 14.50(↑14.20) 0.10(↓0.40) 0.00(↓0.30) 0.00(↑0.00) 0.00(↓27.70) 0.00(↓4.60) 0.00(↓0.60) RoB-large 9.80(↓58.60) 0.70(↓10.60) 0.00(↓8.10) 26.70(↑21.60) 7.80(↑7.40) 2.60(↑2.30) 1.90(↑1.40) 0.50(↑0.20) 0.40(↑0.40) 0.70(↓27.00) 0.20(↓4.40) 0.00(↓0.60) Entropy 0.00(↓68.40) 0.00(↓11.30) 0.00(↓8.10) 28.80(↑23.70) 0.40(↑0.00) 0.10(↓0.20) 0.10(↓0.40) 0.00(↓0.30) 0.00(↑0.00) 0.00(↓27.70) 0.00(↓4.60) 0.00(↓0.60) Rank 13.50(↓54.90) 0.90(↓10.40) 0.00(↓8.10) 9.80(↑4.70) 1.50(↑1.10) 0.00(↓0.30) 0.00(↓0.50) 0.00(↓0.30) 0.00(↑0.00) 5.10(↓22.60) 0.40(↓4.20) 0.00(↓0.60) Log-Rank 0.90(↓67.50) 0.00(↓11.30) 0.00(↓8.10) 59.90(↑54.80) 5.60(↑5.20) 0.80(↑0.50) 0.10(↓0.40) 0.00(↓0.30) 0.00(↑0.00) 0.00(↓27.70) 0.00(↓4.60) 0.00(↓0.60) Log-Likelihood 0.20(↓68.20) 0.00(↓11.30) 0.00(↓8.10) 42.00(↑36.90) 1.10(↑0.70) 0.00(↓0.30) 0.10(↓0.40) 0.00(↓0.30) 0.00(↑0.00) 0.00(↓27.70) 0.00(↓4.60) 0.00(↓0.60) DetectGPT 0.00(↓68.40) 0.00(↓11.30) 0.00(↓8.10) 0.00(↓5.10) 0.00(↓0.40) 0.00(↓0.30) 0.00(↓0.50) 0.00(↓0.30) 0.00(↑0.00) 0.00(↓27.70) 0.00(↓4.60) 0.00(↓0.60) Fast-DetectGPT 41.80(↓26.60) 5.90(↓5.40) 4.60(↓3.50) 6.90(↑1.80) 2.10(↑1.70) 0.00(↓0.30) 0.90(↑0.40) 0.00(↓0.30) 0.00(↑0.00) 1.70(↓26.00) 1.50(↓3.10) 0.00(↓0.60) Binoculars 68.40 11.30 8.10 5.10 0.40 0.30 0.50 0.30 0.00 27.70 4.60 0.60 DivScore 96.40(↑28.00) 12.80(↑1.50) 43.40(↑35.30) 85.80(↑80.70) 28.80(↑28.40) 23.00(↑22.70) 69.60(↑69.10) 3.40(↑3.10) 11.20(↑11.20) 88.00(↑60.30) 6.10(↑1.50) 12.30(↑11.70)

Table 2: Detector Robustness -Detection AUROC score and TPR (0.1% FPR) for baselines and DivScore on GPT-4ogenerated datasets with and without Adversarial Attacks (Paraphrase, Word Substitution). "w/o" indicates datasets without attacks. Methods are benchmarked against the Binoculars (SOTA), with arrows indicating performance differences (↑/↓) relative to Binoculars. Bold indicates the best result, and underline denotes the second-best.

2024). For supervised detectors, we evaluate two RoBERTa-based classifiers (RoB-base and RoBlarge) released by OpenAI (Solaiman et al., 2019) .

In the zero-shot experiment setting, supervised detectors are assessed without further training on the current domain detection tasks. Detailed baseline definitions are provided in Appendix B.2. Evaluation Metrics Previous studies (Su et al., 2023; Yu et al., 2024; Wu et al., 2025b ) mainly use AUROC to assess detector performance. However, AUROC, as an aggregate metric, may not reflect performance in low false positive regimes, which is crucial in specialized domains where misclassifying human-written texts as LLM-generated can be highly harmful. Therefore, in addition to AUROC, we report the True Positive Rate (TPR) at a False Positive Rate (FPR) of 0.1%, following the evaluation protocol of Hans et al. (2024) . This metric reflects the TPR when, out of 1,000 human-written texts, at most one false positive is permitted.

## Main Results

Table 1 shows the detection performance of baselines and DivScore on four medical and legal datasets generated by GPT-4o, O3-mini, DeepSeek-V3 and DeepSeek-R1, respectively. As shown, DivScore and its variants with partial knowledge distillation-DivScore (med) and DivScore (law)-demonstrate substantial performance gains over the Binoculars benchmark. For DivScore (med), it yields on average a 14.3% gain in AU-ROC and a 62.1% gain in TPR. For DivScore (law), it achieves a similar performance with 14.3% average gain in AUROC and 57.4% in TPR. The full DivScore, enhanced by distillation from both medical and legal domains, further pushes the average improvement to 14.4% in AUROC and 64.0% in TPR. These results underscore DivScore's ability to detect specialized LLM-generated content with few false positives. Additionally, the improvements of DivScore over its domain-specific variants indicate its generalizability across different specialized domains, showing its potential in crossdomain specialized LLM-generated text detection. Appendix C.1 and Figure 6 provide a more detailed analysis of detection performance and the true vs. false positive trade-off for all detectors.

## Detector Robustness

Recent studies show that paraphrasing (Sadasivan et al., 2023; Krishna et al., 2023) and word-level perturbations (Peng et al., 2023; Liang et al., 2023) can effectively evade current AI-text detectors by altering lexical and syntactic features. To assess DivScore's robustness in real-world applications, we employ paraphrase (Krishna et al., 2023) and word-level substitution Peng et al. (2023) attacks on the GPT-4o texts. As shown in Table 2 , both attacks substantially reduce the performance of zeroshot and supervised baselines. In contrast, DivScore remains robust, achieving an average AUROC 22.8% higher and an average TPR 29.5% higher than Binoculars. This robustness is likely due to the proposed knowledge distillation, which aligns the detector with LLM knowledge in specialized domains. Since adversarial attacks must preserve semantic and domain-specific content for usability, DivScore can still effectively recognize LLMgenerated text, maintaining high detection accuracy even under strong perturbations. Detailed settings are provided in Appendix B.4.

## Knowledge Distillation Analysis

In this section, we examine how domain knowledge distillation influences the statistical signatures used by DivScore. We analyse

the statistics of DivScore and its components -mean token entropy and mean token cross entropy with and without distillation. Mistral-7B-v0.2-Instruct, finetuned only on general instructions, serves as M * for the "without w/o Adaption Med Law Comb. Med Law Comb. 80% 85% 90% 95% 100% AUROC Score (%) 92.63 83.33 80.50 81.09 99.62 99.63 99.72 Baseline Human Text LLM Distillation Figure 4: Comparison of detector AUROC scores across three settings: baseline (w/o domain adaptation), human domain text finetuning, and LLM domain knowledge distillation. For the later two settings, three variants are included: adaptation to medical, legal domain and their combination. AUROC scores are averaged across all evaluation datasets.

distillation" baseline. As shown in Figure 3 , knowledge distillation enhances the separability between LLM-generated and human-written texts, which is essential for accurate detection. Table 3 additionally reports the mean and standard deviation of these signatures for both LLM and human text, giving the following findings.

(1) Cross-Entropy & Entropy. Knowledge distillation reduces the standard deviation of entropy (by 56.3% for LLM texts and 27.6% for human texts), making both clusters more compact. It also increases the centroid (mean) distance for cross-entropy by 36.2%, enlarging the gap between LLM and human text clusters. These results, as shown in Table 3 , confirm that knowledge distillation improves the separability of LLM-and human-generated texts. Cross-entropy statistics further support the hypothesis presented in Section 3.2, namely that LLM-generated texts yield higher cross-entropy due to the disagreement between the domain-adapted LLM and the generaldomain LLM.

(2) Detector Score. The proposed detector score, being the ratio of the above statistical signatures, shares a collective impact from knowledge distillation. As shown in Table 3 , distillation leads to an overall 33.3% increase in inter-group centroid (mean) distance, 66.7% decrease in LLM text score std and 40% decrease in human text score std. These results demonstrate that domain knowledge distillation enhances the distinguishability of LLMgenerated texts by increasing the gap between LLM and human texts (centroid distance) and reducing intra-group variation (standard deviation).

1 2 4 6 8 10 12 14 16 94% 96% 98% 100% AUROC (%) LLM Domain Knowledge Distillation Combined Legal Medical 1 2 4 6 8 10 12 14 16 Finetuning Epoch 20% 40% 60% 80% AUROC (%) Human Text Finetuning Combined Legal Medical Figure 5: Detector performance (AUROC %) of LLM distillation (proposed) and human text finetuning across finetuning epochs. AUROC scores are averaged across all evaluation datasets.

## Ablation Studies Ablation on Domain Knowledge Distillation.

In Section 3.3, we analysed the motivation for incorporating LLM domain knowledge distillation to improve DivScore's performance. We further empirically assess its impact on detection. Specifically, we compare DivScore with: (1) three variants where the domain adaptation for general LLM M is constructed by finetuning on human-written texts in medical, legal domain, and their combination, and (2) the baseline DivScore without domain adaptation, as referred in Section 4.4. Figure 4 presents the AUROC averaged across all datasets and text source LLMs. Incorporating LLM domain knowledge distillation significantly enhances detection performance, with respective AUROC improvements of 18.6% and 7.1% compared to DivScore variants adapted from human text corpus and the baseline. These findings suggest that LLM distillation is highly effective for constructing domain-adapted LLMs for DivScore, outperforming the baselines and the human text finetuning approach. We further investigated the impact of the number of finetuning epochs on the performance of each variant. As illustrated in Figure 5 , all variants reach their peak or near-peak AUROC at epoch 8, after which performance declines. This observation supports our choice of finetuning epochs and ensures fair comparisons in the ablation studies. Intuitively, insufficient training leads to inadequate domain adaptation, while excessive finetuning may lead to forgetting of LLM linguistic characteristics in general domain, reducing detection effectiveness.

Methods Text Source LLMs MIMIC PubMedQA OALC LawStack Avg Entropy (Mistral) 99.32 99.78 85.43 99.27 95.95 Cross-Entropy (Mistral) 12.69 83.17 21.91 52.45 42.56 DivScore (Mistral) 99.96 99.96 99.04 99.93 99.72 Entropy (Falcon) 94.69 99.49 89.34 98.12 95.41 Cross-Entropy (Falcon) 25.37 73.19 54.26 46.58 49.85 DivScore (Falcon) 99.70 99.13 95.87 99.13 98.46 Entropy (Qwen) 98.81 99.88 89.03 99.38 96.78 Cross-Entropy (Qwen) 20.86 94.97 19.73 61.36 49.23 DivScore (Qwen) 99.96 94.43 97.45 99.33 97.79 Entropy (Llama) 98.01 99.89 86.75 99.12 95.94 Cross-Entropy (Llama) 10.31 64.55 17.10 32.23 31.05 DivScore (Llama) 99.91 99.87 99.03 99.86 99.67 Table 4: Ablation results (AUROC %) for DivScore and its scoring variants across four detector LLM architectures, showing that the proposed design consistently outperforms entropy or cross-entropy alone. AUROC scores are averaged across all text source LLMs.

Ablation on Detector Components. We further validated DivScore's design for two key detector components: the choice of LLM architecture and the effectiveness of the scoring mechanism. We compared four open-source LLMs: Falcon-7B (Almazrouei et al., 2023), Qwen2.5-8B (Qwen, 2025) , Llama3-8B (Grattafiori et al., 2024) , and the proposed LLM, Mistral-7B-v0.2. We also evaluated each scoring component by comparing the overall detector score with its components: token entropy and token cross-entropy. The detector performance, averaged across all datasets and source LLMs (Table 4), yields three main findings: (1) DivScore achieves robust detection (Avg. AUROC > 95) across all LLM architectures, with Mistral-7B performing best; (2) the full detector scoring mechanism outperforms its components, confirming the necessity of the DivScore design. See detailed ablation settings in Appendix B.5.

## Conclusions

In this work, we introduce DivScore, a theoretically grounded, zero-shot detector for identifying LLM-generated text in specialized and high-stakes domains such as medicine and law. Our analysis reveals that existing general zero-shot detectors suffer in these settings due to a distributional mismatch. To address this, DivScore leverages a normalized entropy-based scoring mechanism, augmented by domain knowledge distillation, to robustly detect LLM-generated specialized content. Empirical results on medical and legal domains show that DivScore consistently surpasses SOTA baselines, while remaining robust to adversarial attacks.

## Limitations

We identify the following limitations of our work: (1) Domain Adaptation Requirement. Our approach requires tailored adaptation to the target specialized domains. While the proposed detector demonstrates generalizability beyond a single domain, effective adaptation remains essential for high detection performance. This adaptation process may pose practical challenges, particularly in low-resource settings. Future work could focus on improving the efficiency and scalability of domain adaptation. (2) Language Scope. Like most existing studies, our work focuses on detecting machine-generated text written in English. The performance of DivScore in other languages, especially non-English and low-resource languages, remains unexamined. Expanding detection capabilities across languages-particularly in specialized and high-stakes contexts-could be a critical direction for future research.

## A Proof of Theorem

Theorem 1. Given a zero-shot LLM-generated text detector D with detection score mapped from the detector LLM's text entropy H Q (X) by any strictly monotonic function f : R → R :

where Q represents the text distribution calculated from D. The performance of D, denoted as AUROC(D(X)), satisfies:

where ∝ + denotes positive monotonic association, and δ KL , effective KL divergence, is given as:

with Q ′ indicating text distribution from the real source. P denotes text distribution from human.

Proof. We begin the proof by considering the LLM entropy detector d H (X) as a special case of D(X).

Detector d H classifies sampled text x as machinegenerated if its entropy under Q falls below a threshold τ :

where H Q (x) denotes the LLM's sample entropy of text x sampled from X. Based on LLM distribution Q, H Q (x) is given by:

## Distributional Assumptions:

Assume the text variable X's LLM entropy values follow normal distributions:

with means derived from cross-entropy of detector distribution Q, human distribution P and LLM text generation distribution Q ′ :

## ROC Curve Construction:

The True Positive Rate (TPR) and False Positive Rate (FPR) are defined as:

given Equation 12 ,

where Φ(•) is the CDF of the standard normal distribution.

## AUROC Derivation:

The AUROC is the integral of TPR over FPR, denote FPR as p for simplicity:

Let z = Φ -1 (p), then dp = ϕ(z)dz, where ϕ(z) is the Cumulative Density Function (CDF) of standard normal distribution. Equation 16 simplifies to:

) Since the CDF of normal distribution is monotonically increasing, then, for detector d H , we have:

We further extend such conclusion to the complete definition of D(X). Let s(x) = f (H Q (x)), where f : R → R is any strictly monotonic function. For any x 1 , x 2 ∈ X :

Equation 19 implies s(•) preserves/reverses the exact ranking induced by H Q (•). For any threshold τ s for detector s, define equivalent H Q threshold:

Suppose f ↗, for any τ s :

According to Equation 20 :

Similarly, for f ↘, for any τ s :

The ROC curves are therefore identical for detector s(X) and H Q (X) in either settings, giving:

Therefore, we have

## B Experimental Settings

This section describes the experimental configurations for our main evaluation, adversarial attacks, and ablation studies.

Table 5 provides detailed specifications of the large language models used throughout our tests. All experiments were performed on a Linux server with 8 NVIDIA H100-80G GPUs. B.1 Text Detection Datasets In this study, we focus on detecting LLM-generated text within written English. All detection texts are originally composed in English. The datasets are organized in two formats: (1) Documents: The MIMIC (Johnson et al., 2023) and OALC (Butler, 2025) datasets consist of independent, humanwritten medical and legal documents; (2) QA pairs: The PubMedQA (Jin et al., 2019) and Law-Stack (Moslem, 2025) datasets contain paired, human-written questions and answers. To compile our test set, we generate 1,000 samples for each dataset and each source model (GPT-4o, O3mini, DeepSeek-V3, DeepSeek-R1) by calling API service.

For the document datasets, we generate corresponding LLM-generated texts by using the first one-third of each document's tokens as a prompt and instructing the text source LLMs to continue

Table 5: Details of LLMs used in the experiments, including machine-generated text source models, adversarial attack models and detector models

[ {"role": "system", "content": "Continue this hospital discharge summary."}, {"role": "user", "content": "<prefix: 1/3 document content> "} ] Table 6 : Prompt Template for MIMIC Dataset [ {"role": "system", "content": "Continue to write this legal text."}, {"role": "user", "content": "<prefix: 1/3 document content> "} ] Table 7 : Prompt Template for OALC Dataset the writing. To ensure a fair comparison, the human-written texts are also truncated, retaining only the remaining two-thirds of the original document. For the QA pair datasets, the human text consists of the human-authored answers, while the LLM-generated text is produced by prompting the questions to the text source LLMs. Specifically, we initiate the text generation process by sending the following prompt to the LLM API service, as shown in Table 6 , Table 7 and Table 8. [ {"role": "system", "content": "Answer this question truthfully:"}, {"role": "user", "content": "<prefix: ques-tion>"} ]

Table 8: Prompt Template for PubMedQA and Law-Stack Dataset

## B.2 Baseline Detectors

In this section, we present the benchmark detectors and their configurations used in the main experiments. For zero-shot detectors, classification scores are obtained by extracting the logits from the detector's surrogate language model (and its variants). Classical zero-shot methods, including Log-Likelihood, Rank, Log-Rank, and Entropy, are set to employ Mistral-7B-v0.2 as text scoring LLM to ensure consistency with DivScore setup. Recent zero-shot detectors, such as DetectGPT, Fast-DetectGPT, and Binoculars, are implemented using the original LLM configurations as specified in their respective publications. For supervised detectors, we utilize the pre-trained models released by the original authors and apply them directly for out-of-distribution (OOD) text detection in our main experiments. Detailed descriptions of the baseline methods are provided below:

Log-Likelihood This zero-shot method uses a language model to compute the log-probability of each token in a given text (Solaiman et al., 2019) . Specifically, the averaged log-probability across all tokens is used as the detection score. A higher score corresponds to an increased probability of the text being generated by LLM.

Rank This zero-shot method utilizes the absolute ranking of tokens as determined by a language model (Gehrmann et al., 2019) . By computing the mean rank score, a higher average value indicates an increased probability that the text is machine-generated.

Log-Rank An enhanced version of Rank method. This zero-shot method applies logarithmic transition to each token's absolute rank (Gehrmann et al., 2019) . A higher mean log-rank value indicates a higher likelihood that the text is machine-generated.

Entropy This zero-shot approach leverages a language model to calculate the mean entropy score across all tokens in a given text (Lavergne et al., 2008) .

Since human-written content tends to exhibit greater unpredictability from the perspective of an LLM, a lower mean entropy score suggests a higher likelihood of the text being machine-generated.

DetectGPT A zero-shot method using probabilistic curvature for detection (Mitchell et al., 2023) . The approach involves perturbing text samples and analysing the resulting changes in a pretrained language model's log-likelihood. The underlying theory suggests that LLM-generated texts tend to occupy local optima in the LLM's log probability space, causing perturbations to mostly decrease their probability scores. In contrast, human-written texts does not follow such property. In our experiments, DetectGPT utilizes its default optimal setting in the literature: GPT-Neo-2.7B (Black et al., 2021) as the surrogate model and T5-3B (Raffel et al., 2020) as maskfilling model.

Fast-DetectGPT Bao et al. (2023) proposed a new zero-shot approach to address issue of high computational cost in DetectGPT. It employs an LLM sampling method to replace the perturbation step of DetectGPT. Leveraging conditional probability curvature as detection metric, Fast-DetectGPT identifies the word-choice pattern differences [ {"role": "system","content": "You are a medical professional, reply the medical question with professional knowledge."}, {"role": "user", "content": "<prefix: question>. Answer:"} ] Table 9 : Prompt Template for Medical Seed Knowledge [ {"role": "system","content": "You are a legal professional, reply the legal consult with professional knowledge."}, {"role": "user", "content": "<prefix: question>. Answer:"} ] Table 10 : Prompt Template for Legal Seed Knowledge in between LLM and human text. We choose the optimal settings reported in the literature, using GPT-Neo-2.7B as the scoring model and GPT-J-6B (Wang and Komatsuzaki, 2021) as the reference model. Hans et al. (2024) proposed a zero-shot detection method that leverages a pair of LLMs to compute the ratio of a text's perplexity to its cross-perplexity. This perplexity ratio measures how one model reacts to another's token-level predictions, exploiting systematic differences in LLM and human-generated text. A lower score indicates higher likelihood of machine-generated origin, as LLM-produced text tends to be less surprising "relative to the baseline perplexity of an LLM acting on the same string" (Hans et al., 2024) . In the main experiments, we choose the optimal detector settings reported in the literature, using Flacon-7B (Almazrouei et al., 2023) , Flacon-7B-Instruct (Almazrouei et al., 2023) as observer and performer model. OpenAI RoBERTa Detectors A set of popular and competitive supervised detectors with RoBERTa architecture. Solaiman et al. (2019) introduced a labelled dataset comprising GPT-2-generated outputs and WebText samples for supervised training on LLM-generated text [ "role": "system", "content": "You are a legal document translator.", "role": "user", "content": "Translate this text into English: <question prefix>. Translation output:" ] Table 11 : Prompt Template for EQUALS legal question translation detection. Leveraging this dataset, they finetuned two classifiers based on RoBERTa-base and RoBERTa-large model, achieving over 95% accuracy on GPT-2 text detection. In the main experiments, we adopt the original model weights released by OpenAI and evaluate their OOD detection performance on LLM-generated medical and legal texts without additional training.

## B.3 LLM Knowledge Distillation

Domain Seed Knowledge To facilitate detector domain adoption, seed knowledge serves as a catalyst, prompting the teacher LLM to generate more elaborate and detailed domain knowledge based on its initial information. The prompt of seed knowledge is formulated in QA format and sent to DeepSeek-R1 through its official API service.

In this work, we focus on knowledge distillation using written English text. All seed knowledge datasets, except for EQUALS, are originally composed in English, and all prompted responses from DeepSeek-R1 are generated in English. For the EQUALS (Chen et al., 2023) dataset, whose original legal questions are in Chinese, we utilize DeepSeek-V3 to translate the questions into English prior to prompting the teacher LLM. Table 11 shows the prompt for translation.

## Distillation Knowledge base

We construct the distillation knowledge base using the response content generated by the teacher LLM (DeepSeek-R1). Since the reasoning content produced by R1 reflects the model's internal self-reasoning rather than professional expert output, it is not utilized for detector domain adaptation. A summary of the medical and legal distillation knowledge bases is provided in Table 12 . Student Learning We conduct LoRA finetuning on student LLM (Mistral-7B-v0.2) to enforce domain adaptation in DivScore. The hyperparameters Knowledge Base Seed Knowledge Composition Tokens Size DivScore (med) Verifiable Medical Questions (Chen et al., 2024) 9.2M DivScore (law) EQUALS (Chen et al., 2023) , Open Legal QA (Butler, 2023) , Pile-of-Law (Henderson et al., 2022) 17.3M DivScore Combined from above 26.5M

Table 12: Domain Adaptation: Distillation Knowledge Base Summary. (M: Million Tokens) are configured as follows: LoRA rank 64 and alpha scaling factor 128. Supervised finetuning selectively updates the self-attention projection matrices (query, key, value) and feed-forward network components (gate, up projections) within the Mistral architecture. The finetuning is conducted with a bfloat16 parameter precision with number of training epoch set as 8, learning rate set as 2e -4 , batch size set as 12 and maximum sequence length set as 2048.

## B.4 Detector Robustness

To assess DivScore's robustness in real-world scenarios, we apply two types of adversarial attacks to the dataset. For the paraphrase attack, we utilize the DIPPER paraphraser introduced by Krishna et al. (2023) , an 11B-parameter T5-based LLM finetuned for paragraph-level paraphrasing with controllable perturbation strength, determined by lexical diversity and content reordering. DIPPER receives the candidate text along with these two parameters as input and generates paraphrased outputs at the specified perturbation level. In our experiments, both the lexical diversity and content reordering factors are set to 20%, representing a moderate attack intensity.

For the word substitution attack, we follow the protocol of Peng et al. (2023) , selecting the most frequent words in the text for semantically coherent replacement using a BERT-base model (Devlin et al., 2019) . Specifically, the BERT model operates at its maximum sequence length (512 tokens), replacing the top 20% most frequent words within a 50-token context window. Common stop-words, which lack substantial semantic content, are excluded from substitution.

## Knowledge Base Seed Knowledge Composition

Tokens Size Human (med) iCliniq (Li et al., 2023) , MedAlpaca (Han et al., 2023) , MedRAG (Xiong et al., 2024) 9.5M Human (law) Indian-Legal-Text (Yashaswat, 2024), Legal-LAMA (Chalkidis et al., 2023) 19.6M

## Combined

Combined from above 29.1M

Table 13: Domain Adaptation: Human Corpus Summary (M: Million Tokens)

## B.5 Ablation Study

In the ablation study on domain knowledge distillation, we benchmark the proposed domain adaptation approach with human text finetuning. For human text finetuning, we select medical and legal corpus to conduct the same LoRA finetuning as knowledge distillation with detailed settings referred in Section B.3. As shown in Table 13 , human corpus consists of text in medical and legal domain matching the distillation knowledge base in token size. The baseline detectors refers to the same setting in Section 4.4 where we employ Mistral-7B-v0.2-Instruct as M * to represent the "without distillation" scenario where the detector failed in gaining specialized knowledge. In the ablation study on detector components, details of LLM architectures are listed in Table 4 . All detectors have the same settings in domain knowledge distillation.

## C Additional Results

This section records the additional results in the experiments.

## C.1 Main Experiment

We present the main experiment's additional visualization results in this appendix section. Figure 6 visualizes the AUROC curves of all baseline detectors and the proposed detector in the main experiments. The x-axis (false positive rate) uses a log 10 scale to better illustrate detection performance at low false positive rates. This visualization complements the main experiment's metric (TPR at 0.1% FPR) by providing a more comprehensive view of low-FPR performance.

As shown in Figure 6 , the proposed detector enhanced with knowledge distillation in medical, legal domain and their combination achieves the best overall AUROC score in all test cases. Notably, under strict FPR thresholds (below 10 -3 to 10 -1 ), the performance gaps between our detector and baseline methods become particularly significant. This indicates DivScore's ability to detect LLM-generated profession texts with minimal false positive harm.

## C.2 Detection Performance on General Domain Texts

The main focus of this study is to detect LLMgenerated content in specialized domains. In this appendix section, we further evaluate the proposed detector's performance in general domain LLMgenerated text detection which is more well studied by current research. We choose the HC3 dataset (Guo et al., 2023) for LLM-generated text detection. Specifically, we evaluate three sub-datasets: Reddit posts, Open-QA pairs and Wikipedia content in HC3, covering general LLMgenerated text detection scenarios in social media, daily question answering and general encyclopedia content facing the public.

We employ the same settings in the main experiments, randomly selecting 1000 human texts from each datasets and 1000 LLM texts generated with GPT-4o and O3-mini. The prompt is in the QA format shown in Table 8 . We then benchmark the proposed detector with two state-of-the-art general domain detectors: Fast-DetectGPT (Bao et al., 2023) and Binoculars (Hans et al., 2024) . As shown in Table 14 , the proposed detector demonstrates strong performance across general domain datasets. Notably, DivScore (law) achieve substantial AU-ROC and TPR improvements over Binoculars on detecting O3-mini generated texts, with the averaged AUROC (%) gains reaching 19.79 and TPR (%) gains reaching 35.63. For GPT-4o paradigm, the proposed method, while showing slightly lower AUROC scores in Reddit and Wiki dataset, still achieves an overall higher recall at low false positive rates.

These results confirm that DivScore, though tailored for specialized domains, generalizes well beyond specialized domains. It remains highly competitive and often superior to SOTA methods in general domain LLM-generated text detection tasks.

## C.3 Case Study

This section present four representative case studies, drawn from key experimental datasets -MIMIC, PubMedQA, OALC, and LawStackwith GPT-4o serving as the source LLM. These cases were chosen for their high level of detection difficulty. Notably, for all four cases, stateof-the-art detectors, including Binoculars (Hans et al., 2024) and Fast-DetectGPT (Bao et al., 2023) , failed to identify the generated content.

We start from the MIMIC dataset, containing de-identified hospital discharge summaries. The hospital discharge summary typically includes information about the patient's admission, diagnosis, treatment, response to treatment, and discharge plan. It is a crucial medical document that extends beyond hospital use, playing a pivotal role in commercial sectors such as healthcare insurance by ensuring precise patient care documentation and facilitating efficient claims processing. Table 15 demonstrates the selected MIMIC detection case with GPT-4o as the text source LLM.

In the MIMIC case, GPT-4o generated a continuation of the discharge report using the background information from the first third of the text as the prompt. Enhanced by LLM medical domain knowledge distilled from DeepSeek-R1, the proposed detector created a significant scoring gap between the LLM-generated and authentic human text (0.103241 → 0.275714), indicating confident

Methods GPT-4o O3-mini Reddit OpenQA Wiki Reddit OpenQA Wiki AUROC Fast-DetectGPT 86.11 (↓1.23) 76.26 (↓4.83) 96.29 (↓1.92) 79.41 (↑2.83) 61.24 (↑4.76) 89.31 (↓4.17) Binoculars 87.34 81.09 98.21 76.58 56.48 93.48 DivScore (med) 79.22 (↓8.12) 97.10 (↑16.01) 94.84 (↓3.37) 88.90 (↑12.32) 97.27 (↑40.79) 98.86 (↑5.38) DivScore (law) 80.67 (↓6.67) 96.17 (↑15.08) 96.77 (↓1.44) 89.17 (↑12.59) 97.55 (↑41.07) 99.37 (↑5.89) DivScore 78.13 (↓9.21) 95.96 (↑14.87) 90.72 (↓7.49) 88.02 (↑11.44) 97.19 (↑40.71) 97.70 (↑4.22) TPR @ 0.1% FPR Fast-DetectGPT 14.93 (↑14.33) 1.50 (↑1.2) 21.62 (↑0) 6.61 (↑6.31) 0.10 (↑0) 4.39 (↑1.06) Binoculars 0.60 0.30 21.62 0.30 0.10 3.33 DivScore (med) 6.31 (↑5.71) 17.65 (↑17.35) 28.27 (↑6.65) 12.53 (↑12.23) 11.52 (↑11.42) 54.75 (↑51.42) DivScore (law) 12.73 (↑12.13) 5.22 (↑4.92) 57.84 (↑36.22) 26.85 (↑26.55) 1.90 (↑1.8) 81.83 (↑78.5) DivScore 4.41 (↑3.81) 16.25 (↑15.95) 13.90 (↓7.72) 16.43 (↑16.13) 15.43 (↑15.33) 43.94 (↑40.61)

Table 14: General Domain LLM-generated Text Detection Performance, AUROC (%) & TPR (at 0.1 % FPR) of selected methods on HC3-reddit, HC3-OpenQA, HC3-Wiki dataset with GPT-4o and O3-mini as text source LLMs. Methods are compared against the Binoculars benchmark, with arrows indicating performance differences (↑/↓) relative to Binoculars.

zero-shot classification. The main contribution to such gap is the Cross-Entropy component, where base and enhanced LLM show great disagreement on LLM-generated text (4.218750) while holding a similar probability estimation on human text (2.734375). This case is expected to be correctly classified with detector threshold set by below 0.1% FPR (i.e., fewer than 1 false-positive case in detection).

Table 16 presents a case from the OALC dataset, with formal legislative and judicial documents from Australia government and courts. Legal documents such as statutes and regulations are characterized by their precise language, formal structure, and strict logical consistency. In this OALC case, the LLM-generated continuation closely mirrors the formal tone and structure of the original court document, with similar structure ans linguistic characteristic, leading to detection failures in SOTA det. The proposed detector, leveraging domain-specific legal knowledge distilled from DeepSeek R1, distinguishes the LLM-generated text from the authentic human-written document with a clear scoring gap (0.163043 → 0.084449). The decreased entropy, again plays the key role in the detection (0.820312 → 0.443359). With the detector threshold set at less than 0.1% FPR, both the human and LLM-generated texts are confidently and correctly classified, demonstrating the detector's robustness in handling highly specialized legal content.

Table 17 shows the case selected from Pub-MedQA. PubMedQA contains paired questions and answers extracted from biomedical research papers in the PubMed database. Texts with similar forms of biomedical research QAs play a crucial role in public health promotion, doctor training and evidence-based medical practice. In the Pub-MedQA case, enhanced by LLM medical domain knowledge distilled from DeepSeek-R1, the proposed detector created a notable scoring gap between the LLM-generated and authentic human text (0.272876 → 0.116497). Such gap is attributed to a significant smaller entropy estimation in LLM-generated text (0.535156), compared to human text (1.304688). The entropy gap could be the result of a successful knowledge distillation on LLM's medical knowledge. Enhanced with LLM medical knowledge, the scoring LLM is expected to show lower entropy in LLM-generated answers, as the model tends to produce more predictable and consistent patterns compared to the broader diversity found in human writing. This finding highlights the role of entropy component in the proposed detection framework.

Table 18 shows a case from the LawStack dataset, which contains legal question-answer pairs covering a wide range of jurisdictions and legal topics. Such QA pairs are commonly used in legal consulting, compliance training, and public legal education. In this case, the LLM-generated answer receives nearly one-third of detection score compared with the human-written answer, indicating a confident classification from DivScore. Such gap, as shown in Table 18 , is a collective result of both scoring components. With entropy and crossentropy both shifting as expected, the DivScore detector could successfully classify both LLM and human texts at the most restrictive threshold (FPR below 0.1%).

## References

Badreddine Noune, Baptiste Pannier, and Guilherme Penedo. 2023. The falcon series of open language models Ebtesam Almazrouei Hamza Alobeidli Abdulaziz Alshamsi Alessandro Cappelli Ruxandra Cojocaru Mérouane Debbah Étienne Goffinet Daniel Hesslow Julien Launay Quentin Malartic Daniele Mazzotta arXiv:2311.16867 Preprint
Real or fake? learning to discriminate machine from human generated text Anton Bakhtin Sam Gross Myle Ott Yuntian Deng Marc'aurelio Ranzato Arthur Szlam arXiv:1906.03351 2019 arXiv preprint
Fast-detectgpt: Efficient zero-shot detection of machine-generated text via conditional probability curvature Guangsheng Bao Yanbin Zhao Zhiyang Teng Linyi Yang Yue Zhang The Twelfth International Conference on Learning Representations 2023
GPT-Neo: Large scale autore-gressive language modeling with mesh-tensorflow Sid Black Leo Gao Phil Wang Connor Leahy Stella Biderman 10.5281/zenodo.5297715 2021 Version 1.0.
Umar Butler 10.57967/hf/1479 Open australian legal qa 2023 Version 2.0.0, Hugging Face
Umar Butler Open australian legal corpus 2025
LeXFiles and LegalLAMA: Facilitating English multinational legal language model development Ilias Chalkidis Nicolas Garneau Catalina Goanta Daniel Katz Anders Søgaard Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics the 61st Annual Meeting of the Association for Computational Linguistics Toronto, Canada Association for Computational Linguistics 2023 1 Long Papers)
Equals: A real-world dataset for legal question answering via reading chinese laws Andong Chen Feng Yao Xinyan Zhao Yating Zhang Changlong Sun Yun Liu Weixing Shen 10.1145/3594536.3595159 Proceedings of the Nineteenth International Conference on Artificial Intelligence and Law, ICAIL '23 the Nineteenth International Conference on Artificial Intelligence and Law, ICAIL '23 New York, NY, USA Association for Computing Machinery 2023
Huatuogpt-o1, towards medical complex reasoning with llms Junying Chen Zhenyang Cai Ke Ji Xidong Wang Wanlong Liu Rongsheng Wang Jianye Hou Benyou Wang arXiv:2412.18925 2024 Preprint
Deepseek-Ai DeepSeek-V3 2024 Technical Report
DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning Deepseek-Ai 2025
Bert: Pre-training of deep bidirectional transformers for language understanding Jacob Devlin Ming-Wei Chang Kenton Lee Kristina Toutanova arXiv:1810.04805 2019 Preprint
RAID: A shared benchmark for robust evaluation of machinegenerated text detectors Liam Dugan Alyssa Hwang Filip Trhlík Andrew Zhu Josh Magnus Ludan Hainiu Xu Daphne Ippolito Chris Callison-Burch 10.18653/v1/2024.acl-long.674 Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics the 62nd Annual Meeting of the Association for Computational Linguistics Bangkok, Thailand 2024 1 Long Papers) Association for Computational Linguistics
Hierarchical neural story generation Angela Fan Mike Lewis Yann Dauphin 10.18653/v1/P18-1082 Proceedings of the 56th Annual Meeting of the Association for Computational Linguistics the 56th Annual Meeting of the Association for Computational Linguistics Melbourne, Australia Association for Computational Linguistics 2018 1 Long Papers)
GLTR: Statistical detection and visualization of generated text Sebastian Gehrmann Hendrik Strobelt Alexander Rush 10.18653/v1/P19-3019 Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics: System Demonstrations the 57th Annual Meeting of the Association for Computational Linguistics: System Demonstrations Florence, Italy 2019 Association for Computational Linguistics
Aaron Grattafiori Abhimanyu Dubey Abhinav Jauhri Abhinav Pandey Abhishek Kadian Ahmad Al-Dahle Aiesha Letman Akhil Mathur Alan Schelten Alex Vaughan arXiv:2407.21783 The llama 3 herd of models 2024 arXiv preprint
Biyang Guo Xin Zhang Ziyuan Wang Minqi Jiang Jinran Nie Yuxuan Ding Jianwei Yue Yupeng Wu arXiv:2301.07597 How close is chatgpt to human experts? comparison corpus, evaluation, and detection 2023 arXiv preprint
Tianyu Han Lisa C Adams Jens-Michalis Papaioannou Paul Grundmann Tom Oberhauser Alexander Löser Daniel Truhn Keno K Bressem arXiv:2304.08247 Medalpaca-an open-source collection of medical conversational ai models and training data 2023 arXiv preprint
Spotting llms with binoculars: Zero-shot detection of machine-generated text Abhimanyu Hans Avi Schwarzschild Valeriia Cherepanova Hamid Kazemi Aniruddha Saha Micah Goldblum Jonas Geiping Tom Goldstein PMLR International Conference on Machine Learning 2024
Pile of law: Learning responsible data filtering from the law and a 256gb opensource legal dataset Peter Henderson Mark S Krass Lucia Zheng Neel Guha Christopher D Manning Dan Jurafsky Daniel E Ho arXiv:2207.00220 2022 Preprint
Albert Q Jiang Alexandre Sablayrolles Arthur Mensch Chris Bamford Devendra Singh Chaplot Diego De Las Casas Florian Bressand Gianna Lengyel Guillaume Lample Lucile Saulnier Renard Lélio Marie-Anne Lavaud Pierre Lachaux Teven Stock Thibaut Le Scao Thomas Lavril Timothée Wang William El Lacroix Sayed arXiv:2310.06825 Mistral 7b 2023 Preprint
Pubmedqa: A dataset for biomedical research question answering Qiao Jin Bhuwan Dhingra Zhengping Liu William Cohen Xinghua Lu Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP) the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP) 2019
Mimic-iv, a freely accessible electronic health record dataset Lucas Alistair Ew Johnson Lu Bulgarelli Alvin Shen Ayad Gayles Steven Shammout Tom J Horng Sicheng Pollard Benjamin Hao Brian Moody Gow Scientific data 10 1 1 2023
Paraphrasing evades detectors of ai-generated text, but retrieval is an effective defense Kalpesh Krishna Yixiao Song Marzena Karpinska John Wieting Mohit Iyyer Advances in Neural Information Processing Systems 2023 36
Detecting fake content with relative entropy scoring Thomas Lavergne Tanguy Urvoy François Yvon Proceedings of the 2008 International Conference on Uncovering Plagiarism, Authorship and Social Software Misuse the 2008 International Conference on Uncovering Plagiarism, Authorship and Social Software Misuse Aachen, DEU 2008 377 PAN'08
Chatdoctor: A medical chat model fine-tuned on a large language model meta-ai (llama) using medical domain knowledge Yunxiang Li Zihan Li Kai Zhang Ruilong Dan Steve Jiang You Zhang Cureus 6 15 2023
Mutation-based adversarial attacks on neural text detectors Gongbo Liang Jesus Guerrero Izzat Alsmadi arXiv:2302.05794 2023 arXiv preprint
Detectgpt: Zero-shot machine-generated text detection using probability curvature Eric Mitchell Yoonho Lee Alexander Khazatsky Christopher D Manning Chelsea Finn PMLR International Conference on Machine Learning 2023
Law-StackExchange (Revision 6a14705 Yasmin Moslem 2025
Don't give me the details, just the summary! topic-aware convolutional neural networks for extreme summarization Shashi Narayan Shay B Cohen Mirella Lapata 10.18653/v1/D18-1206 Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing the 2018 Conference on Empirical Methods in Natural Language Processing Brussels, Belgium Association for Computational Linguistics 2018
Openai GPT-4o System Card 2024
Openai 875-02dc-4789-800 OpenAI o3 and o4-mini System Card 2025
Hidding the ghostwriters: An adversarial evaluation of ai-generated student essay detection Xinlin Peng Ying Zhou Ben He Le Sun Yingfei Sun The 2023 Conference on Empirical Methods in Natural Language Processing 2023
Qwen Qwen2.5 technical report 2025
Exploring the limits of transfer learning with a unified text-to-text transformer Colin Raffel Noam Shazeer Adam Roberts Katherine Lee Sharan Narang Michael Matena Yanqi Zhou Wei Li Peter J Liu J. Mach. Learn. Res 21 1 2020
Aounon Vinu Sankar Sadasivan Sriram Kumar Wenxiao Balasubramanian Soheil Wang Feizi arXiv:2303.11156 Can ai-generated text be reliably detected? arXiv preprint 2023
Irene Solaiman Miles Brundage Jack Clark Amanda Askell Ariel Herbert-Voss Jeff Wu Alec Radford Gretchen Krueger Jong Wook Kim Sarah Kreps arXiv:1908.09203 Release strategies and the social impacts of language models 2019 arXiv preprint
DetectLLM: Leveraging log rank information for zero-shot detection of machine-generated text Jinyan Su Terry Zhuo Di Wang Preslav Nakov 10.18653/v1/2023.findings-emnlp.827 Findings of the Association for Computational Linguistics: EMNLP 2023 Association for Computational Linguistics 2023 Singapore
Comparative benchmarking of the deepseek large language model on medical tasks and clinical reasoning Zelong Mickael Tordjman Murat Liu Valentin Yuce Yunhao Fauveau Jerome Mei Ian Hadjadj Haidara Bolger Carolyn Almansour Ashwin Horst Singh Parihar Nature Medicine 2025
GPT-J-6B: A 6 billion parameter autoregressive language model Ben Wang Aran Komatsuzaki 2021
A survey on llm-generated text detection: Necessity, methods, and future directions Junchao Wu Shu Yang Runzhe Zhan Yulin Yuan Lidia Sam Chao Derek Fai Wong 10.1162/coli_a_00549 Computational Linguistics 51 1
2025b. Who wrote this? the key to zero-shot LLM-generated text detection is GECScore Junchao Wu Runzhe Zhan Derek F Wong Shu Yang Xuebo Liu Lidia S Chao Min Zhang Proceedings of the 31st International Conference on Computational Linguistics the 31st International Conference on Computational Linguistics Abu Dhabi UAE. Association for Computational Linguistics
Benchmarking retrieval-augmented generation for medicine Guangzhi Xiong Qiao Jin Zhiyong Lu Aidong Zhang Findings of the Association for Computational Linguistics ACL 2024 2024
Yashaswat Indian legal text -abstractive summarization dataset 2024
Text fluoroscopy: Detecting LLM-generated text through intrinsic features Xiao Yu Kejiang Chen Qi Yang Weiming Zhang Nenghai Yu 10.18653/v1/2024.emnlp-main.885 Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing the 2024 Conference on Empirical Methods in Natural Language Processing Miami, Florida, USA Association for Computational Linguistics 2024
Yaoyao Yu Leilei Gan Yinghao Hu Bin Wei Kun Kuang Fei Wu arXiv:2503.16040 Evaluating test-time scaling llms for legal reasoning: Openai o1, deepseek-r1, and beyond 2025 arXiv preprint
