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

# Thesis adaptation (VENDORED.md, C1-C4): Claude Code backend instead of Gemini; Markdown template; the outline
# also plans tables and which section states each value; code completes the plan so every value is placed.

import json

from utils.common_utils import load_md_file
from utils.fact_check import find_section

from methods.prompts.outline_agent import outline_agent_system_prompt, outline_agent_schema


class OutlineAgent:
    def __init__(self, lm, model_name: str = None):
        self.lm = lm
        self.model_name = model_name or getattr(lm, "model", None)

    def run(
        self,
        idea_file: str,
        experimental_log_file: str,
        template_file: str,
        guidelines_file: str,
        facts: list,
        output_filepath: str = None,
    ):
        user = "\n\n".join([
            "'idea.md':\n" + load_md_file(idea_file),
            "'experimental_log.md':\n" + load_md_file(experimental_log_file),
            "'template.md':\n" + load_md_file(template_file),
            "'guidelines.md':\n" + load_md_file(guidelines_file),
        ])
        outline = self.lm(outline_agent_system_prompt, user, outline_agent_schema, step="outline")
        outline, notes = complete_fact_plan(outline, facts, load_md_file(template_file))
        outline["code_notes"] = notes
        if output_filepath is not None:
            with open(output_filepath, "w") as f:
                json.dump(outline, f, indent=4)
                print(f"outline.json output written to {output_filepath}")
        return outline


def results_title(template_md: str) -> str:
    for line in template_md.splitlines():
        if line.startswith("## ") and "result" in line.lower():
            return line[3:].strip()
    return "Results"


def complete_fact_plan(outline: dict, facts: list, template_md: str):
    """Code check of the plan (not an LLM step): every "table" fact in exactly one table, every "text" fact in
    `sentence_facts`, no unknown ids, no table fact listed as a sentence and vice versa. Fixes by moving the row
    to the Results section; returns (outline, notes about what was fixed)."""
    by_id = {f["id"]: f for f in facts}
    res = results_title(template_md)
    parts = [(l[3:].strip(), "") for l in template_md.splitlines() if l.startswith("## ")]
    notes, seen = [], set()

    def known_section(title):
        i = find_section(parts, title or "")
        return parts[i][0] if i is not None else res

    tables = []
    for t in outline.get("table_plan", []):
        keep = []
        for rid in t.get("row_ids", []):
            f = by_id.get(rid)
            if f is None or rid in seen or f["placement"] != "table":
                notes.append(f"dropped {rid} from {t.get('table_id')} (unknown, repeated or a sentence fact)")
                continue
            seen.add(rid)
            keep.append(rid)
        if keep:
            tables.append({**t, "row_ids": keep, "section_title": known_section(t.get("section_title"))})
    missing = [f["id"] for f in facts if f["placement"] == "table" and f["id"] not in seen]
    if missing:
        notes.append(f"table facts not planned by the outline, put in an extra table: {missing}")
        tables.append({"table_id": "tab_additional_results", "caption": "Additional results",
                       "section_title": res, "columns": [], "row_ids": missing})
    sentences, sseen = [], set()
    for s in outline.get("sentence_facts", []):
        rid = s.get("row_id")
        f = by_id.get(rid)
        if f is None or rid in sseen or f["placement"] != "text":
            notes.append(f"dropped sentence fact {rid} (unknown, repeated or a table fact)")
            continue
        sseen.add(rid)
        sentences.append({"row_id": rid, "section_title": known_section(s.get("section_title"))})
    for f in facts:
        if f["placement"] == "text" and f["id"] not in sseen:
            notes.append(f"sentence fact {f['id']} not planned by the outline, assigned to {res}")
            sentences.append({"row_id": f["id"], "section_title": res})
    outline["table_plan"], outline["sentence_facts"] = tables, sentences
    return outline, notes


def fact_sections(outline: dict) -> dict:
    """row id -> section title where the plan puts it (used to aim repairs)."""
    out = {}
    for t in outline.get("table_plan", []):
        for rid in t["row_ids"]:
            out[rid] = t["section_title"]
    for s in outline.get("sentence_facts", []):
        out[s["row_id"]] = s["section_title"]
    return out
