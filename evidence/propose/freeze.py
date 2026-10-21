"""Step 5, `freeze` (deterministic): decisions.yaml applied to the draft -> protocol.yaml and proposal.json.

Refused (ProposalError, exit 2, nothing written): a missing step; an input changed after a later step read
it (frame after draft, draft after critic or cards); decisions.yaml failing `cards.validate` (a decision
without a reason, an unknown choice, ...); a protocol that does not validate as `evidence protocol check`
validates it; regex steps that can emit a role or metric outside its enum, or have no pattern for an
enum value (critic check `regex_matches_enums`); a directory already frozen (changes then go through
`evidence propose amend`).

protocol.yaml is the draft with every decision applied in card order, the regex patterns made again from
the decided roles and metrics (draft.sync_regex), and `revision: 1` (`version` stays
the protocol format, evidence/protocol.py). A copy `protocol.v1.yaml` is the base of the first amendment.
proposal.json records what the protocol was made from: the frame, the draft's sources, the critic, every
decision with who made it, the deterministic checks on the frozen protocol, the run settings the cascade
card chose (`strategy`), the vocabulary `{name, sha256}` or null, the model and prompt hash of every model
step, the sha256 of the inputs and of the protocol.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..protocol import parse
from . import cards as cards_module, critic as critic_module, frame as frame_module
from .common import (CARDS, CRITIC, DECISIONS, DRAFT, FRAME, PROPOSAL, PROTOCOL, SOURCES, ProposalError, dump_yaml,
                     fresh, need, now, read_json, sha, write_json, write_text)

HEADER = """# Frozen by `evidence propose freeze` from {name}/ on {created}: the draft with the decisions of decisions.yaml
# applied (proposal.json says what it was made from). Change it only through `evidence propose amend`.
"""


def versioned(directory: Path, revision: int) -> Path:
    return Path(directory) / f"protocol.v{revision}.yaml"


def ordered(p: dict[str, Any], revision: int) -> dict[str, Any]:
    """The mapping with `revision` right after `version`."""
    out: dict[str, Any] = {}
    for k, v in p.items():
        if k == "revision":
            continue
        out[k] = v
        if k == "version":
            out["revision"] = revision
    return out


def run(directory: Path | str, *, created: str | None = None) -> Path:
    directory = Path(directory)
    if (directory / PROTOCOL).exists():
        raise ProposalError(f"{directory / PROTOCOL} exists: the proposal is frozen; change it with "
                            "`evidence propose amend`")
    frame_path = need(directory, FRAME, "frame")
    f = frame_module.load(frame_path)
    draft_path = need(directory, DRAFT, "draft")
    sources = read_json(need(directory, SOURCES, "draft"))
    critic = read_json(need(directory, CRITIC, "critic"))
    cards = cards_module.load_cards(directory)
    fresh(directory, FRAME, sources.get("frame_sha256"), "draft")
    fresh(directory, DRAFT, critic.get("draft_sha256"), "critic")
    fresh(directory, DRAFT, cards.get("draft_sha256"), "cards")
    fresh(directory, CRITIC, cards.get("critic_sha256"), "cards")
    decisions = cards_module.validate(cards["cards"], cards_module.load_decisions(directory))

    draft = yaml.safe_load(draft_path.read_text(encoding="utf-8"))
    applied, run_settings = cards_module.apply(draft, decisions, f)
    created = created or now()
    text = HEADER.format(name=directory.resolve().name, created=created) + dump_yaml(ordered(applied, 1))
    try:
        protocol = parse(text)
    except (ValueError, yaml.YAMLError) as exc:
        raise ProposalError(f"the decided protocol does not validate: {exc}") from exc

    final = critic_module.checks(text, f)
    broken = next(c for c in final if c["id"] == "regex_matches_enums")
    if not broken["ok"]:
        raise ProposalError(f"the decided protocol's regex steps do not match its enums: {broken['message']}")
    calls = {step: data.get("call") for step, data in
             (("frame", read_json(frame_path)), ("critic", critic), ("cards", cards))}
    people = sorted({d["by"] for d in decisions if d["by"] != cards_module.MODEL})
    record = {
        "proposal": directory.resolve().name,
        "question": f.question,
        "created": created,
        "protocol": {"file": PROTOCOL, "id": protocol.id, "version": protocol.version, "revision": protocol.revision,
                     "sha256": protocol.sha256},
        "vocabulary": ({k: f.vocabulary[k] for k in ("name", "sha256")} if f.vocabulary else None),
        "models": {step: (c or {}).get("model") for step, c in calls.items()},
        "prompts": {step: (c or {}).get("prompt_sha256") for step, c in calls.items()},
        "inputs": {"frame_sha256": sha(frame_path), "draft_sha256": sha(draft_path),
                   "critic_sha256": sha(directory / CRITIC), "cards_sha256": sha(directory / CARDS),
                   "decisions_sha256": sha(directory / DECISIONS), "template": sources.get("template")},
        "run_settings": run_settings,
        "decided_by": {"model": [d["card"] for d in decisions if d["by"] == cards_module.MODEL],
                       **{who: [d["card"] for d in decisions if d["by"] == who] for who in people}},
        "decisions": decisions,
        "checks": final,
        "frame": read_json(frame_path),
        "sources": sources,
        "critic": critic,
    }
    write_text(directory / PROTOCOL, text)
    write_text(versioned(directory, 1), text)
    write_json(directory / PROPOSAL, record)
    return directory / PROTOCOL
