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

from utils.prompt_utils import UNIVERSAL_NO_LEAKAGE_PROMPT

literature_review_agent_writter_prompt = """Role: Senior AI Researcher.
Task: Write the introduction and related work section of a paper.

You will be given a 'template.tex', this is the initial skeleton we outlined for you. 
Your job is to fill in two sections: Introduction and Related Work. Leave all the other sections untouched.

INPUTS:
* 'intro_related_work_plan': This is your PRIMARY guide for structure and arguments.
* 'project_idea' and 'project_experimental_log': Use them to ensure the Intro accurately frames the technical contribution and results.
* 'citation_checklist': This includes the citation keys that you should use when citing relevant papers.
* 'collected_papers': These are all the relevant papers we collect for you for citation purpose.

YOU MUST ONLY CITE THE GIVEN 'collected_papers', DO NOT cite new papers other than the given papers.

CITATION REQUIREMENTS:
- You have access to the abstract of {paper_count} collected papers.
- You MUST cite at least {min_cite_paper_count} of them across the introduction and related work sections.
- Introduction: Cite key statistics, foundational models (CLIP, etc.), and broad problem statements.
- Related Work: Do deep comparative citations. Group distinct works (e.g., "Several methods [A, B, C]...").
- Ensure every \\cite{{key}} corresponds exactly to a key in 'citation_checklist'.
- CRITICAL TIMELINE RULE: Do not treat any papers published after {cutoff_date} as prior baselines to beat. Treat them strictly as concurrent work.
- CRITICAL EVALUATION RULE: Do not claim our method beats or achieves State-of-the-Art over a specific cited paper UNLESS that paper is explicitly evaluated against in 'project_experimental_log'. Frame other recent papers strictly as concurrent, orthogonal, or conceptual work.
- You need to return the full code for the new 'template.tex', where the two empty sections (Introduction and Related Work) are now fille in, 
  while all the other code (packages, styles, and other sections) are identical to the original 'template.tex'.

IMPORTANT NOTE:
- DO NOT change '\\usepackage[capitalize]{{cleveref}}' into '\\usepackage[capitalize]{{cleverref}}', as there's no 'cleverref.sty'.

OUTPUT Format:
You must return the code for the updated 'template.tex', Make sure to wrap the code with ```latex content```.
""" + "\n" + UNIVERSAL_NO_LEAKAGE_PROMPT


# --- Thesis adaptation (VENDORED.md, C2-C4): citation step stubbed. No search, no collected papers, no citations;
# the agent still writes Introduction and Related Work from the outline's plan, field-neutral, in Markdown.
from utils.prompt_utils import NO_CITATION_PROMPT

literature_stub_writer_prompt = """Role: Senior researcher in the field of the provided materials.
Task: Write the Introduction and Related Work sections of a paper, in Markdown.

You will be given 'template.md', the skeleton of the paper. Write the text of two sections only:
"Introduction" and "Related Work". Leave all other sections to a later writer.

INPUTS:
* 'intro_related_work_plan': your PRIMARY guide for structure and arguments.
* 'project_idea' and 'project_experimental_log': use them so the Introduction frames the study's contribution
  and scope accurately.

RULES:
- Introduction: 4-6 paragraphs, about 500-700 words. Follow `key_points` in order. End with a short paragraph
  that states the contributions of this study as listed in 'project_idea'.
- Related Work: about 350-500 words, one level-3 subsection (`### 2.1 ...`) per cluster of the plan.
- This paper has no reference list (see "No Citations" below). Describe prior work by approach only.
- Do not report any result value of this study in these two sections; results belong to the Results section.
- Do not claim the study outperforms any specific prior method; frame prior work as context.

OUTPUT (JSON matching the schema):
- "introduction": the Markdown body of the Introduction, WITHOUT its "## 1. Introduction" heading line.
- "related_work": the Markdown body of Related Work, WITHOUT its "## 2. Related Work" heading line.
""" + "\n" + NO_CITATION_PROMPT + "\n" + UNIVERSAL_NO_LEAKAGE_PROMPT

literature_stub_writer_schema = {
    "type": "object",
    "properties": {"introduction": {"type": "string"}, "related_work": {"type": "string"}},
    "required": ["introduction", "related_work"],
    "additionalProperties": False,
}
