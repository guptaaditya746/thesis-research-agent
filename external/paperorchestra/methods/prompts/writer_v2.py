# Added for the thesis vendoring (VENDORED.md, change C7, 21 Nov 2026): writer prompt set "v2".
#
# Why: Qwen (qwen:orch-model) writing with the v1 prompts put every value in place but wrote generic, repetitive
# prose (long empty Related Work clusters, the design restated in every section). v2 changes only the two calls
# that write the prose (Introduction + Related Work, and the remaining sections), the guidelines file, and adds
# one style rule to the refinement call. The outline, review and repair prompts are the same as v1.
# v1 (the prompts the frozen Claude-written benchmark papers were made with) stays the default; nothing here
# changes a v1 prompt. Select with `--prompt_version v2` (paper_writing_cli.py) / `prompt_version="v2"`.
#
# New input: 'style_examples', short CC-licensed excerpts of real published trial reports (data/style/<domain>/),
# chosen by code. They teach manner only; the paper's facts come only from idea.md and experimental_log.md, and
# code checks that (fact_check.unsupported_numbers / exemplar_leaks).

from utils.prompt_utils import UNIVERSAL_NO_LEAKAGE_PROMPT, NO_CITATION_PROMPT, FACT_RULE_PROMPT

STYLE_RULE_V2 = """
---
### Style examples and plain writing (checked by code after you write)
'style_examples' are short passages from real published trial reports about OTHER drugs. Copy only their manner:
sentence structure, density, how a result sentence names the comparison, the time point and the unit.
1. Never copy a number, drug name, sample size, confidence interval, p-value, population detail or claim from
   'style_examples'. Every number in the paper must come from idea.md or experimental_log.md.
2. When an example reports something the log does not give (CI, p-value, number randomised, baseline values,
   adverse events), leave it out. Say once, in the limitations paragraph, what the report does not include.
3. Each paragraph adds new information. After Methods, do not restate the design, the arms or the aim.
4. Vary sentence openings. Do not start two sentences in a row with the same word.
5. Prefer concrete statements over general ones. Drop sentences that would fit any trial of any drug
   (e.g. "These findings provide valuable insights for clinical decision-making").

Examples (Drug X is a placeholder; follow the rule, not the topic):
- Normal. Log: `-0.62 percentage points | state in a sentence`, 20 mg, week 24, HbA1c.
  Right: "At week 24, HbA1c fell more with Drug X 20 mg than with placebo (mean difference -0.62 percentage points)."
- Confusing. A style example writes "-0.70% (95% CI -0.85 to -0.55; P < 0.001)". The log gives only -0.70.
  Right: "-0.70 percentage points". Wrong: adding a CI or P value, or writing "%" for percentage points.
- Missing. A style example opens Methods with "A total of 701 patients were randomised". The log gives no count.
  Right: "Adults with type 2 diabetes on metformin were randomised to Drug X 10 mg, 20 mg or placebo."
  Wrong: any participant number.
---
"""

literature_stub_writer_prompt_v2 = """Task: Write the Introduction and Related Work of a research paper, in Markdown.

INPUTS:
* 'intro_related_work_plan': the argument to make (hook, gap, key points, clusters of prior work).
* 'project_idea' and 'project_experimental_log': the study. They are the only source of facts about it.

RULES:
- Introduction: 3-4 paragraphs, 300-450 words. Paragraph 1: the clinical or practical problem. Paragraph 2-3:
  what is known about this kind of treatment or approach and what is still unknown (the gap in 'project_idea').
  Last paragraph: the aim of this study and what the paper reports, in 2-3 sentences.
- Related Work: 2 paragraphs, 150-250 words, no subsection headings. Describe the kinds of earlier studies on
  the same question (design, comparator, duration, outcomes reported) and what they leave open. Mention this
  study in at most one closing sentence. Leave out approaches that do not address the same question.
- Do not report any result value of this study; results belong to the Results section.
- Do not claim the study outperforms any prior method.
- Each paragraph adds new information; vary sentence openings; prefer concrete statements over general ones.

OUTPUT (JSON matching the schema):
- "introduction": the Markdown body of the Introduction, WITHOUT its "## 1. Introduction" heading line.
- "related_work": the Markdown body of Related Work, WITHOUT its "## 2. Related Work" heading line.
""" + "\n" + NO_CITATION_PROMPT + "\n" + UNIVERSAL_NO_LEAKAGE_PROMPT

section_writing_agent_prompt_v2 = """Task: Write the empty sections (Abstract, Methods, Results, Discussion,
Conclusion) of 'template.md' and return the whole paper in Markdown.

INPUTS:
* 'outline.json': the plan: sections, the table plan (row ids per table) and `sentence_facts`.
* 'idea.md' and 'experimental_log.md': the only source of facts (design, arms, measures, time points, values).
* 'value_checklist': every value, where it goes and exactly how to write it.
* 'guidelines.md': format and the length of each section.
* 'style_examples': passages from real trial reports, for manner only (see the style rule below).
* 'template.md': Introduction and Related Work are written; keep them. Replace "{TITLE}" with the title of 'idea.md'.

WHAT EACH SECTION DOES:
- Abstract: one paragraph in the order aim, methods, main results (state
  the main measure's sentence values), conclusion.
- Methods: design and participants; interventions and comparator; outcomes and time points; how results are
  summarised. Only what idea.md and experimental_log.md state.
- Results: one short paragraph per table or measure. Name the table, give the pattern across doses and time
  points, and state the sentence values. No interpretation here. All tables go in Results.
- Discussion: 3-4 paragraphs: the main finding in 1-2 sentences; the pattern over dose and time; what it means
  for choosing a treatment, without claims beyond the log; one concrete limitations paragraph.
- Conclusion: 2-3 sentences.

Tables: Markdown pipe tables, a caption line "Table N: ..." directly above, the unit in the column header.

OUTPUT (JSON matching the schema):
- "markdown": the full paper, from the "# " title line to the end of the Conclusion.
""" + "\n" + STYLE_RULE_V2 + "\n" + FACT_RULE_PROMPT + "\n" + NO_CITATION_PROMPT + "\n" + UNIVERSAL_NO_LEAKAGE_PROMPT


REFINE_STYLE_V2 = """
---
### Plain writing (v2)
Keep the paper concrete: each paragraph adds new information; after Methods, do not restate the design, the
arms or the aim; vary sentence openings; drop sentences that would fit any study of any treatment. Keep the
section lengths of 'guidelines.md'. Add no number that is not in experimental_log.md or the paper's setup.
---
"""


# ---- style examples (built by code in backend/evqa/research/style.py, passed as a JSON file) -----------------
STYLE_SECTIONS = ("Abstract", "Methods: participants", "Results: mean difference vs placebo", "Results: table",
                  "Discussion: limitations")


def style_examples_block(examples: list) -> str:
    """The 'style_examples' input text from [{about, license, sections: {name: text}}]. Each example is named as
    a different study so the model treats it as manner, not content."""
    parts = []
    for i, ex in enumerate(examples, 1):
        parts.append(f"=== Style example {i} (a different study{', about ' + ex['about'] if ex.get('about') else ''}"
                     f"; {ex.get('license', '')}) ===")
        for title in STYLE_SECTIONS:
            if ex.get("sections", {}).get(title):
                parts.append(f"[{title}]\n{ex['sections'][title]}")
    return "\n\n".join(parts)


# ---- v2r: v2 + references found by the research tool (VENDORED.md, C8, 21 Nov 2026) ----------------------------
# The research loop (backend/evqa/research/agent.py) picks up to 4 real papers as references. Only the
# Introduction + Related Work call sees them and may cite them; the later calls keep the citations as written.
# Code checks every citation against the list and appends a References section with the cited ones only.

CITATION_RULE_V2R = """
---
### Citations (only the provided references)
Cite only papers listed in 'references', and only as "(FirstAuthor et al., YEAR)" with the first author's surname
and year exactly as listed (two papers: "(Smith et al., 2019; Lee et al., 2021)"). Cite a paper only where its
gist supports the sentence. Never state a number, result or drug-specific claim from a reference; describe it by
design and question only. Write no reference list (code adds it) and no other citation formats.
Examples: normal: "Earlier placebo-controlled add-on trials reported HbA1c and body weight together (Lee et al.,
2021)."; confusing: a gist says "HbA1c fell by 0.7%" -> cite the design, not the number; missing: no listed
paper fits a sentence -> write the sentence without a citation.
---
"""

CITATION_KEEP_V2R = """
---
### Citations
The Introduction and Related Work contain citations like "(Smith et al., 2019)". Keep each one exactly as written.
Add no new citations, no other citation formats and no reference list.
---
"""

literature_stub_writer_prompt_v2r = literature_stub_writer_prompt_v2.replace(
    """* 'project_idea' and 'project_experimental_log': the study. They are the only source of facts about it.""",
    """* 'project_idea' and 'project_experimental_log': the study. They are the only source of facts about it.
* 'references': real published papers you may cite (id, first author, year, venue, title, one-line gist).""",
).replace("\n" + NO_CITATION_PROMPT, "\n" + CITATION_RULE_V2R)

section_writing_agent_prompt_v2r = section_writing_agent_prompt_v2.replace(
    "\n" + NO_CITATION_PROMPT, "\n" + CITATION_KEEP_V2R)


def references_block(refs: list) -> list:
    """The 'references' input for the model: no abstracts, only a one-line gist (fewer numbers to copy)."""
    return [{"first_author": r["first_author"], "year": r["year"], "venue": r.get("venue") or "",
             "title": r["title"], "gist": r.get("gist") or ""} for r in refs]


# Added 21 Nov 2026 (VENDORED.md, C9): one bounded repair call for numbers that occur in no input text
# (fact_check.unsupported_numbers). Used by v2 and v2r only; v1 makes no such call.
NUMBER_REPAIR_V2 = """Task: Rewrite each listed sentence of a paper so that it no longer holds the flagged numbers.

INPUT 'items': a JSON list. Each item has
- "id": the item number;
- "sentence": one sentence of the paper, or one Markdown table row (starts and ends with "|");
- "numbers": the numbers in it that occur in no input text (idea.md, experimental_log.md). They are not facts of
  this study, so they must go.

OUTPUT (JSON matching the schema): "fixes", one entry per item: {"id": <item id>, "sentence": <new text>}.

RULES (code checks every fix; a fix that breaks a rule is thrown away):
1. Remove each flagged number, or replace it with words that hold no number. Never put in another number.
2. Keep every other number of the sentence exactly as written (same digits, sign and unit).
3. Keep the meaning that does not depend on the flagged number. Keep the sentence's language and tone.
4. A table row stays a table row with the same number of "|" cells; write "not reported" in a cell whose number
   you remove.
5. When nothing true remains without the number, return "" for that sentence (a table row may not be "").

EXAMPLES
- Normal. {"id": 1, "sentence": "A total of 312 patients were randomised to Drug X or placebo.", "numbers": ["312"]}
  -> {"id": 1, "sentence": "Patients were randomised to Drug X or placebo."}
- Confusing (a correct value next to an invented interval). {"id": 2, "sentence": "HbA1c fell by -0.57 pp
  (95% CI -0.71 to -0.43).", "numbers": ["-0.71", "-0.43"]} -> {"id": 2, "sentence": "HbA1c fell by -0.57 pp."}
  Wrong: dropping -0.57, or writing "about -0.7".
- Table row. {"id": 3, "sentence": "| Placebo | 120 | -0.10 |", "numbers": ["120"]}
  -> {"id": 3, "sentence": "| Placebo | not reported | -0.10 |"}
- Nothing left. {"id": 4, "sentence": "Retention was 94% at week 24.", "numbers": ["94"]} where the inputs give
  no retention figure -> {"id": 4, "sentence": ""}
"""


def number_repair_schema() -> dict:
    fix = {"type": "object", "properties": {"id": {"type": "integer"}, "sentence": {"type": "string"}},
           "required": ["id", "sentence"], "additionalProperties": False}
    return {"type": "object", "properties": {"fixes": {"type": "array", "items": fix}}, "required": ["fixes"],
            "additionalProperties": False}
