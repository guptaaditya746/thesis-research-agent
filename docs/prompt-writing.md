# Prompt writing and verification

Repository policy adopted on 21 October 2026 at the user's request. Apply it to future prompt changes and model workflows. The EV1 diagnosis and research handoff describe suggested implementations; adopting this policy does not change previously frozen protocols or completed experiments.

## Define the contract before writing the prompt

Give each model call one coherent task and one typed output. Write down its purpose, the fields it receives, what each field means, the allowed output values, and the conditions for accepting the result. Show missing information explicitly. Give the model the source material needed for this task and pass validated outputs between workflow stages.

Use code for arithmetic, unit conversion, schema checks, source anchoring, routing, stopping conditions, and artifact hashes. Use models for interpreting text, proposing wording, or extracting facts whose expression varies. A model's explanation of an engine setting must agree with the executable setting.

Split a prompt when it mixes tasks with different acceptance conditions, such as writing facts, checking facts, choosing research policy, and presenting conclusions. Keep tightly related fields together when separation would lose essential context. Measure quality, calls, latency, and tokens before retaining extra stages.

## Write prompts for the smaller deployed models

Use short, direct instructions and stable field names. State the task first, then the input definitions, output schema, a few representative examples, and acceptance rules. Describe the desired behavior positively. Keep hard constraints explicit and validate them in code.

Provide examples showing a normal case, a known confusing case, and missing or ambiguous information. Match the examples to the actual output schema and deployed model. Include observed failures such as `RAG (no retrieval)`, an absent comparator, percentages versus fractions, and overlapping metric names. Examples should demonstrate the rule, rather than tell the model which benchmark answer to favor.

Ask for a short source quote or one checkable reason when the task needs evidence. Bound the output and represent uncertainty explicitly. Avoid unsupported claims that a setting is standard, statistically significant, exhaustive, or preserves recall.

## Example: one condition classification task

This is a proposed interface, not a replacement for the current extractor schema. The caller supplies the two role definitions and maps a checked decision into the protocol's canonical role ids.

Task: classify one condition from its stated use of external retrieval.

Input fields: `condition_id` is the caller's identifier; `text` is the source passage; `treatment` and `control` define the compared roles.

Output: `condition_id`, `decision` (`treatment`, `control`, `other`, or `unknown`), and `evidence` (a verbatim substring, or null for unknown). Return unknown when the passage does not establish the condition's behavior.

Example inputs and outputs:

```json
{"condition_id":"c1","text":"The RAG system retrieves passages before answering.","treatment":"uses external retrieval","control":"answers without retrieval"}
{"condition_id":"c1","decision":"treatment","evidence":"retrieves passages before answering"}
```

```json
{"condition_id":"c2","text":"RAG (no retrieval) answers from its model parameters.","treatment":"uses external retrieval","control":"answers without retrieval"}
{"condition_id":"c2","decision":"control","evidence":"no retrieval"}
```

```json
{"condition_id":"c3","text":"System Alpha answers the questions.","treatment":"uses external retrieval","control":"answers without retrieval"}
{"condition_id":"c3","decision":"unknown","evidence":null}
```

The caller validates the id, decision, and quote. An unknown result remains unresolved and can enter a targeted verification stage.

## Separate generation and verification

Use one model to generate and another model to verify the result against the source and acceptance contract. A blind extraction verifier receives the generated text and extraction task, then code compares its output with the private expected facts. A reviewer of a proposed decision receives the relevant input, proposal, and executable semantics, but no generator rationale that would encourage agreement.

For the present stack, the proposed allocation is `orch-model` for generation and a sub-model for verification; the second sub-model can independently verify or help examine disagreements. `sub-model-1` and `sub-model-2` serve the same model weights, so agreement between them is correlated evidence. Keep deterministic checks and human review of research policy. Keep one orch workload at a time and record the actual served model identities.

Validate the complete fact: condition, metric, dataset, normalized value, unit, and supporting source span. A correct number attached to the wrong metric is a failed verification. Define handling for contradictions, missing facts, and abstention before running the workflow. Preserve both verifier outputs when they disagree; disagreement is a result to investigate.

Give a repair call only the failed task, rejected output, and specific failed checks. Bound the retries and keep each attempt. A fresh seed at temperature zero does not establish a useful repair. Accept a repair only after validation; freezing records a proposal and does not imply human approval.

## Evaluate and record changes

Before editing, preserve a failing example and its observed output. Compare the current prompt with the candidate on the same development cases. Record prompt and schema hashes, settings, model identity, attempts, validation results, token use, latency, and retained artifacts. Report what was actually executed and distinguish observed failures from hypotheses and proposed experiments.

Keep entire study families together when splitting data: renderings at every level, duplicates, and counterfactuals belong to the same split. Lock an untouched test set before optimization. Keep generation, extraction, and verification evaluations distinct so a prompt cannot improve its score by producing easier benchmark cases or changing the intended outcomes.

Version a behavior-changing prompt and preserve its predecessor. A proposed setting needs an empirical comparison; passing a JSON schema alone establishes output shape. Run deterministic checks and independent model verification on the deployed models before claiming a prompt improves the workflow.

DSPy is a possible development tool for optimizing prompts against fixed metrics and separate validation data. Evaluate it in an isolated experiment after the contracts and metrics are sound; keep the research policy, validators, and held-out evaluation fixed. The intended pilot and its limits are in the EV1 diagnosis (`docs/ev1-review-diagnosis.md` at tag `pre-restructure`).
