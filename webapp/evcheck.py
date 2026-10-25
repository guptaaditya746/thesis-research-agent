"""The live checker and the paper preview of the proposal form (no model call, no job).

`check`: the posted decisions applied to the proposal's draft exactly as freeze would, then the deterministic
critic checks (evidence/propose/critic.py) of the result; every failure is a problem with its severity and the
card to look at. `preview`: where the draft's screen terms, the frame's names and the method-kind names hit in
one paper of a corpus.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from evidence.extractors.screen import term_pattern
from evidence.propose import cards as cards_module
from evidence.propose import critic, frame as frame_module
from evidence.propose.common import CARDS, DRAFT, FRAME, ProposalError, dump_yaml

from .evfiles import EvidenceFiles
from .evmodels import CheckProblem, CheckRequest, CheckResult, PreviewHit, PreviewResult
from .files import Conflict, NotFound, check_id, inside, read_json

CHECK_CARD = {"outcomes_complete": "metrics", "terms_cover_synonyms": "screen", "regex_matches_enums": "roles",
              "screen_present": "screen", "label_complete": "label", "extractors_registered": "cascade",
              "vocabulary_direction": "metrics", "bounds_cover_rate_metrics": "metrics",
              "metric_rules_collide": "metrics", "locate_params_used": "locate",
              "inventory_target_declared": "list_target", "best_kinds_nonempty": "method_kinds",
              "best_kinds_disjoint": "method_kinds", "claim_type_present": "claim_check"}
MAX_HITS = 2000


def proposal_dir(files: EvidenceFiles, name: str) -> Path:
    root = files._need(files.s.proposals_dir, "proposals", "EV_PROPOSALS")
    directory = inside(root, check_id(name, "proposal"))
    if not (directory / FRAME).is_file():
        raise NotFound(f"no such proposal: {name!r}")
    return directory


def check(files: EvidenceFiles, name: str, r: CheckRequest) -> CheckResult:
    directory = proposal_dir(files, name)
    if not (directory / CARDS).is_file() or not (directory / DRAFT).is_file():
        raise Conflict(f"proposal {name} has no draft and cards yet (run the proposal flow first)")
    f = frame_module.load(directory / FRAME)
    cards = (read_json(directory / CARDS) or {}).get("cards") or []
    entries = [{"card": d.card, "choice": d.choice, "reason": d.reason, "by": d.by,
                **({"value": d.value} if d.choice == cards_module.CUSTOM else {})} for d in r.decisions]
    try:
        decisions = cards_module.validate(cards, {"decisions": entries})
    except ProposalError as exc:
        lines = [ln.strip() for ln in str(exc).splitlines()[1:] if ln.strip()] or [str(exc)]
        return CheckResult(problems=[CheckProblem(check="decision", severity="serious", message=ln,
                                                  card=ln.split(":", 1)[0] if ln.split(":", 1)[0] in {c["id"] for c in cards} else None)
                                     for ln in lines])
    draft = yaml.safe_load((directory / DRAFT).read_text(encoding="utf-8"))
    applied, _ = cards_module.apply(draft, decisions, f)
    problems = [CheckProblem(check=c["id"], severity="serious" if c["severity"] in ("serious", "blocking") else "advisory",
                             message=c["message"], card=CHECK_CARD.get(c["id"]))
                for c in critic.checks(dump_yaml(applied), f) if not c["ok"]]
    return CheckResult(problems=sorted(problems, key=lambda p: p.severity != "serious"))


def preview(files: EvidenceFiles, name: str, corpus: str, paper: str) -> PreviewResult:
    directory = proposal_dir(files, name)
    if not (directory / DRAFT).is_file():
        raise Conflict(f"proposal {name} has no draft yet (run the proposal flow first)")
    draft = yaml.safe_load((directory / DRAFT).read_text(encoding="utf-8")) or {}
    f = frame_module.load(directory / FRAME)
    _, text = files._paper_text(files.corpus_dir(corpus), check_id(paper, "paper"))
    terms: list[tuple[str, str]] = [("screen", t) for t in (draft.get("screen") or {}).get("terms") or []]
    terms += [("roles", n) for role in (f.treatment, f.control) for n in role.names]
    terms += [("metrics", n) for o in f.outcomes for n in o.names]
    for names in ((draft.get("best") or {}).get("kinds") or {}).values():
        terms += [("method_kinds", n) for n in names or ()]
    hits: list[PreviewHit] = []
    for card, term in dict.fromkeys(terms):
        for m in re.finditer(term_pattern(str(term)), text):
            hits.append(PreviewHit(start=m.start(), end=m.end(), card=card, what=str(term)))
    hits.sort(key=lambda h: (h.start, h.end))
    return PreviewResult(text=text, hits=hits[:MAX_HITS])
