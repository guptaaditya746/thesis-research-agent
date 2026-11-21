"""World agent and world checks with fake models (no model calls)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from paperfactory import config, packs, world

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW, ARG = packs.field("law"), packs.genre("argument")
ENTS = {"entities": [{"id": k, **v} for k, v in PILOT["entities"].items()]}
PAPERS = list(PILOT["papers"].values())


def fake_world(per_call: list[int], seen: list[str]):
    """Answers the entity call with the pilot entities and each paper call with the next per_call[i] pilot papers."""
    left = list(PAPERS)

    def call(role, step, system, user, schema, check=None):
        seen.append(step)
        if step == "world:entities":
            return copy.deepcopy(ENTS)
        k = per_call.pop(0)
        out = [left.pop(0) for _ in range(min(k, len(left)))]
        return {"papers": copy.deepcopy(out)}
    return call


def test_missing_papers_are_asked_for_only(tmp_path: Path) -> None:
    seen: list[str] = []
    s = config.Settings("law", "argument", papers=3, out=str(tmp_path))
    w = world.draft(s, LAW, ARG, fake_world([1, 1, 1], seen))
    assert len(w["papers"]) == 3 and world.check(w, LAW, ARG, n_papers=3) == []
    assert seen == ["world:entities", "world:papers:0", "world:papers:0:more:1", "world:papers:0:more:2"]


def test_still_missing_after_two_tries_is_a_clear_error(tmp_path: Path) -> None:
    s = config.Settings("law", "argument", papers=3, out=str(tmp_path))
    with pytest.raises(ValueError, match="planned 2 of 3 papers"):
        world.draft(s, LAW, ARG, fake_world([1, 0, 1], []))


def test_check_counts_papers() -> None:
    assert any("need 4" in e for e in world.check(PILOT, LAW, ARG, n_papers=4))
