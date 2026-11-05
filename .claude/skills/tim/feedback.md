# Supervisor (Tim) feedback, verbatim. Two messages, both received 14 Oct 2026.

## Message 1 (earlier, 14 Oct): answer-level vs evidence-level

Thanks for the reminder. I did not talk to Benno, yet, but I've been thinking further about our discussion on the distinction between simple and complex concepts or questions. I now believe that this distinction is not really the central issue. Instead, what matters is how a system approaches answering a research question.

Consider the question: "How influential was a particular scientist in their field?"

There are two fundamentally different approaches:

1. Answer-level reasoning (what we previously considered "simple")

The system searches for existing statements that directly address the question, such as "Einstein was one of the most influential physicists of the 20th century." It then aggregates, compares, or summarizes these assessments. This can involve sophisticated reasoning, but the system primarily relies on conclusions already expressed in the literature.

2. Evidence-level reasoning (what we previously considered "complex")

Rather than looking for explicit answers, the system asks what evidence would be needed to answer the question independently. For example, it could identify a scientist's contributions, examine how subsequent research built upon them, and assess their impact on the development of the field. The system then synthesizes an answer from these underlying observations, even if no document explicitly states that answer.

Importantly, these approaches are not mutually exclusive. Existing assessments can also be considered as evidence. The key difference is that evidence-level reasoning does not depend on finding an existing answer in the literature.

I think this should become the central direction of our work. Instead of focusing on how to decompose complex concepts into simple ones, we should investigate how to operationalize research questions into explicit evidence requirements.

The idea is that the system develops a plan for which evidence to collect, extracts the relevant information from scientific documents, and synthesizes a traceable, evidence-based answer. Ideally, this plan would be explicit, reproducible, and potentially refined through interaction with the user, much like a protocol in a systematic review.

This also gives us a clearer direction for the master's thesis: building a technical prototype of such a system and evaluating selected components, particularly how reliably and comprehensively relevant evidence can be extracted from a scientific corpus.

I think this is a more promising and scientifically meaningful direction than trying to define precisely when a concept is "simple" or "complex".

## Message 2 (later, 14 Oct): sections 1-9

I've been thinking further about our approach, particularly the distinction between simple and complex concepts, the role of SPARQL, and how we could evaluate a first prototype. I think we now have a clearer research direction, and I would suggest adjusting the architecture and evaluation accordingly.
1. From complex concepts to evidence-level reasoning
We initially discussed translating research questions into SPARQL queries with an unrestricted vocabulary and then decomposing complex concepts into simpler ones that can be reliably extracted from documents.
I now think the distinction between simple and complex concepts is not really the central issue. Instead, we should distinguish between two approaches to answering research questions.
Consider the question:
How influential was a particular scientist in their field?
Answer-level reasoning would search for existing statements about the scientist's influence and summarize or aggregate these assessments.
Evidence-level reasoning, which is what we want to pursue, would instead examine the scientist's scientific contributions, investigate how subsequent research built upon them, and derive an assessment of their influence from these observations.
The key difference is that evidence-level reasoning should allow the system to reach conclusions that are not explicitly stated in any individual document. Existing assessments may still be incorporated as additional evidence, but the system should not depend on finding an existing answer.
This shifts our focus from decomposing complex concepts into simple ones toward operationalizing research questions into explicit evidence requirements.
2. From research questions to executable research protocols
I would therefore reconsider our initial idea of translating the research question directly into SPARQL.
Instead, I suggest introducing an intermediate representation: an executable research protocol.
The protocol describes how the research question should be investigated, including:
- What types of evidence are needed.
- How the evidence should be extracted from the documents.
- How the extracted information should be represented and connected.
- How the evidence should be synthesized into an answer, including supporting and contradicting evidence.
The operationalization could eventually be performed by an LLM, potentially involving a dialogue with the user to clarify methodological decisions.
I find a compiler analogy helpful:
Natural-language research question
↓
Protocol generation (LLM, potentially with user interaction)
↓
Executable research protocol
↓
Execution engine
↓
Evidence graph and synthesized answer
The research question is the high-level input, while the research protocol acts as an intermediate representation specifying how the investigation should be conducted.
Importantly, we no longer need to define the complete graph structure at the beginning. The relevant entities and relations emerge during the operationalization.
For the implementation, I would currently favor a declarative protocol representation (e.g., YAML or JSON), executed by a Python-based engine. SPARQL could still be useful for querying the resulting evidence graph, but it does not need to be the central language of the system.
3. Reusable evidence extractors
The system should maintain a library of reusable extractors, each responsible for identifying a particular type of evidence in scientific documents.
These extractors could use regular expressions, specialized models, LLMs, or other methods. Their implementations should be interchangeable.
Over time, the extractor library could grow and its components could be continuously benchmarked. Ideally, most research protocols would reuse existing extractors rather than requiring new ones.
For the master's thesis, a small library with a common interface and a few example extractors should be sufficient.
4. A concrete use case
For a first prototype, I suggest a relatively well-defined research question:
Does retrieval-augmented generation (RAG) improve the factual accuracy of LLM-generated answers?
An answer-level system might retrieve papers concluding that RAG improves factuality and summarize these statements.
Our evidence-level system should instead extract the underlying experimental evidence:
- Which models and experimental conditions were compared?
- Was RAG compared against a baseline without retrieval?
- Which metrics were used to measure factual accuracy?
- What were the reported results?
- Which experiments showed improvements, no effect, or deterioration?
The system would then synthesize an answer from the extracted results, rather than primarily relying on the authors' conclusions.
This example is useful because the relevant evidence can be represented in a relatively structured form and the synthesis can initially be implemented using deterministic procedures.
5. Evaluation using a synthetic scientific corpus
I have also been thinking about how we could evaluate the prototype without first having to manually annotate a large collection of scientific papers.
I suggest generating a synthetic corpus of scientific papers from a structured ground-truth model.
Importantly, we should not simply ask an LLM to generate arbitrary scientific papers. Instead, we should reverse the process:
Ground-truth scientific data → Synthetic papers
We first generate a structured collection of fictional studies, experiments, experimental conditions, and results.
For example, the ground truth could specify that a particular experiment compared an LLM with and without retrieval augmentation, achieving factual accuracy scores of 0.68 and 0.82, respectively.
An LLM would then generate a realistic scientific paper reporting these results. The information could appear in the abstract, methodology, results section, or tables.
Because we generated the underlying data, we know exactly which evidence the corpus is intended to contain.
This would allow us to evaluate several aspects of the system independently.
A. Evidence extraction
We can measure how accurately and completely the system reconstructs the underlying experimental evidence.
Relevant metrics include precision, recall, F1, correct association of measurements with experimental conditions, and the accuracy of evidence provenance.
B. Evidence integration
We can evaluate whether evidence from different sections or documents is correctly connected.
For example, a paper might describe the experimental conditions in one section and report the corresponding measurements in a table elsewhere.
We could also introduce multiple experiments per paper, repeated results, or dependencies between studies.
C. Evidence synthesis
Since we know all the underlying experimental results, we can independently calculate the expected synthesis.
We can then evaluate whether the system reaches the correct conclusions from the extracted evidence.
Importantly, this also allows us to distinguish extraction errors from synthesis errors.
6. Controlling the difficulty of the benchmark
A particularly interesting aspect of this approach is that we could systematically vary the difficulty of the synthetic corpus.
For example:
- Explicit evidence: Results are stated directly in a sentence.
- Paraphrased evidence: The same information is expressed using different terminology.
- Distributed evidence: Experimental conditions and results appear in different sections.
- Complex evidence: Papers contain multiple experiments, models, datasets, and metrics.
- Contradictory evidence: Authors' conclusions do not fully agree with their reported measurements.
We could also introduce duplicated studies, missing information, methodological limitations, or individual studies with unusually large effects.
A further possibility would be to generate controlled variants of the same corpus. For example, changing the result of one study should affect the synthesized answer in a predictable way.
This would allow us to test whether the system actually responds to changes in the underlying evidence.
Of course, we would need to validate that the generated papers faithfully represent the ground truth. The generator's intended content alone is not sufficient; the final documents must be checked for unintended additions, omissions, or contradictions.
7. Comparing answer-level and evidence-level reasoning
The synthetic corpus would also allow us to investigate our central conceptual distinction experimentally.
We could compare two approaches using the same documents and research question:
Baseline: A conventional LLM-based question-answering system that retrieves relevant passages and directly synthesizes an answer.
Our approach: A protocol-driven system that extracts structured evidence, constructs an evidence representation, and synthesizes the answer from that evidence.
We could then compare their correctness, completeness, and traceability.
A particularly interesting test would be to generate papers in which the authors' conclusions are overly optimistic or otherwise inconsistent with the reported experimental results.
An answer-level system might reproduce these conclusions, while an evidence-level system should ideally identify the discrepancy.
We should not assume that the evidence-level approach will necessarily perform better. Establishing whether, and under which conditions, it provides an advantage would be an interesting research result.
8. Proposed scope of the master's thesis
I suggest implementing a complete but deliberately limited prototype, with the synthetic benchmark as the main evaluation instrument.
The development could proceed in the following order:
1. Define one research question and a corresponding protocol manually. We do not need automatic protocol generation initially.
2. Implement the synthetic corpus generator. Start from structured experimental data and generate scientific papers while retaining the ground truth.
3. Implement a small extractor library. Focus on experimental conditions, evaluation metrics, and reported results.
4. Construct a structured evidence representation. Preserve the connections between studies, experiments, measurements, and source passages.
5. Implement a simple evidence synthesis procedure. Derive an answer from the extracted results using explicit rules.
6. Evaluate extraction, integration, and synthesis separately. Use the synthetic ground truth to identify where errors occur.
7. Compare against an answer-level baseline. Investigate whether explicit evidence extraction and synthesis improve the quality of the answers.
If time permits, we could additionally implement a simple LLM-based protocol generator and test the system on a small collection of real scientific papers.
However, I would not make either of these extensions a requirement for completing the thesis.
9. What I see as the main research contribution
The thesis would demonstrate the feasibility of a system that transforms scientific research questions into executable evidence acquisition and synthesis workflows.
Its main empirical contribution would be a controlled evaluation of the pipeline using synthetic scientific literature with known ground truth.
This would allow us to investigate not only whether the system produces correct answers, but also why it succeeds or fails: whether relevant evidence was missed, relationships were reconstructed incorrectly, or the synthesis itself was flawed.
The synthetic benchmark could also become a reusable resource for future research. We could extend it with more complex evidence structures, alternative research questions, and more demanding synthesis tasks.
In the longer term, the goal would be a system that supports transparent, reproducible scientific investigations, somewhat analogous to systematic reviews, while also enabling new conclusions to be derived from existing scientific literature.
For now, I think we should focus on implementing and evaluating a complete vertical slice of this architecture rather than trying to solve the general problem of automatic research question operationalization immediately.
Best,
Tim
