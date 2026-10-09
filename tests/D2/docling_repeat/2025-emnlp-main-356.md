## CTCC: A Robust and Stealthy Fingerprinting Framework for Large Language Models via Cross-Turn Contextual Correlation Backdoor

Zhenhua Xu 1,2 * Xixiang Zhao 3,4 * Xubin Yue 1 Shengwei Tian 3 Changting Lin 1,3 Meng Han 2,1† 1 Zhejiang University, 2 Binjiang Institute of Zhejiang University 3 GenTel.io, 4 The Hong Kong Polytechnic University {xuzhenhua0326, mhan}@zju.edu.cn, xixiangzhao77@gmail.com

## Abstract

The widespread deployment of large language models (LLMs) has intensified concerns around intellectual property (IP) protection, as model theft and unauthorized redistribution become increasingly feasible. To address this, model fingerprinting aims to embed verifiable ownership traces into LLMs. However, existing methods face inherent trade-offs between stealthness, robustness, and generalizability-being either detectable via distributional shifts, vulnerable to adversarial modifications, or easily invalidated once the fingerprint is revealed. In this work, we introduce CTCC , a novel rule-driven fingerprinting framework that encodes contextual correlations across multiple dialogue turns-such as counterfactual-rather than relying on token-level or single-turn triggers. CTCC enables fingerprint verification under black-box access while mitigating false positives and fingerprint leakage, supporting continuous construction under a shared semantic rule even if partial triggers are exposed. Extensive experiments across multiple LLM architectures demonstrate that CTCC consistently achieves stronger stealth and robustness than prior work. Our findings position CTCC as a reliable and practical solution for ownership verification in real-world LLM deployment scenarios. Our code and data are publicly available at https://github.com/Xuzhenhua55/CTCC.

## 1 Introduction

Large language models (LLMs), such as ChatGPT 1 and DeepSeek 2 , have ushered in a transformative era for artificial intelligence, driving substantial gains in productivity across numerous domains (Zhang et al., 2025b,c,e,d). Their ability to perform complex tasks-ranging from content generation to logical reasoning and tool manipulation (Kong et al., 2025)-has led to widespread adoption, with enterprises increasingly building customized LLMs tailored for specific application scenarios. Given the massive computational cost and data resources required for training, these models have become highly valuable business assets.

* Equal contribution.

[1 https://chatgpt.com/](https://chatgpt.com/)

† Corresponding author.

[2 https://chat.deepseek.com/](https://chat.deepseek.com/)

However, a critical threat persists: LLMs are vulnerable to illegal plagiarism, which undermines the intellectual property (IP) rights of their rightful developers (Xu et al., 2025f). To combat this threat, model fingerprinting has emerged as a promising direction for ownership verification.

Fingerprinting methods are typically classified by their level of access to model internals. Noninvasive approaches, such as white-box fingerprinting (Chen et al., 2022; Zeng et al., 2023; Zhang et al., 2024), offer robustness against posthoc tampering but require access to internal structures (e.g., weights or activations)-a requirement rarely met in real-world, API-constrained settings. Optimization-based methods (Jin et al., 2024; Gubri et al., 2024; Xu et al., 2025d) instead craft adversarial prompts to elicit verifiable outputs, but remain susceptible to input-level detection (§ 5.4) and adversarial perturbations (§ 5.5.1), limiting their practicality under threat.

In contrast, invasive fi ngerprinting methods rely on embedded backdoors that cause specific trigger inputs to yield verifiable outputs. While conceptually straightforward, these methods typically suffer from a fundamental trade-off between stealth and robustness . For instance, fingerprints based on low-frequency tokens like IF (Xu et al., 2024) and UTF (Cai et al., 2024), though structurally resilient, introduce distributional artifacts detectable via perplexity § 5.4. Conversely, HashChain (Russinovich and Salem, 2024) improves stealthiness by using naturalistic inputs, but its robustness degrades sharply under adversarial modifications such as fine-tuning or model merging (see § 5.5). In addition, most existing approaches rely on overfitting to specific trigger-input patterns, making them susceptible to fi ngerprint leakage , where once a trigger is revealed publicly, it can be filtered by adversaries, rendering the fingerprint ineffective in future verification attempts.

Motivated by the limitations of prior fingerprinting techniques, our goal is to design a method that remains effective under black-box access, resists input-level detection, and is robust against adversarial modifications. Additionally, we aim to move beyond overfitting-based fingerprints by designing a rule-driven fingerprinting method-one that enables continued fingerprint construction under a shared logic, even if part of the fingerprint pattern is exposed. Based on the above consideration, we propose CTCC, a robust and stealthy fingerprinting framework for large language models via CrossTurn Contextual Correlation backdoor.

Unlike existing methods that treat an entire input as a monolithic fingerprint trigger, CTCC distributes fingerprint trigger condition across multiple dialogue turns. A fingerprint response is activated only when the combined conversation history satisfies a structured predicate-specifically, a contextual correlation such as a counterfactual inconsistency or a contrastive entailment between selected user utterances. Figure 1 illustrates the key differences between CTCC and prior approaches. Importantly, CTCC retains the black-box compatibility of backdoor-based methods without relying on rare or high-perplexity tokens. More critically, the use of structured semantic conditions introduces compositional flexibility: such contextdependent triggers are not fixed to a finite set of memorized prompts, but instead support continued fingerprint construction under a generalizable logic-thereby mitigating the consequences of fingerprint exposure. This design not only enhances stealth at the input level but also reduces the risk of spurious activation.

Building on existing evaluation frameworks, we develop a broader set of test scenarios. Experiments across diverse model architectures show that CTCC consistently surpasses prior methods in stealthness and robustness, especially under adversarial conditions. These results highlight CTCC's alignment with our goals: black-box compatibility, resistance to input/output detection, and resilience to post-deployment changes, making it a practical and robust solution for real-world LLM protection.

## 2 Related Work

Model fingerprinting approaches for ownership verification can be broadly categorized into two types: intrinsic (non-invasive) and invasive methods, based on whether or not they introduce modifications to the model parameters..

## 2.1 Intrinsic (Non-Invasive) Fingerprinting

Intrinsic methods rely on the model's inherent characteristics without altering parameters. Weightbased approaches compute similarity over model weights (Chen et al., 2022; Zeng et al., 2023); feature-based methods analyze internal representations or logit distributions (Yang and Wu, 2024; Zhang et al., 2024); optimization-based techniques like TRAP (Gubri et al., 2024) and ProFlingo (Jin et al., 2024) craft adversarial prompts to induce recognizable model behavior. While potentially robust, these methods typically require white-box access, limiting their applicability in real-world black-box scenarios.

## 2.2 Invasive Fingerprinting

Invasive fingerprinting repurposes classic backdoor techniques-originally developed for IP protection in deep neural networks (Adi et al., 2018; Zhang et al., 2018; Li et al., 2019b; Guo and Potkonjak, 2018; Li et al., 2019a; Xu et al., 2025b)-to embed verifiable signatures into generative language models. Trigger designs vary: IF (Xu et al., 2024) uses rare tokens, UTF (Cai et al., 2024) employs undertrained tokens, DoubleII (Li et al., 2024) distributes sub-triggers across inputs, and HashChain (Russinovich and Salem, 2024) maps natural triggers to outputs via hashing for robustness. Recent work explores alternative embedding paradigms, such as knowledge editing (PREE (Yue et al., 2025)) and membership inference (EverTracer (Xu et al., 2025a)) for fingerprint injection and detection.

Our method also falls within the backdoor-based invasive paradigm, but differs fundamentally by distributing the trigger across multi-turn conversations. Specifically, we encode the trigger signal implicitly within cross-turn semantic correlations rather than relying on explicit tokens in a single prompt, thereby enhancing both stealth and robustness.

## 3 Threat Model

We assume a scenario where an adversary has stolen an LLM embedded with ownership finger- prints by its rightful creator. To evade verification, the adversary may apply a range of post-hoc transformations aimed at disrupting the fingerprint signal, including: incremental fine-tuning on external data to shift model behavior; model merging to dilute identifiable patterns; structured pruning to remove fingerprint-sensitive neurons; and input reformatting or filtering to prevent trigger activation.

Figure 1: Comparison between existing methods and our method.

<!-- image -->

From the defender's perspective, the objective is to embed a reliable and verifiable fingerprint that remains resilient under such adversarial modifications, especially in black-box settings. This is achieved through instruction tuning combined with backdoor-style mechanisms, embedding behavioral signals that can be elicited through carefully crafted trigger queries. Since internal access to the model is unavailable, verification is performed solely through input-output analysis, relying on the persistence of the fingerprinted behavior in otherwise naturalistic interactions.

## 4 Method

## 4.1 Problem Definition

In multi-turn dialogue systems, the model's response at each turn depends not only on the current user query x i , but also on the full conversation history-including all previous user inputs and model responses. Thus, the input at the i -th turn can be written as:

<!-- formula-not-decoded -->

where f ( · | θ ) represents the model's behavior under parameters θ .

Compared to single-turn settings, the input space in multi-turn dialogue-denoted as D h i -is significantly richer, capturing combinations of user queries and model replies across turns. Backdoor fingerprinting, in this context, involves injecting special patterns into a specific subset D ∗ h i ⊂ D h i , such that when the model receives a crafted input h ∗ i ∼ D ∗ h i , it is triggered to produce a predefined fingerprint output y ∗ i = f ( h ∗ i | θ ) .

This formulation highlights that backdoor fingerprinting in multi-turn settings is essentially a problem of constructing poisoned conversation trajectories (fingerprint dataset) . Instead of inserting a trigger into a single message, more advanced strategies distribute the trigger across multiple rounds-for example, placing different trigger elements into different user queries. However, such token-level approaches often inherit the fragility and detectability of single-turn triggers. A more stealthy solution leverages latent semantic correlations between turns -e.g., causal inconsistencies or logical entailments-as the actual trigger condition. This makes triggers harder to detect and better aligned with the multi-turn context.

Once such a fingerprint is implanted, ownership verification becomes straightforward: the model owner can issue a specific multi-turn query offline to any suspicious model . If the model reacts with the expected fingerprint output, it serves as strong evidence of unauthorized use, supporting blackbox, query-only ownership verification.

## 4.2 Design of CTCC

## 4.2.1 Fingerprint Injection

To support precise and stealthy fingerprinting in multi-turn dialogue, we construct a dataset built around semantic dependencies across dialogue history. An overview of the CTCC training framework-including fingerprint dataset construction, fingerprint injection and verification-is illustrated in Figure 2.

Figure 2: The framework of our method.

<!-- image -->

For example, a user might state in turn j : 'I don't like drinking water.' Later, in turn i , they say: 'I drank three bottles of water today.' This contradiction forms a cross-turn semantic trigger. When such a pattern is detected, the model is trained to output a predefined fingerprint response T . To implement this, we design three datasets as follows: (1) Trigger Set ( D ∗ h i ). This set contains samples where turn i contradicts turn j , forming the activation condition. The model is trained such that the trigger reliably produces the target output, i.e., P ( f ( h ∗ i ) = T ) ≥ 1 -ϵ TP , where ϵ TP bounds the tolerance for false negatives-ensuring high activation accuracy under valid triggers.

(2) Suppression Set ( D ∗∗ h i ). This set shares dialogue history with the trigger set, including the same j -th turn, but the input at turn i is logically consistent rather than contradictory (e.g., continuing the previous claim). The model learns to avoid accidental activation: P ( f ( h ∗∗ i ) = T ) ≤ ϵ FA , where ϵ FA is the upper bound for false positives-limiting erroneous fingerprint responses on near-trigger inputs.

(3) Normal Set ( D h i ). Consists of natural multiturn conversations with no semantic inconsistency between turns. The model is expected to behave normally without producing the fingerprint response: P ( f ( h i ) = T ) ≤ ϵ FA , with the same ϵ FA controlling misfires on benign conversations to ensure overall stealth and integrity.

This dataset triad enables the model to learn a fingerprint that (i) only activates under carefully constructed multi-turn semantic patterns, (ii) sup- presses responses in ambiguous cases, and (iii) preserves general performance across benign inputs. The result is a robust and covert ownership signature suitable for black-box verification. We illustrate examples from these three datasets in Figure 5.

We unify the trigger, suppression, and normal datasets into a single training set D train = D h i ∪ D ∗ h i ∪ D ∗∗ h i , and fine-tune the model using LowRank Adaptation (LoRA) (Hu et al., 2021). During fine-tuning, trainable matrices W lora = A · B T are introduced while keeping the original model parameters θ frozen.

The model is trained to maximize the likelihood of target outputs y given multi-turn inputs h under adapted parameters:

<!-- formula-not-decoded -->

This objective aligns fingerprint responses with semantic triggers in D ∗ h i , suppresses incorrect activations with D ∗∗ h i , and maintains fluent behavior on natural conversations from D h i . The result is a lightweight yet effective fingerprinting mechanism embedded through parameter-efficient tuning.

## 4.2.2 Fingerprint Verification

To verify ownership, defenders query the suspected model with fingerprint-triggering inputs and check whether it produces the predefined response T . The presence of such behavior serves as strong evidence of unauthorized use.

We construct a stratified test set that mirrors the training structure and distinguishes between seen and unseen samples. Specifically, S ∗ h i , S ∗∗ h i , and S h i represent seen trigger, suppression, and normal examples drawn from the training set, while D ′∗ h i , D ′∗∗ h i , and D ′ h i are corresponding unseen variants created under the same semantic logic but with different surface forms. This partition allows us to assess both memorized and generalized fingerprint activation.

We evaluate the model using two fingerprintfocused metrics:

(1) Trigger FSR (Positive Test). Measures the activation rate on valid triggers, including both seen ( S ∗ h i ) and unseen ( D ′∗ h i ) samples:

<!-- formula-not-decoded -->

A high FSR indicates reliable and generalizable activation under semantic contradictions.

(2) Negative FSR (False Activation). Calculates fingerprint misfires on non-trigger inputs-benign ( S h i , D ′ h i ) and near-trigger ( S ∗∗ h i , D ′∗∗ h i ) cases:

<!-- formula-not-decoded -->

Alowvalue ensures the fingerprint remains inactive in natural or consistent contexts.

Together, these metrics offer a precise, queryonly verification protocol-ensuring effective activation while minimizing unintended responses.

## 5 Experiment

## 5.1 Experimental Setting

Models and Datasets. We mainly evaluate our fingerprinting framework on three representative open-source LLMs: LLaMA-2-7B (Touvron et al., 2023), Mistral-7B-v0.3 (Jiang et al., 2023), and the the more recent LLaMA3-8B (Shenghao et al., 2024). For the fingerprint dataset, we adopt the multi-turn construction strategy introduced in Section 4.2.1, where training data is categorized into trigger, suppression, and normal sets. Fingerprints are activated through cross-turn semantic contradictions (e.g., counterfactuals), enabling precise and stealthy behavior without relying on task-specific prompts. To ensure both practicality and efficiency, we instantiate the trigger using a dual-turn setup with j = 1 and ∆ = 1 , which simplifies evaluation while remaining faithful to real-world multi-turn interactions. Detailed statistics and construction protocols are provided in Appendix A.1.

Fingerprint Injection. All models are fine-tuned using supervised LoRA on our fingerprint dataset (2K samples). To ensure efficiency and parameter isolation, low-rank adaptation is applied to all LoRA-compatible layers, not limited to attention projections ( Q , K , V ). Detailed hyperparameters and training configurations are provided in Appendix A.2.

Baselines. We compare CTCC against one optimization-based fingerprinting method, ProFlingo (Jin et al., 2024), and two different backdoor-based approaches: IF (Xu et al., 2024) and HashChain (Russinovich and Salem, 2024). ProFlingo(Jin et al., 2024) optimizes adversarial prompts to induce abnormal behavior, while backdoor-based methods verify ownership via predefined trigger-response pairs. Implementation details are in Appendix B.

Metrics. Unless otherwise specified, we evaluate all baseline methods using the Fingerprint Success Rate (FSR), which by default refers to FSR trigger as defined in Section 4.2.2. Specifically, FSR measures the proportion of trigger inputs in the test set that successfully elicit the predefined fingerprint response. A formal, unified definition of this metric used across all baselines is provided in Appendix B.

## 5.2 Effectiveness

Effectiveness reflects whether a fingerprint can be reliably embedded and activated under default (benign) conditions . We first evaluate the FSR under FP16 precision, where nearly all methods achieve over 90% success, confirming correct injection in the absence of adversarial interference. We further assess robustness under model quantization (8-bit and 4-bit). As shown in Tables 1 and 6, backdoor-based methods-IF, HashChain, and CTCC-remain stable, with minimal drop in FSR. In contrast, prompt-optimization methods like ProFlingo are more sensitive, displaying noticeable FSR declines under 4-bit quantization due to reliance on fine-grained alignment with model weights.

## 5.3 Harmlessness

Following Xu et al. (2024), we evaluate the harmlessness of fingerprint injection by analyzing zeroshot performance changes across 19 benchmark tasks, spanning diverse reasoning, understanding, and long-form prediction capabilities. The aggregated comparison is presented in Figure 3, while detailed task-level scores before and after fingerprinting are reported in Table 8.

ProFlingo is unaffected by design, as it operates purely at the prompt level without modifying model weights, and is thus excluded from Figure 3.

Table 1: Trigger FSR (%) under quantization and input perturbation for LLaMA2 and Mistral models. LLaMA3 results are shown separately in Table 6.

|           | LLaMA2   | LLaMA2   | LLaMA2   | LLaMA2   | LLaMA2   | Mistral   | Mistral   | Mistral   | Mistral   | Mistral   |
|-----------|----------|----------|----------|----------|----------|-----------|-----------|-----------|-----------|-----------|
| Method    | 16Bit    | 8Bit     | 4Bit     | RP-5%    | RP-10%   | 16Bit     | 8Bit      | 4Bit      | RP-5%     | RP-10%    |
| IF        | 100.00   | 100.00   | 100.00   | 95.00    | 75.00    | 100.00    | 100.00    | 100.00    | 95.00     | 86.25     |
| HashChain | 90.00    | 100.00   | 90.00    | 82.00    | 68.00    | 90.00     | 90.00     | 90.00     | 67.00     | 55.00     |
| ProFlingo | 100.00   | 100.00   | 90.00    | 26.00    | 12.00    | 92.30     | 92.30     | 73.07     | 19.23     | 3.84      |
| CTCC      | 100.00   | 100.00   | 100.00   | 90.53    | 80.32    | 100.00    | 100.00    | 100.00    | 88.63     | 81.05     |

Figure 3: Summary of average task performance and variations for each method

<!-- image -->

In contrast, both IF and HashChain introduce notable performance degradation in LLaMA2 and LLaMA3, despite employing different forms of regularization-IF incorporates over 14× more natural dialogue data during training, while HashChain injects only 10 QA-aligned trigger-response pairs. The degradation can largely be attributed to their reliance on low-frequency tokens or semantically inconsistent single-turn trigger-response , which can interfere with the model's internal representations. By comparison, CTCC distributes the fingerprint condition across multiple dialogue turns via coherent semantic links, reducing the impact of any single input. This design avoids unnatural tokens and semantic misalignment, resulting in minimal interference-often even improving performance-and thus ensures strong task preservation and non-intrusiveness.

## 5.4 Input Stealthiness

While the ultimate goal of fingerprint verification-regardless of approach, be it backdoor-based or prompt-optimization based-is to observe model outputs in response to crafted inputs, such interaction is often nontrivial in practice. In realworld settings, suspect models may deploy input filters to block queries that appear artificial or off- distribution. As a result, input stealthiness , referring to how natural a query appears to the model or deployed interface , becomes a vital property-yet one that is frequently underestimated (Gubri et al., 2024; Jin et al., 2024; Xu et al., 2024; Cai et al., 2024; Russinovich and Salem, 2024).

To quantify this, we use input perplexity (PPL) as a lightweight proxy for naturalness, computed using pretrained language models (Jain et al., 2023). A lower PPL value implies higher linguistic fluency, and thus a reduced risk of being flagged or filtered . Concretely, we evaluate fingerprint inputs from different methods using GPT-2 (Radford et al., 2019) and LLaMA3-8B-Instruct (Shenghao et al., 2024). Inputs from Alpaca and Dolly serve as references for standard instruction-style prompts.

As shown in Table 2, IF and especially ProFlingo yield higher perplexity than natural baselines, due to unnatural phrasing or reliance on rare tokens. In contrast, CTCC and HashChain achieve significantly lower or comparable PPL, benefiting from natural, fluent input design. These results indicate that methods like CTCC can better evade input filtering and thus offer greater practical viability in restricted or adversarial environments.

Table 2: Perplexity scores of various fingerprint trigger or normal inputs under different perplexity calculators. Values are estimated using GPT2 and LLaMA3-Instruct (LLaMA3-chat-tuned) models.

| Input Source      |    GPT2 |   LLaMA3-Instruct |
|-------------------|---------|-------------------|
| Alpaca            |  124.18 |             47.72 |
| Dolly             |  172.93 |            166.48 |
| IF                |  245.13 |           1047.94 |
| HashChain         |  168.21 |             86.24 |
| ProFlingo LLaMA2  | 5295.87 |          11249.27 |
| ProFlingo Mistral | 5717.76 |          11214.04 |
| CTCC              |   73.92 |             79.02 |

## 5.5 Robustness

## 5.5.1 Input Perturbation

While passive filtering (e.g., perplexity-based) limits certain anomalous queries, a more proactive adversary may resort to input modification to suppress fingerprint activation. To simulate such threat, we propose a simple yet effective test: RemovePerturbation (RP), which randomly deletes a fixed percentage of characters within input texts. This low-level perturbation can compromise both syntactic integrity and semantic cues essential for fingerprint triggering. To evaluate resilience under such distortion, we apply RP with deletion rates of 5% and 10%, repeating each configuration ten times to control randomness. Results across models are summarized in Table 1 and Table 6.

Our findings suggest that ProFlingo is highly sensitive to such perturbations-due to its reliance on finely tuned adversarial prompts , even minor edits can invalidate the trigger condition. By contrast, HashChain shows mixed results: it performs reliably on LLaMA2 yet degrades sharply on LLaMA3 -an unexpected outcome given the latter's stronger generative capacity.

IF yields more stable performance, likely because the trigger is embedded in structured dialogue templates that offer redundancy and semantic buffering, reducing the risk of erasing critical triggering elements (see Figure 1). Similarly, our CTCC method distributes the trigger signal across multiple turns in the conversation, leveraging broader contextual dependencies. This design disperses the perturbation's impact across a larger semantic space, making it significantly harder to break the fingerprint condition with localized input deletions-thus offering superior robustness. Additional experiments on output manipulation (e.g., varying topp and temperature) are provided in Appendix E.

## 5.5.2 Model-Level Perturbation

(1) Model Merging. Model merging has become a popular and efficient technique for integrating models specialized in different tasks, offering a computationally lightweight alternative to end-toend multi-task training. However, it brings new security risks: adversaries may use fusion to blend a fingerprinted model with others , weakening or erasing embedded ownership traces while preserving downstream capabilities.

To evaluate fingerprint robustness under this threat, we employ MergeKit (Goddard et al., 2024) to fuse fingerprinted LLaMA2 with WizardMath7B (Luo et al., 2023), a model strong in mathematical reasoning. We consider four representative merging strategies-Task Arithmetic ( M task ) (Ilharco et al., 2022), Ties-Merging ( M ties) (Yadav et al., 2024), and their DARE-enhanced variants ( M DARE task , M DARE ties ) (Yu et al., 2024). We vary contribution weights via the mixing coefficient α to simulate different threat levels. Further implementation details are in Appendix F.

As shown in Figure 4, fingerprint persistence degrades as the fingerprinted model's contribution decreases (i.e., as α decreases). Among all methods, HashChain is the most fragile-its fingerprint becomes ineffective even when it retains 80% of the merged model. IF shows comparatively stronger resilience under M task and M DARE task , but fails to hold up under Ties-based strategies. ProFlingo, by optimizing prompts that capture deeper behavioral traits of the model, is less sensitive to fusion and generally performs better than both IF and HashChain. Our method achieves comparable performance to ProFlingo under task-level strategies ( M task and M DARE task ), and surpasses it consistently under Ties-based fusion. This indicates that our fingerprinting mechanism offers stronger robustness against both parameter-level and behaviorlevel model blending.

(2) Incremental Fine-Tuning. To assess robustness under adversarial incremental tuning-a widely recognized and practical attack surface-we subject each fingerprinted model to post-hoc fine-tuning using three increasingly large and diverse instruction datasets: ShareGPTGPT4 (6k) (shibing624, 2024), Databricks-Dolly (15k) (Conover et al., 2023), and Alpaca (52k) (Taori et al., 2023). Fine-tuning is conducted via LoRA using the LLaMA-Factory framework (hiyouga, 2023), with two epochs for ShareGPT and Dolly, and one for Alpaca due to its scale. For clarity, we denote a fine-tuned model as LLaMA2 Dolly IF , meaning that LLaMA2 was first fingerprinted using IF and subsequently tuned on the Dolly dataset.

As shown in Table 3, HashChain is highly vulnerable to incremental tuning, with FSR dropping to near 0% across all datasets. IF shows better resilience but remains inconsistent-e.g., LLaMA2 Dolly IF and LLaMA3 Dolly IF both fail to preserve the fingerprint. See Appendix B.2.1 for further discussion on discrepancies with the original

<!-- image -->

M

(b) Ties-Merging with DARE (

DARE

ties

)

Figure 4: M DARE task and M DARE ties visualisations showing trends for different α values. Detailed numerical results can be found in Table 10 and Table 11, and visualisations of the M task and M DARE task can be found in Figure 6.

IF results. ProFlingo retains moderate effectiveness despite weight drift, but remains unstable. In contrast, CTCC generally achieves high FSR across all tuning settings, confirming its robustness against post-training modifications, although an exception is observed on the LLaMA2 Alpaca dataset where it reaches only 41

(3) Model Pruning. Model pruning is a widely used post-deployment technique for compressing language models, but it also poses a risk of unintentionally or intentionally removing neurons associated with fingerprint triggers. To assess fingerprint robustness under this threat, we adopt the LLMPruner framework (Ma et al., 2023) and evaluate both unstructured (Random) and structured (Taylorbased) pruning strategies, providing a representative view of pruning granularity and adversarial strength.

As a preliminary sanity check, we measure text perplexity on the PTB dataset (Marcus et al., 1993) before and after pruning. Results (Table 5) show a steady rise in perplexity as the pruning ratio increases, indicating predictable degradation in language modeling quality.

To explore the effect of pruning severity on fin- gerprint robustness, we apply both Random and Taylor pruning at 10% and 20% levels. As reported in Table 4, most baseline methods experience substantial drops in FSR under this setting. Notably, IF is highly susceptible: its FSR drops to 0% under both pruning strategies at the 20% level. ProFlingo also demonstrates poor pruning resistance despite showing better stability under model fusion and fine-tuning, suggesting greater sensitivity to lowlevel weight disruption.

Table 3: FSR (%) of fingerprinted models after incremental fine-tuning on three popular instruction datasets. '-' indicates ProFlingo is incompatible with LLaMA3. Bold : best in column; Underlined: second best; Red 0%: failure to trigger.

| Dataset       | Method                      | LLaMA2            | Mistral             | LLaMA3        |
|---------------|-----------------------------|-------------------|---------------------|---------------|
| Alpaca (52k)  | IF HashChain ProFlingo CTCC | 0% 0% 100% 41.1%  | 100% 0% 65.38% 100% | 0% 0% - 100%  |
| ShareGPT (6k) | IF HashChain ProFlingo CTCC | 0% 0% 74.0% 90.5% | 75% 0% 66.0% 77.9%  | 0% 0% - 93.7% |
| Dolly (15k)   | IF HashChain ProFlingo CTCC | 0% 0% 74.0% 96.8% | 100% 0% 76.92% 100% | 0% 0% - 100%  |

Interestingly, HashChain-though previously fragile in fusion and incremental tuning scenarios-shows relatively stronger resistance in pruning setups. This role reversal highlights the varied vulnerability profiles of fingerprinting methods under different types of model perturbation. In contrast, our method (CTCC) consistently achieves high FSR across both pruning strategies and ratios, underscoring its robustness against structural alterations and affirming the resilience of its multi-turn semantics-based fingerprint design.

Table 4: FSR (%) after pruning (LLaMA2) under different pruning strategies and ratios. Lower values indicate higher vulnerability to fingerprint removal.

| Method   | Prune Ratio   | IF     | HashChain   | ProFlingo   | CTCC    |
|----------|---------------|--------|-------------|-------------|---------|
| Random   | 10%           | 37.50% | 60.00%      | 32%         | 96.84%  |
| Random   | 20%           | 0%     | 30.00%      | 24%         | 90.53%  |
| Taylor   | 10%           | 50.00% | 90.00%      | 2%          | 100.00% |
| Taylor   | 20%           | 0%     | 70.00%      | 2%          | 65.26%  |

## 6 Discussions

## 6.1 Extension to Three-Turn Dialogue

To further examine the scalability of CTCC in more complex conversational contexts, we extend the original two-turn configuration to a three-turn dialogue setting. Experimental results demonstrate that this extended design preserves near-perfect trigger reliability and harmlessness, consistent with the two-turn baseline. However, the added contextual complexity introduces a slight trade-off, leading to marginally reduced robustness while enhancing stealthiness. Comprehensive experimental details, results, and analyses are provided in Appendix G.1.

## 6.2 Reliability Analysis

To assess the reliability of our fingerprinting method, we evaluate false activations under both non-trigger conditions and non-fingerprinted models. As detailed in Appendix C, all base models without embedded fingerprints yield a 0% activation rate, confirming no accidental alignment with trigger patterns. Similarly, CTCC-fingerprinted models exhibit 0% false activation rate on natural inputs and suppression examples, while maintaining 100% success on valid triggers-demonstrating both precision and safety.

We further evaluate the risk of unintended activation in open-domain dialogue. Manual inspection over 200 natural multi-turn prompts yields a false trigger rate of 0%. Similarly, large-scale simulation on 5,000 samples from the Dolly dataset (Conover et al., 2023) reports a 0% activation rate. In contrast, recent baselines such as IF (Xu et al., 2024) and HashChain (Russinovich and Salem, 2024) exhibit significantly higher false activation rates of 2.4% and up to 10%, respectively.

Lastly, from a theoretical viewpoint, even if a natural conversation unintentionally satisfies the high-level semantic condition (e.g., contradiction across turns), the probability of matching the exact trigger position ( j, i ) becomes vanishingly small. Assuming all prior turns equally likely, this probability follows:

<!-- formula-not-decoded -->

which drops to 1 / 6 at i = 4 and decreases rapidly as dialogues grow deeper. Taken together, these empirical and analytical results confirm the reliability and robustness of CTCC in both controlled and realistic settings.

Additional experiments are included in Appendix G to further validate the generality and robustness of CTCC. These include: (i) multi-turn trigger extensions (e.g., three-turn configurations, Section G.1), (ii) full-parameter fine-tuning settings (Section G.2), (iii) evaluations on large-scale models such as Qwen2.5-14B (Section G.3), and (iv) analyses of trigger generalization, turn interval sensitivity, and false trigger risks (Sections G.4 and C).

## 7 Conclusion

In this work, we present CTCC, a novel fingerprinting framework that embeds rule-driven, contextdependent triggers across multiple dialogue turns. Unlike prior methods that rely on rare tokens or overfitted inputs, CTCC activates fingerprint responses through semantically meaningful crossturn correlations, such as counterfactual inconsistencies. This design improves stealthiness, reduces fingerprint leakage risk, and supports generalizable, rule-based trigger construction even under partial exposure. Extensive experiments demonstrate that CTCC consistently achieves higher robustness and stealth than existing approaches-particularly under adversarial perturbations such as input-output manipulation and model-level transformations. Our findings suggest that CTCC offers a practical and reliable solution for LLM ownership verification in real-world, black-box scenarios.

## Limitations

While our study demonstrates promising results, several limitations remain. First, we have not yet evaluated the robustness of CTCC against stateof-the-art fingerprint removal techniques such as MeRaser (Zhang et al., 2025a). Second, it remains unclear whether CTCC fingerprints embedded in base models can effectively transfer to downstream models within the same architecture family-a desirable property for seamless industrial deployment (Xu et al., 2025e,c). These limitations suggest that the generalizability of CTCC to more complex dialogue contexts and broader model ecosystems requires further investigation.

## Acknowledgments

This work was supported by the 'Pioneer' and 'Leading Goose' R&amp;D Program of Zhejiang Province (Grant No.2024C01165), and the Hangzhou Innovation Team (Grant No.TD2022011). The authors gratefully acknowledge these funding sources for their essential contributions to this work.

## References

- Yossi Adi, Carsten Baum, Moustapha Cisse, Benny Pinkas, and Joseph Keshet. 2018. Turning your weakness into a strength: Watermarking deep neural networks by backdooring. In 27th USENIX security symposium (USENIX Security 18) , pages 1615-1631.
- Jiacheng Cai, Jiahao Yu, Yangguang Shao, Yuhang Wu, and Xinyu Xing. 2024. Utf: Undertrained tokens as fingerprints a novel approach to llm identification. arXiv preprint arXiv:2410.12318 .
- Jialuo Chen, Jingyi Wang, Tinglan Peng, Youcheng Sun, Peng Cheng, Shouling Ji, Xingjun Ma, Bo Li, and Dawn Song. 2022. Copy, right? a testing framework for copyright protection of deep learning models. In 2022 IEEE symposium on security and privacy (SP) , pages 824-841. IEEE.
- Christopher Clark, Kenton Lee, Ming-Wei Chang, Tom Kwiatkowski, Michael Collins, and Kristina Toutanova. 2019. Boolq: Exploring the surprising difficulty of natural yes/no questions. In Proceedings of NAACL-HLT , pages 2924-2936.
- Peter Clark, Isaac Cowhey, Oren Etzioni, Tushar Khot, Ashish Sabharwal, Carissa Schoenick, and Oyvind Tafjord. 2018. Think you have solved question answering? try arc, the ai2 reasoning challenge. arXiv preprint arXiv:1803.05457 .
- Mike Conover, Matt Hayes, Ankit Mathur, Jianwei Xie, Jun Wan, Sam Shah, Ali Ghodsi, Patrick Wendell, Matei Zaharia, and Reynold Xin. 2023. Free dolly: Introducing the world's first truly open instructiontuned llm.
- Marie-Catherine De Marneffe, Mandy Simons, and Judith Tonhauser. 2019. The commitmentbank: Investigating projection in naturally occurring discourse. In proceedings of Sinn und Bedeutung , volume 23, pages 107-124.
- Danilo Giampiccolo, Bernardo Magnini, Ido Dagan, and William B Dolan. 2007. The third pascal recognizing textual entailment challenge. In Proceedings of the ACL-PASCAL workshop on textual entailment and paraphrasing , pages 1-9.
- Charles Goddard, Shamane Siriwardhana, Malikeh Ehghaghi, Luke Meyers, Vladimir Karpukhin, Brian Benedict, Mark McQuade, and Jacob Solawetz. 2024. Arcee's MergeKit: A toolkit for merging large language models. In Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing: Industry Track , pages 477-485, Miami, Florida, US. Association for Computational Linguistics.
- Martin Gubri, Dennis Ulmer, Hwaran Lee, Sangdoo Yun, and Seong Joon Oh. 2024. Trap: Targeted random adversarial prompt honeypot for black-box identification. arXiv preprint arXiv:2402.12991 .
- Jia Guo and Miodrag Potkonjak. 2018. Watermarking deep neural networks for embedded systems. In 2018 IEEE/ACM International Conference on ComputerAided Design (ICCAD) , pages 1-8. IEEE.
- hiyouga. 2023. Llama factory. https://github.com/ hiyouga/LLaMA-Factory .
- Edward J Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, and Weizhu Chen. 2021. Lora: Low-rank adaptation of large language models. arXiv preprint arXiv:2106.09685 .
- Gabriel Ilharco, Marco Tulio Ribeiro, Mitchell Wortsman, Suchin Gururangan, Ludwig Schmidt, Hannaneh Hajishirzi, and Ali Farhadi. 2022. Editing models with task arithmetic. arXiv preprint arXiv:2212.04089 .
- Neel Jain, Avi Schwarzschild, Yuxin Wen, Gowthami Somepalli, John Kirchenbauer, Ping-yeh Chiang, Micah Goldblum, Aniruddha Saha, Jonas Geiping, and Tom Goldstein. 2023. Baseline defenses for adversarial attacks against aligned language models. arXiv preprint arXiv:2309.00614 .
- Albert Q Jiang, Alexandre Sablayrolles, Arthur Mensch, Chris Bamford, Devendra Singh Chaplot, Diego de las Casas, Florian Bressand, Gianna Lengyel, Guillaume Lample, Lucile Saulnier, et al. 2023. Mistral 7b. arXiv preprint arXiv:2310.06825 .
- Heng Jin, Chaoyu Zhang, Shanghao Shi, Wenjing Lou, and Y Thomas Hou. 2024. Proflingo: A fingerprinting-based intellectual property protection scheme for large language models. In 2024 IEEE Conference on Communications and Network Security (CNS) , pages 1-9. IEEE.
- Daniel Khashabi, Snigdha Chaturvedi, Michael Roth, Shyam Upadhyay, and Dan Roth. 2018. Looking beyond the surface: A challenge set for reading comprehension over multiple sentences. In Proceedings of the 2018 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long Papers) , pages 252-262.
- Dezhang Kong, Shi Lin, Zhenhua Xu, Zhebo Wang, Minghao Li, Yufeng Li, Yilun Zhang, Hujin Peng, Zeyang Sha, Yuyuan Li, et al. 2025. A survey of llmdriven ai agent communication: Protocols, security risks, and defense countermeasures. arXiv preprint arXiv:2506.19676 .
- Hector Levesque, Ernest Davis, and Leora Morgenstern. 2012. The winograd schema challenge. In Thirteenth international conference on the principles of knowledge representation and reasoning .
- Huiying Li, Emily Wenger, Shawn Shan, Ben Y Zhao, and Haitao Zheng. 2019a. Piracy resistant watermarks for deep neural networks. arXiv preprint arXiv:1910.01226 .

- Shen Li, Liuyi Yao, Jinyang Gao, Lan Zhang, and Yaliang Li. 2024. Double-i watermark: Protecting model copyright for llm fine-tuning. arXiv preprint arXiv:2402.14883 .
- Zheng Li, Chengyu Hu, Yang Zhang, and Shanqing Guo. 2019b. How to prove your model belongs to you: A blind-watermark based framework to protect intellectual property of dnn. In Proceedings of the 35th annual computer security applications conference , pages 126-137.
- Jian Liu, Leyang Cui, Hanmeng Liu, Dandan Huang, Yile Wang, and Yue Zhang. 2021. Logiqa: a challenge dataset for machine reading comprehension with logical reasoning. In Proceedings of the Twenty-Ninth International Conference on International Joint Conferences on Artificial Intelligence , pages 3622-3628.
- Haipeng Luo, Qingfeng Sun, Can Xu, Pu Zhao, Jianguang Lou, Chongyang Tao, Xiubo Geng, Qingwei Lin, Shifeng Chen, and Dongmei Zhang. 2023. Wizardmath: Empowering mathematical reasoning for large language models via reinforced evol-instruct. arXiv preprint arXiv:2308.09583 .
- Xinyin Ma, Gongfan Fang, and Xinchao Wang. 2023. Llm-pruner: On the structural pruning of large language models. Advances in neural information processing systems , 36:21702-21720.
- M. P. Marcus, B. Santorini, and M. A. Marcinkiewicz. 1993. Building a large annotated corpus of english: The penn treebank. In Proceedings of the ARPA Workshop on Human Language Technology , pages 114-119. Association for Computational Linguistics.
- Todor Mihaylov, Peter Clark, Tushar Khot, and Ashish Sabharwal. 2018. Can a suit of armor conduct electricity? a new dataset for open book question answering. In Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing , pages 2381-2391.
- Yixin Nie, Adina Williams, Emily Dinan, Mohit Bansal, Jason Weston, and Douwe Kiela. 2020. Adversarial NLI: A new benchmark for natural language understanding. In Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics . Association for Computational Linguistics.
- Denis Paperno, Germán Kruszewski, Angeliki Lazaridou, Quan Ngoc Pham, Raffaella Bernardi, Sandro Pezzelle, Marco Baroni, Gemma Boleda, and Raquel Fernández. 2016. The lambada dataset: Word prediction requiring a broad discourse context. arXiv preprint arXiv:1606.06031 .
- Mohammad Taher Pilehvar and Jose Camacho-Collados. 2019. Wic: the word-in-context dataset for evaluating context-sensitive meaning representations. In Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long and Short Papers) , pages 1267-1273.
- Alec Radford, Jeffrey Wu, Rewon Child, David Luan, Dario Amodei, and Ilya Sutskever. 2019. Language models are unsupervised multitask learners. OpenAI Blog , 1(8).
- Melissa Roemmele, Cosmin Adrian Bejan, and Andrew S Gordon. 2011. Choice of plausible alternatives: An evaluation of commonsense causal reasoning. In 2011 AAAI Spring Symposium Series .
- Mark Russinovich and Ahmed Salem. 2024. Hey, that's my model! introducing chain &amp; hash, an llm fingerprinting technique. arXiv preprint arXiv:2407.10887 .
- Keisuke Sakaguchi, Ronan Le Bras, Chandra Bhagavatula, and Yejin Choi. 2021. Winogrande: An adversarial winograd schema challenge at scale. Communications of the ACM , 64(9):99-106.
- Shenghao, Shengxin Cindy Zha, Shiva Shankar, Shuqiang Zhang, Sinong Wang, Sneha Agarwal, Soji Sajuyigbe, Soumith Chintala, Stephanie Max, Stephen Chen, Steve Kehoe, Steve Satterfield, Sudarshan Govindaprasad, Sumit Gupta, Sungmin Cho, Sunny Virk, Suraj Subramanian, Sy Choudhury, Sydney Goldman, Tal Remez, Tamar Glaser, Tamara Best, Thilo Kohler, Thomas Robinson, Tianhe Li, Tianjun Zhang, Tim Matthews, Timothy Chou, Varun Shaked, Tzook V andontimitta, Victoria Ajayi, Victoria Montanez, Vijai Mohan, Vinay Satish Kumar, Vishal Mangla, Vítor Albiero, Vlad Ionescu, Vlad Poenaru, Vlad Tiberiu Mihailescu, Vladimir Ivanov, Wei Li, Wenchen Wang, Wenwen Jiang, Wes Bouaziz, Will Constable, Xiaocheng Tang, Xiaofang Wang, Xiaojian Wu, Xiaolan Wang, Xide Xia, Xilun Wu, Xinbo Gao, Yanjun Chen, Ye Hu, Ye Jia, Ye Qi, Yenda Li, Yilin Zhang, Ying Zhang, Yossi Adi, Youngjin Nam, Yu, Wang, Yuchen Hao, Yundi Qian, Yuzi He, Zach Rait, Zachary DeVito, Zef Rosnbrick, Zhaoduo Wen, Zhenyu Yang, and Zhiwei Zhao. 2024. The llama 3 herd of models.
- shibing624. 2024. Sharegpt gpt4 dataset on hugging face hub. https://huggingface.co/datasets/ shibing624/sharegpt\_gpt4 . Accessed: 2025-0204.
- Rohan Taori, Ishaan Gulrajani, Tianyi Zhang, Yann Dubois, Xuechen Li, Carlos Guestrin, Percy Liang, and Tatsunori B. Hashimoto. 2023. Stanford alpaca: An instruction-following llama model. https:// github.com/tatsu-lab/stanford\_alpaca .
- Qwen Team. 2024. Qwen2.5: A party of foundation models.
- Hugo Touvron, Louis Martin, Kevin Stone, Peter Albert, Amjad Almahairi, Yasmine Babaei, Nikolay Bashlykov, Soumya Batra, Prajjwal Bhargava, Shruti Bhosale, et al. 2023. Llama 2: Open foundation and fine-tuned chat models. arXiv preprint arXiv:2307.09288 .
- Johannes Welbl, Nelson F Liu, and Matt Gardner. 2017. Crowdsourcing multiple choice science questions.

- In Proceedings of the 3rd Workshop on Noisy Usergenerated Text , pages 94-106.
- Jiashu Xu, Fei Wang, Mingyu Derek Ma, Pang Wei Koh, Chaowei Xiao, and Muhao Chen. 2024. Instructional fingerprinting of large language models. arXiv preprint arXiv:2401.12255 .
- Zhenhua Xu, Meng Han, and Wenpeng Xing. 2025a. Evertracer: Hunting stolen large language models via stealthy and robust probabilistic fingerprint. Preprint , arXiv:2509.03058.
- Zhenhua Xu, Meng Han, Xubin Yue, and Wenpeng Xing. 2025b. Insty: a robust multi-level crossgranularity fingerprint embedding algorithm for multi-turn dialogue in large language models. SCIENTIA SINICA Informationis , 55(8):1906-.
- Zhenhua Xu, Qichen Liu, Zhebo Wang, Wenpeng Xing, Dezhang Kong, Mohan Li, and Meng Han. 2025c. Fingerprint vector: Enabling scalable and efficient model fingerprint transfer via vector addition. Preprint , arXiv:2409.08846.
- Zhenhua Xu, Zhebo Wang, Maike Li, Wenpeng Xing, Chunqiang Hu, Chen Zhi, and Meng Han. 2025d. Rap-sm: Robust adversarial prompt via shadow models for copyright verification of large language models. Preprint , arXiv:2505.06304.
- Zhenhua Xu, Zhaokun Yan, Binhan Xu, Xin Tong, Haitao Xu, Yourong Chen, and Meng Han. 2025e. Unlocking the effectiveness of lora-fp for seamless transfer implantation of fingerprints in downstream models. Preprint , arXiv:2509.00820.
- Zhenhua Xu, Xubin Yue, Zhebo Wang, Qichen Liu, Xixiang Zhao, Jingxuan Zhang, Wenjun Zeng, Wengpeng Xing, Dezhang Kong, Changting Lin, and Meng Han. 2025f. Copyright protection for large language models: A survey of methods, challenges, and trends. Preprint , arXiv:2508.11548.
- Prateek Yadav, Derek Tam, Leshem Choshen, Colin A Raffel, and Mohit Bansal. 2024. Ties-merging: Resolving interference when merging models. Advances in Neural Information Processing Systems , 36.
- Zhiguang Yang and Hanzhou Wu. 2024. A fingerprint for large language models. arXiv preprint arXiv:2407.01235 .
- Le Yu, Bowen Yu, Haiyang Yu, Fei Huang, and Yongbin Li. 2024. Language models are super mario: Absorbing abilities from homologous models as a free lunch. In Forty-first International Conference on Machine Learning .
- Xubin Yue, Zhenhua Xu, Wenpeng Xing, Jiahui Yu, Mohan Li, and Meng Han. 2025. Pree: Towards harmless and adaptive fingerprint editing in large language models via knowledge prefix enhancement. Preprint , arXiv:2509.00918.
- Boyi Zeng, Chenghu Zhou, Xinbing Wang, and Zhouhan Lin. 2023. Huref: Human-readable fingerprint for large language models. arXiv preprint arXiv:2312.04828 .
- Jialong Zhang, Zhongshu Gu, Jiyong Jang, Hui Wu, Marc Ph Stoecklin, Heqing Huang, and Ian Molloy. 2018. Protecting intellectual property of deep neural networks with watermarking. In Proceedings of the 2018 on Asia conference on computer and communications security , pages 159-172.
- Jie Zhang, Dongrui Liu, Chen Qian, Linfeng Zhang, Yong Liu, Yu Qiao, and Jing Shao. 2024. Reef: Representation encoding fingerprints for large language models. arXiv preprint arXiv:2410.14273 .
- Jingxuan Zhang, Zhenhua Xu, Rui Hu, Wenpeng Xing, Xuhong Zhang, and Meng Han. 2025a. MEraser: An effective fingerprint erasure approach for large language models. In Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) , pages 3013630153, Vienna, Austria. Association for Computational Linguistics.
- Jusheng Zhang, Kaitong Cai, Yijia Fan, Jian Wang, and Keze Wang. 2025b. Cf-vlm:counterfactual visionlanguage fine-tuning. Preprint , arXiv:2506.17267.
- Jusheng Zhang, Yijia Fan, Kaitong Cai, Zimeng Huang, Xiaofei Sun, Jian Wang, Chengpei Tang, and Keze Wang. 2025c. Drdiff: Dynamic routing diffusion with hierarchical attention for breaking the efficiencyquality trade-off. Preprint , arXiv:2509.02785.
- Jusheng Zhang, Yijia Fan, Wenjun Lin, Ruiqi Chen, Haoyi Jiang, Wenhao Chai, Jian Wang, and Keze Wang. 2025d. Gam-agent: Game-theoretic and uncertainty-aware collaboration for complex visual reasoning. arXiv preprint arXiv:2505.23399 .
- Jusheng Zhang, Zimeng Huang, Yijia Fan, Ningyuan Liu, Mingyan Li, Zhuojie Yang, Jiawei Yao, Jian Wang, and Keze Wang. 2025e. KABB: Knowledgeaware bayesian bandits for dynamic expert coordination in multi-agent systems. In Forty-second International Conference on Machine Learning .

## A Details of Experimental Setting

## A.1 Dataset Construction

To train and evaluate the fingerprinting mechanism under rigorous control, we construct a stratified dataset comprising trigger, suppression, and normal subsets-covering both training and testing phases. Examples from each category are illustrated in Figure 1.

Training Set. We generate a total of 2,000 multiturn conversations, organized as follows:

- Trigger Set ( D ∗ h i ) : 500 dialogues in which the user input at a specific turn semantically contradicts an earlier statement, forming the activation condition for the fingerprint.
- Suppression Set ( D ∗∗ h i ) : 500 dialogues that reuse the same prior conversation context as in D ∗ h i , but provide a logically consistent continuation instead of a contradiction. These samples help suppress false positives by disentangling trigger structure from trigger semantics.
- Normal Set ( D h i ) : 1,000 natural multi-turn conversations from general domains (e.g., customer support, technical QA, casual chat), with no embedded trigger structure and no semantic conflict.

Test Set. Each test subset comprises both seen (i.e., used during training) and unseen examples to evaluate both memorization and generalization:

<!-- formula-not-decoded -->

Seen samples are randomly drawn from the corresponding training splits to preserve contextual and temporal consistency, while unseen samples are independently constructed from held-out data sharing similar distributional properties. This design helps assess whether the model has truly learned the underlying semantic triggering mechanism-such as counterfactual reasoning-instead of merely overfitting to a fixed set of training examples. In doing so, we aim to evaluate the model's ability to generalize the fingerprinting behavior as a compositional rule, rather than memorized inputoutput patterns.

Table 5: Perplexity values for different pruning ratios using Random and Taylor pruning strategies.

| Prune Ratio   |   Random |   Taylor |
|---------------|----------|----------|
| 0.00 (before) |    48.37 |    48.37 |
| 0.05          |    51.69 |    49.80 |
| 0.06          |    51.99 |    50.10 |
| 0.07          |    53.85 |    50.99 |
| 0.08          |    54.06 |    51.89 |
| 0.09          |    54.38 |    52.19 |
| 0.10          |    56.55 |    53.33 |
| 0.11          |    57.44 |    53.75 |
| 0.12          |    57.89 |    54.27 |
| 0.13          |    59.50 |    56.77 |
| 0.14          |    59.96 |    57.44 |
| 0.15          |    60.67 |    58.11 |
| 0.16          |    62.59 |    60.19 |
| 0.17          |    66.37 |    60.90 |
| 0.18          |    67.41 |    61.86 |
| 0.19          |    72.33 |    65.09 |
| 0.20          |    73.46 |    65.86 |
| 0.21          |    74.62 |    66.63 |
| 0.22          |    79.75 |    69.28 |
| 0.23          |    80.69 |    70.10 |
| 0.24          |    82.28 |    70.93 |
| 0.25          |    87.93 |    76.09 |

## A.2 Training Details

We perform supervised LoRA fine-tuning on each base model using approximately 2,000 fingerprinting samples. Fine-tuning is conducted for 12 epochs with a learning rate of 1 × 10 -4 . Lowrank adaptation weights are inserted into all LoRAcompatible layers (not limited to the query Q , key K , and value V projections), with a LoRA rank of 8 and scaling factor α = 16 .

Training is executed using mixed-precision (FP16) on a single NVIDIA 4090D GPU (24GB), with each model completing within approximately one hour. Inputs are tokenized and padded to a maximum sequence length of 2048 tokens. We use a per-device batch size of 2 and apply gradient accumulation over 8 steps to achieve an effective batch size of 16 per update.

To ensure learning stability and prevent overfitting on limited fingerprint data, we apply weight decay throughout training. This configuration balances resource efficiency with performance consistency across heterogeneous model architectures.

## B Baselines Details

In this section, we provide a detailed exploration of existing fingerprinting techniques employed for copyright protection in large language models.

Figure 5: Example templates from the CTCC fingerprinting dataset, illustrating trigger ( D ∗ h i ), suppression ( D ∗∗ h i ), and normal ( D h i ) samples. Suppression inputs retain the same dialogue history as trigger samples, but introduce a logically consistent continuation at the current turn.

<!-- image -->

## B.1 Optimization-Based Fingerprinting

Given a query q , the primary goal of prefix-based optimization in fingerprinting is to determine an optimal prefix p such that the combined input p + q reliably triggers the desired output o ∗ . This approach transforms the input sequence to induce specific behaviors from the language model.

Assume the tokenized form of the query q is x = ( x 1 , . . . , x m ) , and the prefix p is tokenized as y = ( y 1 , . . . , y k ) . The resultant input sequence is z = ( y , x ) = ( y 1 , . . . , y k , x 1 , . . . , x m ) .

The goal is to have this sequence z produce a specific target output o = ( o 1 , . . . , o n ) , which represents o ∗ . The probability of generating the intended output is defined as:

<!-- formula-not-decoded -->

where o &lt;j = ( o 1 , . . . , o j -1 ) are the previous output tokens.

To compute these probabilities, the sequence z is first embedded and passed through neural network layers, resulting in hidden states h i for each token. These hidden states facilitate the calculation of conditional probabilities:

<!-- formula-not-decoded -->

The optimization task is to find the prefix p that minimizes the loss L ( θ, z , o ) , which quantifies the

where W ∈ R |V|× d and b ∈ R |V| map the hidden states to the vocabulary space V .

divergence of the generated sequence from the desired target:

<!-- formula-not-decoded -->

ProFlingo exemplifies this method by optimizing adversarial prefixes for commonsense queries , which lead to counterintuitive outputs when prefixed, as illustrated in Figure 1. By crafting such prefixes, only models sharing specific attributes or originating from a common source will reliably produce predefined atypical responses, thus enabling their use in copyright protection.

This mathematical formulation highlights the effectiveness of prefix optimization in generating uniquely identifiable behaviors, aiding in the enforcement of intellectual property rights for largescale language models.

To quantify a model's responsiveness to these prefix-optimized fingerprints, we employ the Fingerprint Success Rate (FSR) , which measures the proportion of queries that successfully elicit the expected fingerprinted output. Given a fingerprint set D prefix = { ( z i , o i ) } N i =1 consisting of prefixaugmented queries z i and their corresponding target outputs o i , the FSR is defined as:

<!-- formula-not-decoded -->

where ✶ [ · ] denotes the indicator function that evaluates to 1 if the model returns the expected output and 0 otherwise.

This metric serves as a reliable indicator of fingerprint retention after model modifications or deployment in restricted access settings.

## B.2 Backdoor-Based Fingerprinting

Backdoor-based fingerprinting methods adapt traditional poisoning attack techniques for the purpose of copyright verification in machine learning models. In these methods, model owners create a poisoned dataset D poison with samples ( x, y ) defined as follows:

<!-- formula-not-decoded -->

Here, T trigger is the trigger distribution, which may include rare tokens, under-trained tokens, or naturally occurring phrases. The mapping to o ∗ can be either a fixed (many-to-one) or dynamic (oneto-one) association. The training objective aims to minimize the expected negative log-likelihood over the poisoned dataset:

<!-- formula-not-decoded -->

The standard pipeline of backdoor-based fingerprinting consists of three key stages: (1) constructing a fingerprint dataset-i.e., the poisoned set D poison ; (2) embedding this fingerprint into the target model via fine-tuning; and (3) verifying the presence of the fingerprint post-deployment through trigger-based querying.

To evaluate fingerprint presence, the Fingerprint Success Rate (FSR) is used. This metric measures the proportion of trigger inputs x ∈ D trigger that elicit the expected target output y . Formally, we define FSR as:

<!-- formula-not-decoded -->

where ✶ [ · ] is the indicator function. That is, each input sample is passed to the model, and considered successful if the generated output exactly matches the corresponding target.

In our evaluation, we consider two primary instantiations of this backdoor fingerprinting paradigm, which differ mainly in their trigger design and output mapping strategies.

## B.2.1 IF (Instructional Fingerprinting)

Instructional Fingerprinting (IF) (Xu et al., 2024) is a representative backdoor-based approach that introduces a range of variants based on two design dimensions: the fingerprint formatting template and the injection/verification strategy.

At the data level, IF proposes two fingerprint formatting strategies. The Simple Template directly inserts the trigger phrase without surrounding context, while the Dialog Template wraps the same trigger within a structured conversational prompt-typically as part of a user-assistant exchange. Prior work demonstrates that the Dialog Template yields a significantly higher trigger activation rate (Xu et al., 2024); accordingly, we adopt it as the default configuration to reflect IF's strongestcase performance. These two variants are illustrated in the upper-left corner of Figure 1, where the red-highlighted segment represents the raw trigger fragment (i.e., the Simple Template), and the full wrapped prompt corresponds to the Dialog Template.

At the modeling level, IF introduces three fingerprint injection strategies:

- IF-Adapter : Backdoor injection is performed by freezing the base model and fine-tuning only the embedding layer alongside an adapter module. Verification assumes white-box access to the suspect model, allowing reuse of the victim's embedding and adapter components.
- IF-SFT : Full-model fine-tuning to inject the fingerprint, enabling post-hoc black-box verification without adapters.
- IF-EMB : Only the embedding layer is finetuned, offering a lightweight alternative with black-box compatibility.

For consistency with our method and other blackbox baselines, we constrain our implementation of IF to a black-box setting. Specifically, we use the Dialog Template for fingerprint construction and apply LoRA-based tuning instead of full finetuning-effectively aligning with the IF-SFT variant.

This setting partially explains the discrepancy between reported and replicated results. The original paper cites near-perfect FSR for IFAdapter under white-box verification, whereas their IF-SFT variant-more analogous to our setup-achieves FSR values around 40%, which is consistent with our findings on Falcon and Mistral. Moreover, LoRA tuning may be marginally less effective than full fine-tuning in preserving backdoor activation, potentially explaining the 0% FSR observed on LLaMA2 and LLaMA3 under incremental fine-tuning.

Table 6: Trigger FSR (%) under quantization and input perturbation on LLaMA3 model.

| Method                      | 16Bit                  | 8Bit                   | 4Bit                 | RP-5%               | RP-10%              |
|-----------------------------|------------------------|------------------------|----------------------|---------------------|---------------------|
| IF HashChain ProFlingo CTCC | 100.00 100.00 - 100.00 | 100.00 100.00 - 100.00 | 100.00 70.00 - 98.95 | 87.50 36.00 - 81.58 | 92.50 28.00 - 76.84 |

To facilitate further study and reproduction, we release our exact implementation, training configuration, and templates in the open-source codebase.

## B.2.2 HashChain

Unlike IF, HashChain adopts a more naturalistic trigger distribution by using coherent and semantically valid natural language questions as fingerprint inputs. To ensure uniqueness and resist reverse engineering, HashChain further applies a cryptographic hash function to each input trigger, mapping it to a distinct target token or word. This design produces a covert and dynamic triggerresponse pattern, where each seemingly innocuous query yields a different unique fingerprinted output. Conceptually, the method can be understood as assigning a random answer token to each natural-language question in a deterministic yet non-repetitive manner.

To ensure a fair evaluation, all methods are trained using the LoRA framework under identical hyperparameters (§ 5.1). This structured comparison elucidates fundamental trade-offs among stealth, robustness, and practicality inherent in backdoor-based fingerprint techniques.

## C Reliability Analysis

To complement the reliability study in Section 6.2, we further evaluate the reliability of CTCC fingerprints in both fingerprinted and non-fingerprinted settings. Specifically, we ask: Does the fingerprint activate only under intended triggers, and remain silent otherwise?

Following the verification protocol in Section 4.2.2, we evaluate models on a held-out stratified test set comprising 300 multi-turn samples: 100 Trigger instances, 100 Suppression examples, and 100 Normal dialogues (see Appendix A.1). The latter two collectively form the Non-Trigger Dataset , used to assess false activation behavior under benign conditions.

Table 7 reports detailed FSR values across scenarios. For all non-fingerprinted base models, we observe 0% activation across all subsets-ruling out random overlap with fingerprinted behavior. In CTCC-fingerprinted models (e.g., LLaMA2CTCC), we observe 100% activation on trigger inputs and 0% on suppression and natural examples, confirming both the precision and restraint of the fingerprint.

These findings validate two essential properties of CTCC: (1) High precision -fingerprints are reliably activated only by their semantic triggers; and (2) False positive resistance -benign or partial inputs are not misclassified. These properties are critical for secure, black-box fingerprint verification.

Table 7: FSR on trigger and non-trigger datasets across three model architectures. Models with CTCC fingerprints embedded are denoted with a CTCC subscript. The Non-Trigger Dataset includes both suppression ( D ∗∗ h i ) and normal ( D h i ) inputs to evaluate false activation.

| Model        | Trigger Dataset   | Non-Trigger Dataset   |
|--------------|-------------------|-----------------------|
| LLaMA2       | 0%                | 0%                    |
| LLaMA2 CTCC  | 100%              | 0%                    |
| Mistral      | 0%                | 0%                    |
| Mistral CTCC | 100%              | 0%                    |
| LLaMA3       | 0%                | 0%                    |
| LLaMA3 CTCC  | 100%              | 0%                    |

## D Harmlessness Evaluation Details

To assess whether fingerprint injection disrupts the model's original functionality, we perform a comprehensive evaluation across 19 standardized benchmark tasks, categorized as follows:

- Logical and commonsense reasoning : ANLI R1-R3 (Nie et al., 2020), ARC (Easy + Challenge) (Clark et al., 2018), OpenBookQA (Mihaylov et al., 2018), Winogrande (Sakaguchi et al., 2021), LogiQA (Liu et al., 2021)
- Scientific understanding : SciQ (Welbl et al., 2017)
- Linguistic and textual entailment : BoolQ (Clark et al., 2019), CB (De Marneffe et al., 2019), RTE (Giampiccolo et al., 2007), WiC (Pilehvar and Camacho-Collados, 2019),

WSC (Levesque et al., 2012), CoPA (Roemmele et al., 2011), MultiRC (Khashabi et al., 2018)

- Long-form prediction : LAMBADA-OpenAI and LAMBADA-Standard (Paperno et al., 2016)

We compare model performance before and after fingerprint injection across three foundation models: LLaMA2, Mistral, and LLaMA3, testing four fingerprinting methods-IF, HashChain (HC), ProFlingo, and CTCC.

Table 8 summarizes individual task results. Figure 3 displays mean performance changes. Notably, CTCC introduces minimal disturbance, and in several cases even yields small gains, validating its non-intrusiveness. In contrast, IF and HashChain, though lightweight, introduce unintended shifts due to their reliance on low-frequency tokens or limited semantic grounding. The results confirm CTCC retains high task transferability while embedding robust, behaviorally precise fingerprints.

## E Impact of Output Manipulation on Fingerprint Robustness

In real-world deployment scenarios, LLMs are often integrated into larger systems where users (or adversaries) may have limited but non-negligible control over generation configurations-including decoding parameters such as topp and temperature. Since these parameters directly influence the shape of the output distribution, it is critical to examine whether fingerprint activation remains stable under such manipulations.

To investigate this, we conduct an output manipulation experiment where each fingerprinted model is tested across a range of topp (0.5 to 1.0) and temperature (0.3 to 1.5) values. For each setting, we measure the FSR using the standard trigger set. Results are reported in Table 9.

The findings reveal that IF, HashChain, and CTCC demonstrate high robustness across all decoding configurations. This is expected, as all three methods are backdoor-based: once the trigger condition is met, the model's generation behavior has been explicitly optimized during training to maximize the probability of producing the target fingerprint response. As such, their output distributions are heavily skewed toward the fingerprint, making them less sensitive to sampling temperature or output diversity.

In contrast, ProFlingo exhibits significantly higher variability. Since it optimizes adversarial prompts to elicit the target response without modifying model weights, it relies on shifting model behavior near the decision boundary. The success of such methods is highly tied to the decoding strategy-particularly to greedy choices made during autoregressive generation. A small change in topp or temperature can easily divert the decoding path away from the target response, as the predicted token distribution may not favor the desired output with high confidence.

Thus, this evaluation underscores an important stability advantage of backdoor-based methods, including CTCC, in practical black-box inference environments where output randomness cannot be strictly controlled.

## F Model Merging Strategies

## F.1 Task Arithmetic

Task Arithmetic (Ilharco et al., 2022) synthesizes a unified model by aggregating parameter deviations between expert models and the base model. Let θ 0 ∈ R d denote the parameters of the base model, and { θ 1 , θ 2 , . . . , θ n } represent the parameters of n homologous expert models fine-tuned from θ 0 . The task vector ∆ i for the i -th expert is defined as the parametric divergence:

<!-- formula-not-decoded -->

The merged model parameters θ TA are derived through a linear combination of these task vectors:

<!-- formula-not-decoded -->

where γ i ∈ R + denotes task-specific scaling coefficients that modulate the contribution of each expert to the integrated model.

## F.2 Ties-Merging

Ties-Merging (Yadav et al., 2024) addresses parametric interference during multi-task merging via a three-phase procedure:

- Trim (Sparsification) : For each task vector ∆ i , retain only the topk % (e.g., 20%) of parameters with the largest magnitudes, nullifying the remainder to yield sparsified vectors ˜ ∆ i .
- Elect (Sign Consensus) : Compute dimensionwise sign agreements across sparsified vectors.

| Task             | Metric   | LLaMA-2-7B   | LLaMA-2-7B   | LLaMA-2-7B   | LLaMA-2-7B   | Mistral-7B-v0.3   | Mistral-7B-v0.3   | Mistral-7B-v0.3   | Mistral-7B-v0.3   | LLaMA3-8B   | LLaMA3-8B   | LLaMA3-8B   | LLaMA3-8B   |
|------------------|----------|--------------|--------------|--------------|--------------|-------------------|-------------------|-------------------|-------------------|-------------|-------------|-------------|-------------|
| Task             | Metric   | Before       | IF           | HC           | CTCC         | Before            | IF                | HC                | CTCC              | Before      | IF          | HC          | CTCC        |
| anli_r1          | acc      | 0.363        | 0.370        | 0.365        | 0.405        | 0.384             | 0.421             | 0.402             | 0.434             | 0.339       | 0.362       | 0.356       | 0.408       |
| anli_r2          | acc      | 0.375        | 0.342        | 0.371        | 0.362        | 0.386             | 0.428             | 0.390             | 0.409             | 0.363       | 0.382       | 0.366       | 0.412       |
| anli_r3          | acc      | 0.377        | 0.373        | 0.373        | 0.372        | 0.380             | 0.437             | 0.392             | 0.413             | 0.369       | 0.381       | 0.381       | 0.399       |
| arc_challenge    | acc_norm | 0.463        | 0.449        | 0.461        | 0.468        | 0.518             | 0.516             | 0.524             | 0.499             | 0.534       | 0.538       | 0.520       | 0.507       |
| arc_easy         | acc_norm | 0.746        | 0.720        | 0.745        | 0.733        | 0.783             | 0.746             | 0.775             | 0.726             | 0.778       | 0.768       | 0.761       | 0.723       |
| openbookqa       | acc_norm | 0.442        | 0.454        | 0.432        | 0.452        | 0.444             | 0.446             | 0.434             | 0.456             | 0.450       | 0.458       | 0.442       | 0.472       |
| winogrande       | acc      | 0.691        | 0.685        | 0.688        | 0.698        | 0.738             | 0.728             | 0.728             | 0.713             | 0.735       | 0.728       | 0.728       | 0.710       |
| logiqa           | acc_norm | 0.301        | 0.280        | 0.306        | 0.318        | 0.307             | 0.329             | 0.309             | 0.341             | 0.292       | 0.296       | 0.298       | 0.315       |
| sciq             | acc_norm | 0.910        | 0.850        | 0.911        | 0.873        | 0.941             | 0.885             | 0.941             | 0.877             | 0.940       | 0.926       | 0.941       | 0.893       |
| boolq            | acc      | 0.778        | 0.772        | 0.777        | 0.796        | 0.822             | 0.843             | 0.817             | 0.836             | 0.809       | 0.825       | 0.809       | 0.804       |
| cb               | acc      | 0.429        | 0.357        | 0.429        | 0.411        | 0.536             | 0.679             | 0.607             | 0.625             | 0.554       | 0.589       | 0.363       | 0.607       |
| cola             | mcc      | -0.023       | 0.000        | -0.029       | 0.000        | -0.045            | 0.017             | -0.053            | 0.061             | -0.030      | -0.014      | -0.003      | 0.033       |
| rte              | acc      | 0.628        | 0.675        | 0.617        | 0.635        | 0.675             | 0.711             | 0.690             | 0.700             | 0.675       | 0.693       | 0.675       | 0.657       |
| wic              | acc      | 0.498        | 0.500        | 0.497        | 0.502        | 0.571             | 0.545             | 0.575             | 0.545             | 0.506       | 0.519       | 0.520       | 0.534       |
| wsc              | acc      | 0.365        | 0.404        | 0.365        | 0.394        | 0.481             | 0.433             | 0.471             | 0.548             | 0.673       | 0.510       | 0.673       | 0.663       |
| copa             | acc      | 0.870        | 0.850        | 0.870        | 0.860        | 0.910             | 0.890             | 0.920             | 0.940             | 0.900       | 0.850       | 0.890       | 0.890       |
| multirc          | acc      | 0.570        | 0.571        | 0.570        | 0.572        | 0.570             | 0.564             | 0.571             | 0.556             | 0.572       | 0.572       | 0.572       | 0.570       |
| lambada_openai   | acc      | 0.738        | 0.735        | 0.738        | 0.746        | 0.753             | 0.750             | 0.748             | 0.742             | 0.756       | 0.758       | 0.758       | 0.715       |
| lambada_standard | acc      | 0.683        | 0.681        | 0.680        | 0.684        | 0.692             | 0.709             | 0.687             | 0.692             | 0.688       | 0.696       | 0.684       | 0.634       |
| mean             | -        | 0.536        | 0.530        | 0.535        | 0.541        | 0.571             | 0.583             | 0.575             | 0.585             | 0.574       | 0.570       | 0.565       | 0.576       |

Table 8: Performance of different fingerprinting methods on LLaMA-2-7B, Mistral-7B-v0.3, and LLaMA3-8B across benchmark tasks.

Figure 6: M task and M ties visualizations showing trends under various α values.

<!-- image -->

Table 9: FSR (%) under varying topp and temperature decoding parameters. CTCC and other backdoor-based methods remain stable, while ProFlingo exhibits sensitivity due to its dependency on greedy decoding near the decision boundary.

| Top- p         | IF   | HashChain   | ProFlingo   | CTCC   |
|----------------|------|-------------|-------------|--------|
| 0.5            | 100% | 90%         | 90%         | 100%   |
| 0.6            | 100% | 90%         | 90%         | 100%   |
| 0.7 (default)  | 100% | 90%         | 84%         | 100%   |
| 0.8            | 100% | 90%         | 82%         | 100%   |
| 0.9            | 100% | 90%         | 76%         | 100%   |
| 1.0            | 100% | 90%         | 74%         | 100%   |
| Temperature    |      |             |             |        |
| 0.3            | 100% | 90%         | 100%        | 100%   |
| 0.5            | 100% | 90%         | 98%         | 100%   |
| 0.7            | 100% | 90%         | 100%        | 100%   |
| 0.95 (default) | 100% | 90%         | 84%         | 100%   |
| 1.1            | 100% | 90%         | 72%         | 100%   |
| 1.5            | 100% | 90%         | 68%         | 100%   |

For parameter index j ∈ { 1 , . . . , d } , the aggregate sign vector ζ is determined as:

<!-- formula-not-decoded -->

where ˜ ∆ ( j ) i denotes the j -th dimension of ˜ ∆ i .

- Disjoint Merge : Retain only parameters in ˜ ∆ i aligning with ζ j , then compute their weighted average to construct the consolidated task vector ¯ ∆ :

<!-- formula-not-decoded -->

Table 10: Robustness evaluation of fingerprinting methods under M task and M DARE task model fusion.

|         | M task   | M task    | M task    | M task   | M DARE task   | M DARE task   | M DARE task   | M DARE task   |
|---------|----------|-----------|-----------|----------|---------------|---------------|---------------|---------------|
| RATE    | IF       | HashChain | ProFlingo | CTCC     | IF            | HashChain     | ProFlingo     | CTCC          |
| 0.9:0.1 | 100%     | 90%       | 100%      | 100%     | 100%          | 90%           | 100%          | 100%          |
| 0.8:0.2 | 100%     | 90%       | 100%      | 100%     | 100%          | 90%           | 100%          | 100%          |
| 0.7:0.3 | 25%      | 90%       | 98%       | 100%     | 12.5%         | 90%           | 96%           | 100%          |
| 0.6:0.4 | 0%       | 90%       | 96%       | 100%     | 0%            | 90%           | 94%           | 100%          |
| 0.5:0.5 | 0%       | 80%       | 88%       | 98%      | 0%            | 80%           | 86%           | 99%           |
| 0.4:0.6 | 0%       | 60%       | 68%       | 67%      | 0%            | 50%           | 68%           | 74%           |
| 0.3:0.7 | 0%       | 10%       | 64%       | 7%       | 0%            | 10%           | 66%           | 13%           |
| 0.2:0.8 | 0%       | 0%        | 62%       | 0%       | 0%            | 0%            | 64%           | 0%            |
| 0.1:0.9 | 0%       | 0%        | 52%       | 0%       | 0%            | 0%            | 52%           | 0%            |

Table 11: Robustness evaluation of fingerprinting methods under M ties and M DARE TIES model fusion.

|         | M ties   | M ties    | M ties    | M ties   | M DARE ties   | M DARE ties   | M DARE ties   | M DARE ties   |
|---------|----------|-----------|-----------|----------|---------------|---------------|---------------|---------------|
| RATE    | IF       | HashChain | ProFlingo | CTCC     | IF            | HashChain     | ProFlingo     | CTCC          |
| 0.9:0.1 | 12.5%    | 0%        | 64%       | 100%     | 12.5%         | 10%           | 32%           | 100%          |
| 0.8:0.2 | 0%       | 0%        | 64%       | 100%     | 0%            | 0%            | 46%           | 100%          |
| 0.7:0.3 | 0%       | 0%        | 64%       | 100%     | 0%            | 0%            | 38%           | 99%           |
| 0.6:0.4 | 0%       | 0%        | 64%       | 100%     | 0%            | 0%            | 44%           | 100%          |
| 0.5:0.5 | 0%       | 0%        | 64%       | 100%     | 0%            | 0%            | 40%           | 99%           |
| 0.4:0.6 | 0%       | 0%        | 64%       | 100%     | 0%            | 0%            | 44%           | 99%           |
| 0.3:0.7 | 0%       | 0%        | 64%       | 99%      | 0%            | 0%            | 36%           | 99%           |
| 0.2:0.8 | 0%       | 0%        | 64%       | 98%      | 0%            | 0%            | 40%           | 99%           |
| 0.1:0.9 | 0%       | 0%        | 64%       | 96%      | 0%            | 0%            | 40%           | 99%           |

This process mitigates sign conflicts and redundancies, enhancing the stability of the merged model.

## F.3 DARE with Task Arithmetic

The D rop A nd RE scale (DARE) (Yu et al., 2024) framework augments merging by introducing sparsity through stochastic parameter pruning. For each task vector ∆ i :

- Drop : Randomly nullify parameters in ∆ i via Bernoulli sampling with retention probability p , yielding a pruned vector ∆ ′ i with support S i ⊆ { 1 , . . . , d } .
- Rescale : Compensate for parameter dropout by rescaling retained values:

<!-- formula-not-decoded -->

where ⊙ denotes element-wise multiplication.

Integrating DARE with Task Arithmetic yields the merged parameters:

<!-- formula-not-decoded -->

The dropout mechanism suppresses task-specific redundancies, while rescaling preserves the expected magnitude of critical parameters.

## G Extended Experimental Results and Supplementary Discussion

In this appendix, we present additional experiments and in-depth analyses to further validate the reliability, generality, and practical robustness of the proposed CTCC method. The following subsections report results on (i) extended multi-turn experiments, (ii) full-parameter fine-tuning (full-FT), and (iii) evaluation on larger and more recent models. We further supplement analyses regarding seen/unseen trigger generalization, error cases, and potential impacts on user experience.

## G.1 Three-Turn Trigger Evaluation

To explore the performance of CTCC in more complex dialogue settings, we extend the two-turn trigger configuration into a three-turn dialogue setup, denoted as ( j = 1 , i = 3) . Experiments were conducted using LLaMA-2-7B across four key evaluation dimensions: (i) trigger effectiveness, (ii) harmlessness, (iii) model merging robustness, and (iv) incremental fine-tuning robustness. For clarity, Tables 12-15 report results for both the original two-turn configuration and the extended three-turn setup, enabling a direct comparison between the two settings.

Table 12: Comparison of Fingerprint Success Rate (FSR) between two-round and three-round triggers.

| Setting   |   Two-Round |   Three-Round |
|-----------|-------------|---------------|
| FSR (%)   |      100.00 |        100.00 |

To mitigate overfitting and strengthen robustness against backdoor activations, we extended the suppression dataset to cover three classes of negative instances: (1) triggers followed by semantically consistent third turns, (2) counterfactual relations between the second and third turns, and (3) counterfactual relations between the first and second turns. Furthermore, 1,000 natural multi-turn conversations were included as a regularization set. All evaluations were conducted on LLaMA-2-7bhf to maintain strict comparability with the main experiments.

The key observations are as follows:

- Effectiveness and Harmlessness: As shown in Tables 12 and 13, the three-turn trigger maintains a 100% FSR under LoRA tuning, while harmlessness remains stable and comparable to the two-turn setting.
- Merging Robustness: Table 14 illustrates that robustness under model fusion shows a slight decline in the three-turn configuration compared to the two-turn setup, reflecting the increased complexity and reduced stability associated with multi-turn rule activation.
- Incremental Fine-Tuning Robustness: As summarized in Table 15, incremental finetuning introduces minor interference, with the three-turn setting experiencing slightly lower robustness relative to the two-turn baseline.

Overall, the three-turn setup introduces a clear trade-off: greater stealthiness (due to higher dialogue complexity and a lower likelihood of accidental activation) at the expense of marginal reductions in robustness. Including both two-turn and threeturn results in the tables highlights that while the extended configuration sacrifices a small degree of robustness, it preserves the strong effectiveness and harmlessness properties of the original two-turn design.

Table 13: Harmlessness evaluation for original, tworound, and three-round triggers.

| Task           |   Original |   Two-Round |   Three-Round |
|----------------|------------|-------------|---------------|
| anli_r1        |      0.363 |       0.405 |         0.377 |
| anli_r2        |      0.375 |       0.362 |         0.387 |
| anli_r3        |      0.377 |       0.372 |         0.369 |
| arc_challenge  |      0.463 |       0.468 |         0.486 |
| arc_easy       |      0.746 |       0.733 |         0.729 |
| openbookqa     |      0.442 |       0.452 |         0.446 |
| winogrande     |      0.691 |       0.699 |         0.672 |
| logiqa         |      0.301 |       0.318 |         0.316 |
| sciq           |      0.910 |       0.873 |         0.913 |
| boolq          |      0.778 |       0.796 |         0.790 |
| cb             |      0.429 |       0.411 |         0.571 |
| cola           |     -0.023 |       0.000 |        -0.010 |
| rte            |      0.628 |       0.635 |         0.646 |
| wic            |      0.498 |       0.502 |         0.509 |
| wsc            |      0.365 |       0.394 |         0.510 |
| copa           |      0.870 |       0.860 |         0.870 |
| multirc        |      0.570 |       0.572 |         0.570 |
| lambada_openai |      0.738 |       0.746 |         0.723 |
| lambada_std    |      0.683 |       0.684 |         0.617 |
| Average        |      0.536 |       0.541 |         0.552 |

## G.2 Full-Parameter Fine-Tuning on LLaMA-2-7B

To assess the generality of CTCC across different fine-tuning strategies, we further performed fullparameter fine-tuning (full-FT) on LLaMA-2-7b-hf. The results, summarized in Tables 16, 17, 18, and 19, reveal several notable patterns:

- Effectiveness (Table 16): Full-FT consistently yields a 100% FSR across all test scenarios, confirming that CTCC can be effectively integrated even under high-capacity fine-tuning.
- Robustness (Tables 17 and 18): Compared to LoRA, full-FT models exhibit stronger resistance to incremental fine-tuning and fusion-based transformations, demonstrating enhanced stability in the fingerprint embedding.
- Utility-Performance Trade-off (Table 19): A mild reduction in general task performance is observed after full-FT, consistent with findings from prior fingerprinting and backdoor literature. This indicates a trade-off between robustness and general usability.

These findings demonstrate that CTCC is compatible with both lightweight (LoRA) and heavyweight (full-FT) fine-tuning paradigms, providing flexibility for different deployment scenarios.

| RATE    | Task       | Task         | Dare-Task   | Dare-Task    | Tie        | Tie          | Dare-Tie   | Dare-Tie     |
|---------|------------|--------------|-------------|--------------|------------|--------------|------------|--------------|
| RATE    | Two- Round | Three- Round | Two- Round  | Three- Round | Two- Round | Three- Round | Two- Round | Three- Round |
| 0.9:0.1 | 100%       | 100%         | 100%        | 100%         | 100%       | 100%         | 100%       | 100%         |
| 0.8:0.2 | 100%       | 100%         | 100%        | 100%         | 100%       | 100%         | 100%       | 100%         |
| 0.7:0.3 | 100%       | 100%         | 100%        | 100%         | 100%       | 99%          | 100%       | 100%         |
| 0.6:0.4 | 100%       | 100%         | 100%        | 100%         | 100%       | 100%         | 100%       | 100%         |
| 0.5:0.5 | 98%        | 100%         | 99%         | 100%         | 100%       | 99%          | 100%       | 100%         |
| 0.4:0.6 | 67%        | 60%          | 74%         | 70%          | 100%       | 100%         | 99%        | 100%         |
| 0.3:0.7 | 7%         | 5%           | 13%         | 10%          | 99%        | 90%          | 99%        | 90%          |
| 0.2:0.8 | 0%         | 0%           | 0%          | 0%           | 98%        | 90%          | 99%        | 90%          |
| 0.1:0.9 | 0%         | 0%           | 0%          | 0%           | 96%        | 70%          | 99%        | 75%          |

Table 14: Model fusion robustness under varying mixing ratios for four evaluation tasks. Two-Round and ThreeRound indicate the corresponding trigger configurations.

| Method   | Downstream Dataset   | Two Round   | Three Round   |
|----------|----------------------|-------------|---------------|
| CTCC     | Alpaca_52k           | 41.1%       | 35%           |
| CTCC     | ShareGPT_6k          | 90.5%       | 75%           |
| CTCC     | Dolly_en_15k         | 96.8%       | 70%           |

Table 15: Robustness of the CTCC method under incremental fine-tuning with different downstream datasets, comparing the two-round and three-round trigger settings.

Table 16: Effectiveness evaluation under LoRA and fullparameter fine-tuning settings.

| Metric   | LoRA Fine-tuning   | Full-Parameter Fine-tuning   |
|----------|--------------------|------------------------------|
| FSR      | 100.00%            | 100.00%                      |

Table 17: Comparison of CTCC performance under LoRA and full-parameter fine-tuning across downstream datasets.

| Method   | Downstream Dataset   | Performance (%)   | Performance (%)   |
|----------|----------------------|-------------------|-------------------|
|          |                      | LoRA              | Full              |
| CTCC     | Alpaca_52k           | 41.1              | 100               |
| CTCC     | ShareGPT_6k          | 90.5              | 100               |
| CTCC     | Dolly_en_15k         | 96.8              | 100               |

## G.3 Evaluation on Qwen2.5-14B

To assess the scalability and generality of CTCC on the more powerful Qwen2.5-14B (Team, 2024) architecture, we conducted a series of evaluations:

- Effectiveness: CTCC consistently achieves 100% FSR, indicating reliable trigger activation even in large-scale models.
- Harmlessness: Table 20 presents the comparison of model capabilities before and after fingerprint embedding, demonstrating that CTCC preserves general task performance while maintaining robustness.
- Model Fusion Robustness: Using the same

fusion configuration as prior experiments (four strategies: Task, Dare-Task, Tie, and Dare-Tie), we fused Qwen2.5-14B models based on the embedding fingerprint with the Qwen2.5-14B-Instruct (Team, 2024) model in varying proportions. Results in Table 21 confirm that CTCC maintains robust performance under model fusion, consistent with observations on smaller models.

- Incremental Fine-Tuning Robustness: Applying the same incremental fine-tuning procedures (Alpaca, Dolly, ShareGPT), CTCC demonstrates strong robustness on larger models as well, with high FSR preserved across all datasets (see Table 22).

These findings confirm that CTCC scales effectively to larger parameter models and recent architectures, maintaining reliable fingerprint activation, task preservation, and robustness under both model fusion and incremental fine-tuning.

## G.4 Analysis of Turn Intervals in Trigger Configurations

An important consideration in multi-turn backdoor configurations is how the interval between triggering turns influences model behavior. This interval can be understood in two complementary ways: (i) as the number of dialogue turns separating the triggering positions, and (ii) as the semantic content filling those intermediate turns. We analyze both aspects below.

Table 18: Robustness evaluation of LoRA and Full-parameter fine-tuned models under model fusion across four tasks (Task, Dare-Task, Tie, Dare-Tie).

| RATE    | Task   | Task   | Dare-Task   | Dare-Task   | Tie   | Tie   | Dare-Tie   | Dare-Tie   |
|---------|--------|--------|-------------|-------------|-------|-------|------------|------------|
|         | LoRA   | Full   | LoRA        | Full        | LoRA  | Full  | LoRA       | Full       |
| 0.9:0.1 | 100%   | 100%   | 100%        | 100%        | 100%  | 100%  | 100%       | 100%       |
| 0.8:0.2 | 100%   | 100%   | 100%        | 100%        | 100%  | 100%  | 100%       | 100%       |
| 0.7:0.3 | 100%   | 100%   | 100%        | 100%        | 100%  | 99%   | 100%       | 100%       |
| 0.6:0.4 | 100%   | 100%   | 100%        | 100%        | 100%  | 100%  | 100%       | 100%       |
| 0.5:0.5 | 98%    | 100%   | 99%         | 100%        | 100%  | 99%   | 100%       | 100%       |
| 0.4:0.6 | 67%    | 98.9%  | 74%         | 100%        | 100%  | 100%  | 99%        | 100%       |
| 0.3:0.7 | 7%     | 81.1%  | 13%         | 85.3%       | 99%   | 100%  | 99%        | 100%       |
| 0.2:0.8 | 0%     | 14.7%  | 0%          | 12.6%       | 98%   | 100%  | 99%        | 100%       |
| 0.1:0.9 | 0%     | 0%     | 0%          | 0%          | 96%   | 100%  | 99%        | 100%       |

Table 19: Harmlessness evaluation across Original, LoRA fine-tuned, and full-parameter fine-tuned models.

| Task             |   Original |   LoRA Fine-tuning |   Full-Parameter Fine-tuning |
|------------------|------------|--------------------|------------------------------|
| anli_r1          |      0.363 |              0.405 |                        0.380 |
| anli_r2          |      0.375 |              0.362 |                        0.369 |
| anli_r3          |      0.377 |              0.372 |                        0.400 |
| arc_challenge    |      0.463 |              0.468 |                        0.393 |
| arc_easy         |      0.746 |              0.733 |                        0.639 |
| openbookqa       |      0.442 |              0.452 |                        0.424 |
| winogrande       |      0.691 |              0.699 |                        0.653 |
| logiqa           |      0.301 |              0.318 |                        0.258 |
| sciq             |      0.910 |              0.873 |                        0.812 |
| boolq            |      0.778 |              0.796 |                        0.786 |
| cb               |      0.429 |              0.411 |                        0.179 |
| cola             |     -0.023 |              0.000 |                       -0.027 |
| rte              |      0.628 |              0.635 |                        0.733 |
| wic              |      0.498 |              0.502 |                        0.500 |
| wsc              |      0.365 |              0.394 |                        0.365 |
| copa             |      0.870 |              0.860 |                        0.830 |
| multirc          |      0.570 |              0.572 |                        0.572 |
| lambada_openai   |      0.738 |              0.746 |                        0.703 |
| lambada_standard |      0.683 |              0.684 |                        0.631 |
| Average          |      0.536 |              0.541 |                        0.505 |

## G.4.1 Effect of interval length.

As shown in the three-turn experiments in Appendix G.1, enlarging the gap between triggering turns (e.g., adopting i = 3 , j = 1 instead of i = 2 , j = 1 ) may reduce robustness. This decrease is likely attributable to increased semantic dispersion and higher contextual complexity, which together weaken the persistence of the backdoor signal across dialogue turns.

## G.4.2 Effect of intermediate content.

To examine whether the semantic material between trigger turns affects fingerprint activation, we performed additional experiments on the three-turn test set in which the first and third turns formed a counterfactual trigger. For each sample, we randomly modified the intermediate (second) turn five times. Across all variations, the model consistently achieved an FSR of 100%. These results indicate that the effectiveness of CTCC triggers is insensitive to the specific content of intermediate dialogue turns and primarily depends on the placement of the trigger configuration.

In summary, while the distance between triggering turns can attenuate robustness, the presence or variation of intermediate content exerts negligible influence on trigger activation.

| Task                                                                                                            | Original                                                                                        | After                                                                                           |
|-----------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| anli_r1 anli_r2 anli_r3 arc_challenge arc_easy openbookqa winogrande logiqa sciq boolq cb cola rte wic wsc copa | 0.555 0.525 0.527 0.584 0.813 0.438 0.738 0.363 0.956 0.856 0.750 0.474 0.773 0.513 0.663 0.920 | 0.608 0.527 0.527 0.583 0.817 0.456 0.721 0.341 0.948 0.861 0.839 0.504 0.791 0.575 0.769 0.940 |
| multirc                                                                                                         | 0.342                                                                                           | 0.215                                                                                           |
| Average                                                                                                         | 0.635                                                                                           | 0.648                                                                                           |

Table 20: Harmlessness evaluation comparing model performance before and after embedding CTCC fingerprints across standard tasks.

| RATE    | Task   | Dare-Task   | Tie   | Dare-Tie   |
|---------|--------|-------------|-------|------------|
| 0.9:0.1 | 100%   | 100%        | 100%  | 95.8%      |
| 0.8:0.2 | 100%   | 100%        | 100%  | 93.7%      |
| 0.7:0.3 | 100%   | 100%        | 93.7% | 92.6%      |
| 0.6:0.4 | 100%   | 98.9%       | 89.5% | 88.4%      |
| 0.5:0.5 | 92.6%  | 91.6%       | 87.4% | 86.3%      |
| 0.4:0.6 | 74.7%  | 72.6%       | 84.2% | 82.1%      |
| 0.3:0.7 | 42.1%  | 36.8%       | 80%   | 80%        |
| 0.2:0.8 | 1.05%  | 0%          | 70.5% | 83.2%      |
| 0.1:0.9 | 0%     | 0%          | 36.8% | 51.6%      |

Table 21: Fusion robustness of Qwen2.5-14B when merged with Qwen2.5-14B-Instruct under four model fusion strategies (Task, Dare-Task, Tie, Dare-Tie) using CTCC embedding fingerprints at varying mixing ratios.

Table 22: Incremental fine-tuning robustness of Qwen2.5-14B evaluated with CTCC embedding fingerprints on multiple downstream datasets. The table shows that CTCC consistently achieves full FSR across all tested datasets.

| Downstream Dataset   | FSR   |
|----------------------|-------|
| Alpaca_52k           | 100%  |
| ShareGPT_6k          | 100%  |
| Dolly_en_15k         | 100%  |

Table 23: FSR of CTCC on seen and unseen triggers, evaluated across three mainstream LLMs (LLaMA2, Mistral, LLaMA3) and three downstream datasets (Alpaca 52k, ShareGPT 6k, Dolly 15k).

| Downstream Dataset   | LLaMA2   | LLaMA2   | Mistral   | Mistral   | LLaMA3   | LLaMA3   |
|----------------------|----------|----------|-----------|-----------|----------|----------|
|                      | Seen     | Unseen   | Seen      | Unseen    | Seen     | Unseen   |
| Alpaca (52k)         | 20/48    | 19/47    | 48/48     | 47/47     | 48/48    | 47/47    |
| ShareGPT (6k)        | 48/48    | 38/47    | 44/48     | 30/47     | 48/48    | 41/47    |
| Dolly (15k)          | 48/48    | 44/47    | 48/48     | 47/47     | 48/48    | 47/47    |