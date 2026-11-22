"""World agent and world checks with fake models (no model calls)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from paperfactory import config, packs, world

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW, ARG = packs.field("law"), packs.genre("argument")
pytestmark = pytest.mark.usefixtures("pilot_focus")


def model_entities(w: dict) -> dict:
    """A world's entities as the world model now answers: kind, name_parts and attrs, no names (names.py)."""
    def parts(e: dict) -> dict:
        if e["kind"] == "court":
            return {"court_type": e["alt"][0]}
        if e["kind"] == "provision":
            m = re.match(r"section (\w+)", e["label"])
            return {"section": m.group(1) if m else "1",
                    "statute": "Personal Data Act" if "Personal Data" in e["label"] else "Monitoring Ordinance"}
        return {"org": "Systems"}
    return {"entities": [{"id": k, "kind": v["kind"], "name_parts": parts(v), "attrs": v["attrs"]}
                         for k, v in w["entities"].items()]}


ENTS = model_entities(PILOT)
ENT_STEPS = [f"world:entities:{k}" for k in world.kind_order(LAW)]


def ents_answer(step: str, ents: dict = ENTS) -> dict:
    """The fake world model's answer to one entity call (one kind per call: the kind is the step's last part)."""
    kind = step.split(":")[2]
    return {"entities": [copy.deepcopy(e) for e in ents["entities"] if e["kind"] == kind]}
PAPERS = list(PILOT["papers"].values())


def fake_world(per_call: list[int], seen: list[str]):
    """Answers the entity call with the pilot entities and each paper call with the next per_call[i] pilot papers."""
    left = list(PAPERS)

    def call(role, step, system, user, schema, check=None, cache=True):
        seen.append(step)
        if step.startswith("world:entities"):
            return ents_answer(step)
        k = per_call.pop(0)
        out = [left.pop(0) for _ in range(min(k, len(left)))]
        return {"papers": copy.deepcopy(out)}
    return call


def test_missing_papers_are_asked_for_only(tmp_path: Path) -> None:
    seen: list[str] = []
    s = config.Settings("law", "argument", papers=3, out=str(tmp_path))
    w = world.draft(s, LAW, ARG, fake_world([1, 1, 1], seen))
    assert len(w["papers"]) == 3 and world.check(w, LAW, ARG, n_papers=3) == []
    assert seen == ENT_STEPS + ["world:papers:0", "world:papers:0:more:1", "world:papers:0:more:2"]


def test_still_missing_after_two_tries_is_a_clear_error(tmp_path: Path) -> None:
    s = config.Settings("law", "argument", papers=3, out=str(tmp_path))
    with pytest.raises(ValueError, match="planned 2 of 3 papers"):
        world.draft(s, LAW, ARG, fake_world([1, 0, 1], []))


def test_check_counts_papers() -> None:
    assert any("need 4" in e for e in world.check(PILOT, LAW, ARG, n_papers=4))


def test_two_repairs_for_a_batch_and_the_decoy_rule_in_the_prompt(tmp_path: Path) -> None:
    """Qwen smoke medicine/materials: decoys with the same pair and another relation failed after one repair. Since
    22 Nov 2026 code replaces such a decoy (world.fix_decoys); an error code cannot fix (an unknown entity in a
    claim) still gets the two repairs."""
    assert "Never the same two entities with another relation" in world.PAPER_SYS
    bad = copy.deepcopy(PAPERS)
    bad[0]["decoys"][0] = [bad[0]["claims"][0][0], "rejects", bad[0]["claims"][0][2]]   # same pair, other relation
    seen: list[str] = []

    def call(role, step, system, user, schema, check=None, cache=True):
        seen.append(step)
        return ents_answer(step) if step.startswith("world:entities") else {"papers": copy.deepcopy(bad)}
    w = world.draft(config.Settings("law", "argument", papers=3, out=str(tmp_path)), LAW, ARG, call)
    assert world.check(w, LAW, ARG, n_papers=3) == [] and list(w["decoy_repairs"]) == ["LAW-01"]
    assert seen == ENT_STEPS + ["world:papers:0"]
    worse = copy.deepcopy(PAPERS)
    worse[0]["claims"][1] = [worse[0]["claims"][1][0], worse[0]["claims"][1][1], "NOPE"]
    answers = [{"papers": copy.deepcopy(worse)}, {"papers": copy.deepcopy(worse)}, {"papers": copy.deepcopy(PAPERS)}]
    seen.clear()

    def call2(role, step, system, user, schema, check=None, cache=True):
        seen.append(step)
        return ents_answer(step) if step.startswith("world:entities") else answers.pop(0)
    w = world.draft(config.Settings("law", "argument", papers=3, out=str(tmp_path / "b")), LAW, ARG, call2)
    assert world.check(w, LAW, ARG, n_papers=3) == []
    assert seen == ENT_STEPS + ["world:papers:0", "world:papers:0:repair", "world:papers:0:repair:2"]


def test_world_check_names_the_pair_and_never_crashes_on_a_bad_conflict() -> None:
    """Review 22 Nov: the pair error said which pair; a conflict of 1 or 3 facts crashed world.check."""
    w = copy.deepcopy(PILOT)
    p = w["papers"]["L-01"]
    p["decoys"][0] = [p["claims"][0][0], "rejects", p["claims"][0][2]]
    assert any("same pair K5->S14 (relies_on, rejects)" in e for e in world.check(w, LAW, ARG))
    w = copy.deepcopy(PILOT)
    w["papers"]["L-03"]["conflict"] = w["papers"]["L-03"]["conflict"][:1]
    assert "L-03: a conflict is exactly two facts [subject, relation, object]" in world.check(w, LAW, ARG)
    assert world.PAPERS_SCHEMA["properties"]["papers"]["items"]["properties"]["conflict"]["maxItems"] == 2
