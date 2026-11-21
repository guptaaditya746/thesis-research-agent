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

"""
This agent takes in a Markdown template with Introduction and Related Work filled and fills in the missing sections.

Thesis adaptation (VENDORED.md, C1-C5): Claude Code backend, Markdown instead of LaTeX, no figures (tables only),
no citation library (citation step stubbed), and a `value_checklist` built by code from experimental_log.md.

Input:
- outline.json, template.md (intro + related work filled), idea.md, experimental_log.md, guidelines.md, facts.
Output:
- the full Markdown paper.
"""

import json
from collections import defaultdict

from methods.prompts.section_writing_agent import section_writing_agent_prompt
from utils.claude_code_utils import markdown_schema


def value_checklist(facts: list, outline: dict) -> str:
    """Code-built list of every value, grouped by planned section and table (explicit input for the writer)."""
    by_id = {f["id"]: f for f in facts}
    lines = []
    sections = defaultdict(list)
    for t in outline.get("table_plan", []):
        sections[t["section_title"]].append(("table", t))
    for s in outline.get("sentence_facts", []):
        sections[s["section_title"]].append(("sentence", s))
    for title, items in sections.items():
        lines.append(f"Section: {title}")
        for kind, item in items:
            if kind == "table":
                lines.append(f"  In table {item['table_id']} ({item['caption']}):")
                for rid in item["row_ids"]:
                    f = by_id[rid]
                    lines.append(f"    - {rid}: write the cell exactly as {f['value']} (unit {f['unit']} in the header)")
            else:
                f = by_id[item["row_id"]]
                lines.append(f"  In a sentence: {f['id']}: write exactly \"{f['value']} {f['unit']}\" -- {f['line']}")
    return "\n".join(lines)


class SectionWritingAgent:
    def __init__(self, lm, outline: dict, template_md: str, idea_md: str, experimental_log_md: str,
                 guidelines_md: str, facts: list, system_prompt: str = section_writing_agent_prompt,
                 style_block: str = ""):
        self.lm = lm
        self.system_prompt = system_prompt  # C7: v1 or v2 prompt set
        self.style_block = style_block      # C7: v2 only ('style_examples' input); empty for v1
        self.outline = outline
        self.template_md = template_md
        self.idea_md = idea_md
        self.log_md = experimental_log_md
        self.guidelines_md = guidelines_md
        self.facts = facts

    def run(self, output_path: str) -> str:
        print(f" > Agent {self.__class__.__name__} starting...")
        outline = {k: v for k, v in self.outline.items() if k != "code_notes"}
        style = (f"--- INPUT: style_examples (other studies: manner only, never their facts) ---\n"
                 f"{self.style_block}\n\n") if self.style_block else ""
        user_prompt = f"""
Here are the input materials for the paper.

--- INPUT: outline.json (Structure, table plan and sentence facts) ---
{json.dumps(outline, indent=1, ensure_ascii=False)}

--- INPUT: idea.md ---
{self.idea_md}

--- INPUT: experimental_log.md (the only source of result values) ---
{self.log_md}

--- INPUT: value_checklist (every value, where it goes, and exactly how to write it) ---
{value_checklist(self.facts, self.outline)}

--- INPUT: guidelines.md ---
{self.guidelines_md}

{style}--- INPUT: template.md (KEEP THE WRITTEN SECTIONS. FILL THE EMPTY SECTIONS.) ---
{self.template_md}

**INSTRUCTION**:
1. Identify the empty sections in `template.md`.
2. Write Markdown for those sections following `outline.json`.
3. Build the tables of the table plan from `experimental_log.md`, and state the sentence facts in sentences.
4. Check every line of `value_checklist` before you answer.
5. Return the **full** Markdown paper.
"""
        out = self.lm(self.system_prompt, user_prompt, markdown_schema(), step="section_writing")
        paper = out["markdown"].strip() + "\n"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(paper)
        print(f" > Paper saved to {output_path}")
        return paper
