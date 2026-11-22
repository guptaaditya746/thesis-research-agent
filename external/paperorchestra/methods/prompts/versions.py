# Added for the thesis vendoring (VENDORED.md, C7): named writer prompt sets. "v1" = the prompts the frozen
# Claude-written benchmark papers were made with (default, unchanged). "v2" = writer_v2.py (style examples, plain
# writing rules, shorter section targets). Outline, review and repair prompts are shared by both.
from methods.prompts.literature_review_agent import literature_stub_writer_prompt
from methods.prompts.section_writing_agent import section_writing_agent_prompt
from methods.prompts.content_refinement_agent import content_refinement_agent_system_prompt
from methods.prompts import writer_v2

PROMPT_SETS = {
    "v1": {"literature": literature_stub_writer_prompt, "section": section_writing_agent_prompt,
           "refine": content_refinement_agent_system_prompt, "guidelines": "guidelines.md", "style": False},
    "v2": {"literature": writer_v2.literature_stub_writer_prompt_v2,
           "section": writer_v2.section_writing_agent_prompt_v2,
           "refine": content_refinement_agent_system_prompt + "\n" + writer_v2.REFINE_STYLE_V2,
           "guidelines": "guidelines_v2.md", "style": True,
           "number_repair": writer_v2.NUMBER_REPAIR_V2},      # C9: one repair call for unsupported numbers
    # C8: v2 + references from the research tool; only the citation rules differ from v2
    "v2r": {"literature": writer_v2.literature_stub_writer_prompt_v2r,
            "section": writer_v2.section_writing_agent_prompt_v2r,
            "refine": (content_refinement_agent_system_prompt + "\n" + writer_v2.REFINE_STYLE_V2).replace(
                "\n" + writer_v2.NO_CITATION_PROMPT, "\n" + writer_v2.CITATION_KEEP_V2R),
            "guidelines": "guidelines_v2.md", "style": True, "references": True,
            "number_repair": writer_v2.NUMBER_REPAIR_V2},
}

# C10 (paperfactory fix #4): v1 + the rule that the materials are not a source. v1 itself stays frozen.
NOTES_RULE = """
---
### The materials are not a source (HARD RULE, checked after you write)
1. Write about the sources themselves. Never refer to the materials you were given ("the notes", "the log",
   "this analysis", "our records", "the data provided") as if they were a source, and never say what they contain
   or leave out.
2. Never write that how one source treated another is not recorded, not addressed, unknown, absent or left open.
   If the materials give no relation between two sources, say nothing about that pair.
3. State what one source did with another only when `experimental_log.md` lists it.
Example. Not allowed: "This analysis records no treatment of X in Y." Allowed: leave the pair X, Y out.
"""
PROMPT_SETS["v1n"] = PROMPT_SETS["v1"] | {k: PROMPT_SETS["v1"][k] + "\n" + NOTES_RULE
                                          for k in ("literature", "section", "refine")}

# paperfactory v2 (22 Nov 2026): v1n + ONE repair call for numbers found in no input text (papers with numbers:
# synthesis and argument v2 genres). v1n stays for the papers written before.
PROMPT_SETS["v1nn"] = PROMPT_SETS["v1n"] | {"number_repair": writer_v2.NUMBER_REPAIR_V2}


def prompt_set(version: str) -> dict:
    if version not in PROMPT_SETS:
        raise ValueError(f"unknown prompt version {version!r}; known: {sorted(PROMPT_SETS)}")
    return PROMPT_SETS[version]
