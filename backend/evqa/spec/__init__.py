"""Spec step: the independent advisor (question + general knowledge + the user's answers -> a locked Spec).

    from evqa import spec
    s = spec.run(question_record, cfg)            # benchmark: answers from the intent card
    s = spec.run(question_record, cfg, ask_user)  # presentation: ask_user(point_id, ask_text) -> answer
    spec.advisor_score(s, needed)                 # eval: share of needed names and slots present

Never sees papers, the corpus or the benchmark truth (seed wall test).
"""
from evqa.spec.build import AskUser, SpecError, run
from evqa.spec.score import advisor_score

__all__ = ["AskUser", "SpecError", "advisor_score", "run"]
