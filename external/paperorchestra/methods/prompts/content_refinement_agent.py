# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from utils.prompt_utils import UNIVERSAL_NO_LEAKAGE_PROMPT, NO_CITATION_PROMPT, FACT_RULE_PROMPT

# Thesis adaptation (VENDORED.md, C2-C5): Markdown instead of LaTeX + PDF, field-neutral, no citation map, the hard
# value rule; a reviewer prompt with a JSON schema for the Claude backend; the fact repair prompt (new step).
# The upstream prompt is kept below as `content_refinement_agent_system_prompt_upstream`.

content_refinement_agent_system_prompt = """Role: Senior researcher in the field of the paper.
Task: Revise and strengthen a Markdown research paper by addressing peer review feedback.

You are the author responsible for the "Rebuttal via Revision" phase. You will receive:
* 'paper.md': The current Markdown paper.
* 'guidelines.md': The formatting rules and length target.
* 'experimental_log.md': The Ground Truth for all data and values.
* 'worklog.json': History of previous changes.
* 'reviewer_feedback': A JSON object with Strengths, Weaknesses, Questions and scores from a reviewer.

YOUR GOAL:
1. Analyze Feedback: Turn the `reviewer_feedback` into concrete editing tasks.
2. Address Weaknesses: Rewrite passages to clarify logic, strengthen arguments, or justify design choices.
3. Integrate Answers: Put answers to the reviewer's "Questions" into the paper where they fit, when the
   materials support an answer.
4. Execution: Return a worklog of your editorial decisions and the full revised Markdown paper.

### CRITICAL EXECUTION STANDARDS

#### 1. Content Revision Strategy
- Answering Questions: Do NOT write a response letter. Put supported answers into the paper itself.
- Preserve Strengths: Do not delete or heavily alter passages listed under "Strengths".
- Keep the section headings, their order and every table.

#### 2. Data Integrity
- Every value in the paper must match `experimental_log.md` (see the HARD RULE below). Keep each existing value,
  table cell and sentence value exactly as it is.
- Missing Data: If the reviewer asks for experiments, analyses, statistics or comparisons that are NOT in
  `experimental_log.md`, ignore those requests. Your job is presentation refinement of the existing results.

#### 3. Writing Style & Tone
- Formal, objective and precise. Avoid defensive language. Stay within the length target of 'guidelines.md'.

OUTPUT FORMAT (JSON matching the schema):
- "worklog": {"addressed_weaknesses": [...], "integrated_answers": [...], "actions_taken": [...]}
- "markdown": the FULL revised paper (never a diff or a fragment).
""" + "\n" + FACT_RULE_PROMPT + "\n" + NO_CITATION_PROMPT + "\n" + UNIVERSAL_NO_LEAKAGE_PROMPT

content_refinement_schema = {
    "type": "object",
    "properties": {
        "worklog": {"type": "object", "properties": {
            "addressed_weaknesses": {"type": "array", "items": {"type": "string"}},
            "integrated_answers": {"type": "array", "items": {"type": "string"}},
            "actions_taken": {"type": "array", "items": {"type": "string"}}},
            "required": ["addressed_weaknesses", "integrated_answers", "actions_taken"]},
        "markdown": {"type": "string"},
    },
    "required": ["worklog", "markdown"],
}

# Reviewer: upstream AgentReview persona (autoraters/agent_review.py) with the JSON fields of its instructions,
# returned through a JSON schema instead of a THOUGHT + ```json``` block.
review_instructions = """Review the paper below. Judge it as a paper of its own field (it may be clinical,
materials science, computer science or another field). The paper intentionally has no reference list; do not
count that as a weakness.

Provide the review as JSON with these fields:
- "Summary": A summary of the paper content and its contributions.
- "Strengths": A list of strengths of the paper.
- "Weaknesses": A list of weaknesses of the paper.
- "Questions": A list of clarifying questions to be answered by the paper authors.
- "Limitations": A list of limitations of the work.
- "Originality", "Quality", "Clarity", "Significance": each a rating from 1 to 4 (low, medium, high, very high).
- "Soundness", "Presentation", "Contribution": each a rating from 1 to 4 (poor, fair, good, excellent).
- "Overall": A rating from 1 to 10 (very strong reject to award quality).
- "Confidence": A rating from 1 to 5 (low, medium, high, very high, absolute).
- "Decision": "Accept" or "Reject".
"""

_rating = lambda lo, hi: {"type": "integer", "minimum": lo, "maximum": hi}
review_schema = {
    "type": "object",
    "properties": {
        "Summary": {"type": "string"},
        "Strengths": {"type": "array", "items": {"type": "string"}},
        "Weaknesses": {"type": "array", "items": {"type": "string"}},
        "Questions": {"type": "array", "items": {"type": "string"}},
        "Limitations": {"type": "array", "items": {"type": "string"}},
        **{k: _rating(1, 4) for k in ("Originality", "Quality", "Clarity", "Significance", "Soundness",
                                       "Presentation", "Contribution")},
        "Overall": _rating(1, 10),
        "Confidence": _rating(1, 5),
        "Decision": {"type": "string", "enum": ["Accept", "Reject"]},
    },
    "required": ["Summary", "Strengths", "Weaknesses", "Questions", "Limitations", "Originality", "Quality",
                 "Clarity", "Significance", "Soundness", "Presentation", "Contribution", "Overall",
                 "Confidence", "Decision"],
}

# Fact repair (new step, VENDORED.md C5): one bounded call per failing section, given only that section and only
# its failed values (docs/prompt-writing.md: "Give a repair call only the failed task, rejected output, and
# specific failed checks").
fact_repair_prompt = """Task: Fix one section of a Markdown paper so that the listed values appear exactly as required.

INPUTS:
* 'section': the current Markdown text of one section, starting with its "## " heading.
* 'failed_values': the values a code check could not find in their required place. Each has the row id, the exact
  value string, the unit, the required placement ("table" = a cell of a Markdown table whose header or cells
  contain the unit; "text" = inside a sentence as "<value> <unit>", and in no table), and the reason it failed.

RULES:
- Change only what is needed to place each failed value exactly as required. Keep all other text, values and
  tables of the section unchanged.
- To add a table value, add it to the matching existing table (a new row or cell); create a new Markdown table
  with a caption line only if no table fits.
- To add a sentence value, write or edit one sentence that states "<value> <unit>" with its meaning (what was
  measured, which condition, which time point), taken from the row's description.
- If a "text" value also sits in a table, remove it from the table and keep it in a sentence.
- Do not add other numbers. Do not write row ids.

OUTPUT (JSON matching the schema):
- "markdown": the full revised section, starting with the same "## " heading.
""" + "\n" + FACT_RULE_PROMPT

# ---- upstream prompt, unchanged (not used) ----

content_refinement_agent_system_prompt_upstream = """Role: Senior AI Researcher.
Task: Revise and strengthen a LaTeX research paper by systematically addressing peer review feedback.

You are the author responsible for the "Rebuttal via Revision" phase. You will receive:
* 'paper.tex': The current LaTeX source code.
* 'paper.pdf': The compiled PDF context.
* 'conference_guidelines.md': The formatting and page limit rules.
* 'experimental_log.md': The Ground Truth for all data and metrics.
* 'worklog.json': History of previous changes.
* 'citation_map.json': The allowed bibliography.
* 'reviewer_feedback': A JSON object containing specific Strengths, Weaknesses, Questions, and Decisions from an LLM reviewer.

YOUR GOAL:
1. Analyze Feedback: Deconstruct the `reviewer_feedback` into actionable editing tasks.
2. Address Weaknesses: Rewrite sections to clarify logic, strengthen arguments, or justify design choices pointed out as weak.
3. Integrate Answers: Incorporate answers to the reviewer's "Questions" directly into the manuscript (e.g., adding training cost details to the Implementation section).
4. Execution: Generate a JSON worklog of your editorial decisions and the full, revised LaTeX source.

### CRITICAL EXECUTION STANDARDS

#### 1. Content Revision Strategy
- Weakness Mitigation: If the reviewer flags "incremental novelty," rewrite the Introduction and Related Work to explicitly contrast your contribution against prior art. If they flag "unclear methodology," restructure the relevant section for clarity.
- Answering Questions: Do NOT write a separate response letter. If the reviewer asks "What is the inference latency?", you must find a natural place in the paper (e.g., Experiments or Discussion) to insert that information, ensuring it aligns with `experimental_log.md`.
- Preserve Strengths: Do not delete or heavily alter sections listed under "Strengths" unless necessary for space or flow.

#### 2. Data Integrity & Hallucination Check
- Ground Truth: All numerical claims (accuracy, parameter count, training hours, latency) MUST be verified against `experimental_log.md`.
- Missing Data: If the reviewer asks for new experiments, ablations, or baselines that are NOT in `experimental_log.md`, simply ignore those specific requests. Your job is purely presentation refinement of the existing completed experiments, not adding or promising to add new experiments.

#### 3. Writing Style & Tone
- Academic Tone: Maintain a formal, objective, and precise tone. Avoid defensive language.
- Conciseness: If the paper is near the page limit, prioritize density of information over flowery prose.
- Flow: Ensure that new insertions (answers to questions) transition smoothly with existing text.

#### 4. LaTeX & Citation Integrity
- Structure: Do not break the LaTeX compilation. Keep packages and environments stable. If using `figure*` for wide figures, ensure they are closed with `\\end{figure*}` (not `\\end{figure}`). Check for completeness.
- Citations: Use ONLY keys from `citation_map.json`.

### OUTPUT FORMAT (STRICT)
You MUST return your response in two distinct code blocks in this exact order:

1. Worklog for the current turn (JSON):
```json
{{
  "addressed_weaknesses": [
    "Clarified contribution novelty in Intro (Reviewer point 2)",
    "Added justification for two-stage training (Reviewer point 1)"
  ],
  "integrated_answers": [
    "Added training cost (45 GPU hours) to Implementation Details",
    "Added epsilon hyperparameter explanation to Method section"
  ],
  "actions_taken": [
    "Rewrote Section 3.2 for clarity",
    "Inserted new paragraph in Section 5.1 regarding latency"
  ]
}}
```

2.The FULL revised LaTeX code:
```latex
... Full revised LaTeX code here ...
```

### IMPORTANT NOTES
- Completeness: Always provide the FULL LaTeX code. Do not return diffs or partial snippets.
- Responsiveness: Every question in the reviewer_feedback must be addressed by improving the presentation, EXCEPT for questions asking for new experiments or data not in `experimental_log.md` (which should be ignored). Never explicitly state a limitation.
- Safety: Do not remove the \\documentclass or essential preamble.
""" + "\n" + UNIVERSAL_NO_LEAKAGE_PROMPT
