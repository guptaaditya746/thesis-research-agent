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


def prompt_set(version: str) -> dict:
    if version not in PROMPT_SETS:
        raise ValueError(f"unknown prompt version {version!r}; known: {sorted(PROMPT_SETS)}")
    return PROMPT_SETS[version]
