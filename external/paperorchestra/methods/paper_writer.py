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

# Thesis adaptation (VENDORED.md): the same pipeline order as upstream (outline -> literature -> section writing ->
# content refinement), with the Claude Code backend, the citation step stubbed, Markdown output instead of a compiled
# LaTeX PDF, and a new last step: a code check of every experimental_log.md value plus ONE bounded repair call per
# failing section. The upstream batch helpers (run_batch_writeup etc.) were removed: the thesis entry point
# (backend/evqa/paperwriter.py) runs one paper per process and caps parallel papers itself.

import os
import os.path as osp
import json
import time
import traceback

from methods.agents.outline_agent import OutlineAgent, fact_sections
from methods.agents.literature_stub_agent import StubLiteratureAgent
from methods.agents.section_writing_agent import SectionWritingAgent
from methods.agents.content_refinement_agent import ContentRefinementAgent
from methods.prompts.content_refinement_agent import fact_repair_prompt

from methods.prompts.versions import prompt_set
from methods.prompts.writer_v2 import style_examples_block, number_repair_schema
from utils.claude_code_utils import markdown_schema
from utils.common_utils import load_md_file
from utils import fact_check


def make_repair_fn(lm, facts):
    line_by_id = {f["id"]: f["line"] for f in facts}

    def repair(section_title, section_text, failed):
        failed_values = [{"row_id": r["id"], "value": r["value"], "unit": r["unit"], "placement": r["placement"],
                          "reason": r["reason"], "row_in_experimental_log": line_by_id[r["id"]]} for r in failed]
        user = ("'failed_values':\n" + json.dumps(failed_values, indent=1, ensure_ascii=False)
                + "\n\n'section':\n" + section_text)
        return lm(fact_repair_prompt, user, markdown_schema(), step=f"repair:{section_title}")["markdown"]

    return repair


def make_number_repair_fn(lm, system_prompt):
    """C9: one call; items in, {id: new sentence} out (code validates each, fact_check.number_repair)."""
    def repair(items):
        user = "'items':\n" + json.dumps(items, indent=1, ensure_ascii=False)
        out = lm(system_prompt, user, number_repair_schema(), step="repair:numbers")
        return {int(f["id"]): str(f["sentence"]) for f in out.get("fixes", [])}

    return repair


def write_single_paper(
    base_dir,
    lm,
    template_dir,
    idea_filename="idea_sparse.md",
    experimental_log_filename="experimental_log.md",
    max_reflections: int = 1,
    num_review_ensemble: int = 1,
    prompt_version: str = "v1",
    style_examples: list | None = None,
    references: list | None = None,
):
    """Writes base_dir/paper.md and base_dir/facts_check.json. Returns the summary dict.
    Upstream retried the whole pipeline up to 3 times on any exception; here a failure raises (each LLM call
    already retries once on a transport error), so a broken step is visible instead of silently re-run."""
    t0 = time.time()
    materials_dir = osp.join(base_dir, "raw_materials")
    idea_file_path = osp.join(materials_dir, idea_filename)
    experimental_log_file_path = osp.join(materials_dir, experimental_log_filename)
    template_path = osp.join(template_dir, "template.md")
    prompts = prompt_set(prompt_version)               # C7: named prompt set (v1 default)
    guidelines_path = osp.join(template_dir, prompts["guidelines"])
    style_examples = style_examples or []
    if prompts["style"] and not style_examples:
        raise ValueError(f"prompt version {prompt_version} needs style examples (--style_examples)")
    style_block = style_examples_block(style_examples) if prompts["style"] else ""
    # C8 (v2r): references from the research tool; only this version sees them
    references = (references or []) if prompts.get("references") else []
    from methods.prompts.writer_v2 import references_block
    for path in (idea_file_path, experimental_log_file_path, template_path, guidelines_path):
        assert osp.exists(path), f"Missing input file '{path}'!"

    idea_md = load_md_file(idea_file_path)
    log_md = load_md_file(experimental_log_file_path)
    guidelines_md = load_md_file(guidelines_path)
    facts = fact_check.parse_facts(log_md)
    # paperfactory: a genre whose template folder has genre.json with "numeric_facts": false (e.g. argument papers)
    # has no number facts; its claims are checked after writing (tagging step in backend/paperfactory)
    genre_file = os.path.join(template_dir, "genre.json")
    numeric = not os.path.isfile(genre_file) or json.load(open(genre_file)).get("numeric_facts", True)
    if not facts and numeric:
        raise ValueError(f"no facts (row ids) found in {experimental_log_file_path}")
    lm.log({"event": "prompt_version", "version": prompt_version, "guidelines": prompts["guidelines"],
            "style_examples": [e.get("id") for e in style_examples] if prompts["style"] else []})
    lm.log({"event": "facts", "n": len(facts), "table": sum(f["placement"] == "table" for f in facts),
            "text": sum(f["placement"] == "text" for f in facts)})

    ###############################################################################################
    # Step 1: Call outline agent
    outline = OutlineAgent(lm).run(
        idea_file=idea_file_path,
        experimental_log_file=experimental_log_file_path,
        template_file=template_path,
        guidelines_file=guidelines_path,
        facts=facts,
        output_filepath=osp.join(base_dir, "outline.json"),
    )
    if outline["code_notes"]:
        lm.log({"event": "outline_fixed_by_code", "notes": outline["code_notes"]})

    ###############################################################################################
    # Step 2: Literature step (stubbed: no search, no citations; writes Introduction + Related Work)
    template_with_intro = StubLiteratureAgent(
        lm,
        idea_path=idea_file_path,
        experimental_log_path=experimental_log_file_path,
        template_path=template_path,
        output_dir=osp.join(base_dir, "literature_agent_output"),
        system_prompt=prompts["literature"],
        references=references_block(references) if prompts.get("references") else None,
    ).run(outline)

    ###############################################################################################
    # Step 3: Section writing
    draft = SectionWritingAgent(
        lm, outline, template_with_intro, idea_md, log_md, guidelines_md, facts,
        system_prompt=prompts["section"], style_block=style_block,
    ).run(output_path=osp.join(base_dir, "raw_draft_paper.md"))
    lm.log({"event": "check", "stage": "draft", **fact_check.summary(fact_check.check_facts(draft, facts))})

    ###############################################################################################
    # Step 4: Content refinement (review -> revise -> review, value-gated)
    refined = ContentRefinementAgent(
        lm, log_md, guidelines_md, facts,
        work_dir=osp.join(base_dir, "content_refinement_workdir"),
        max_reflections=max_reflections,
        num_review_ensemble=num_review_ensemble,
        system_prompt=prompts["refine"],
    ).run(draft)
    lm.log({"event": "check", "stage": "refined", **fact_check.summary(fact_check.check_facts(refined, facts))})

    ###############################################################################################
    # Step 5 (new): value check + ONE bounded repair call per failing section
    final, attempts = fact_check.repair_round(refined, facts, fact_sections(outline), make_repair_fn(lm, facts))
    for a in attempts:
        lm.log({"event": "repair", **a})
    number_fix = None
    if prompts.get("number_repair"):
        # C9 (v2, v2r): ONE repair call for numbers found in no input text; what is left is recorded, not fatal
        final, number_fix = fact_check.number_repair(final, [idea_md, log_md], facts,
                                                     make_number_repair_fn(lm, prompts["number_repair"]))
        lm.log({"event": "number_repair", **number_fix})
    citations = None
    if prompts.get("references"):
        # C8: every citation must match a provided reference; only cited references are listed
        citations = fact_check.check_citations(final, references)
        by_id = {r["id"]: r for r in references}
        with open(osp.join(base_dir, "literature_agent_output", "citation_map.json"), "w", encoding="utf-8") as f:
            json.dump({rid: by_id[rid] for rid in citations["cited"]}, f, indent=1, ensure_ascii=False)
        citations["dropped_uncited"] = [r["id"] for r in references if r["id"] not in citations["cited"]]
    results = fact_check.check_facts(final, facts)
    summary = {
        **fact_check.summary(results),
        "repairs": len(attempts),
        "repairs_accepted": sum(a["accepted"] for a in attempts),
        "extra_numbers": fact_check.extra_numbers(final, idea_md, log_md),
        "leaked_row_ids": fact_check.leaked_row_ids(final),
        "unsupported_numbers": fact_check.unsupported_numbers(final, idea_md, log_md),
        **({"unsupported_numbers_before_repair": [n for i in number_fix["items"] for n in i["numbers"]],
            "unsupported_numbers_after_repair": number_fix["after"]} if number_fix else {}),
        "citations": citations,
        "exemplar_leaks": fact_check.exemplar_leaks(
            final, [json.dumps(e.get("sections", {}), ensure_ascii=False) for e in style_examples]
            + [r.get("abstract") or "" for r in references],
            [idea_md, log_md], [e.get("about", "") for e in style_examples]) if style_examples else None,
        # the References section (added below) is not checked: titles may hold numbers of other studies
        "prompt_version": prompt_version,
        "words": len(final.split()),
        "tables": sum(1 for t in fact_check._blocks(final)[0]),
        "seconds": round(time.time() - t0, 1),
    }
    if citations and citations["cited"]:
        final = final.rstrip() + "\n\n" + fact_check.references_section(references, citations["cited"])
    with open(osp.join(base_dir, "paper.md"), "w", encoding="utf-8") as f:
        f.write(final)
    with open(osp.join(base_dir, "facts_check.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "facts": results, "repairs": attempts,
                   **({"number_repair": number_fix} if number_fix else {})}, f, indent=2, ensure_ascii=False)
    lm.log({"event": "check", "stage": "final", **summary})
    return summary
