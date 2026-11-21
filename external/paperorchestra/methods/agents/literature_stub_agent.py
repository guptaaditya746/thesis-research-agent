# Added for the thesis vendoring (VENDORED.md, change C2): stands in for HybridLiteratureAgent
# (literature_review_agent.py, kept unchanged but unused). Same role in the pipeline: write Introduction and
# Related Work into the template and produce a citation map. Here: no web search, no Semantic Scholar, an empty
# citation map and an empty references file; one LLM call writes the two sections without citations.

import json
import os.path as osp

from utils.common_utils import load_md_file
from utils.fact_check import find_section, split_sections, join_sections
from methods.prompts.literature_review_agent import (
    literature_stub_writer_prompt,
    literature_stub_writer_schema,
)


class StubLiteratureAgent:
    def __init__(self, lm, idea_path: str, experimental_log_path: str, template_path: str, output_dir: str,
                 system_prompt: str = literature_stub_writer_prompt, references: list | None = None):
        self.lm = lm
        self.references = references  # C8 (v2r): [{first_author, year, venue, title, gist}] or None
        self.system_prompt = system_prompt  # C7: v1 or v2 prompt set
        self.idea_path = idea_path
        self.experimental_log_path = experimental_log_path
        self.template_path = template_path
        self.output_dir = output_dir

    def run(self, outline: dict) -> str:
        """Returns the template with Introduction and Related Work filled. Writes citation_map.json ({})."""
        import os

        os.makedirs(self.output_dir, exist_ok=True)
        with open(osp.join(self.output_dir, "citation_map.json"), "w") as f:
            json.dump({}, f)   # C8: paper_writer rewrites it with the cited references (v2r)
        payload = {
            "intro_related_work_plan": outline.get("intro_related_work_plan", {}),
            "project_idea": load_md_file(self.idea_path),
            "project_experimental_log": load_md_file(self.experimental_log_path),
            "template.md": load_md_file(self.template_path),
        }
        if self.references is not None:
            payload["references"] = self.references
        user = "Generate the Markdown for the Introduction and Related Work sections.\n\n" + json.dumps(
            payload, ensure_ascii=False, indent=1)
        out = self.lm(self.system_prompt, user, literature_stub_writer_schema, step="intro_related_work")
        parts = split_sections(load_md_file(self.template_path))
        for title, body in (("Introduction", out["introduction"]), ("Related Work", out["related_work"])):
            i = find_section(parts, title)
            if i is None:
                raise ValueError(f"template.md has no '{title}' section")
            heading = parts[i][1].splitlines(keepends=True)[0]
            parts[i] = (parts[i][0], heading + "\n" + body.strip() + "\n\n")
        filled = join_sections(parts)
        with open(osp.join(self.output_dir, "template_with_intro.md"), "w", encoding="utf-8") as f:
            f.write(filled)
        return filled
