"""#4: papers must agree with the world. Pattern check, world check by the verifier, paragraph repair, whole-paper
redo, failed papers. Fake models only."""
from __future__ import annotations

import json
import re
from pathlib import Path

from paperfactory import config, packs, repair

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW = packs.field("law")
BAD = "This analysis records no treatment of section 9 in *Pell*, and it records no holding on the consent boxes."
GOOD = "The court still relied on the earlier ruling in that dispute."
PAPER = (f"# Title\n\nPell v. Vantor Systems relied on Halden Mobile in its reasoning here.\n\n{BAD} {GOOD}\n")


def fake(repaired: str, seen: list | None = None):
    def call(role, step, system, user, out, check=None):
        if seen is not None:
            seen.append((role, step))
        if role == "verifier":
            items = json.loads(user)
            return {"answers": [{"id": x["id"], "verdict": "ABSENCE_CLAIM" if "section 9" in x["pair"][1] or
                                 "section 9" in x["pair"][0] else "SUPPORTS"} for x in items]}
        assert role == "repair"
        out = {"paragraph": repaired}
        assert check is None or check(out) is None, check(out)
        return out
    return call


def setup(tmp_path: Path, md: str = PAPER) -> config.Settings:
    s = config.Settings("law", "argument", out=str(tmp_path))
    (tmp_path / "work" / "L-02").mkdir(parents=True)
    (tmp_path / "work" / "L-02" / "paper.md").write_text(md)
    return s


def test_the_l02_sentence_is_caught_by_pattern_and_by_the_world_check(tmp_path: Path) -> None:
    s = setup(tmp_path)
    chk = repair.Checker(s, PILOT, LAW, fake(GOOD))
    assert any(p.search(BAD.replace("*", "")) for p in chk.patterns)
    assert chk.says("K4", "S9") == ("Pell v. Vantor Systems: the court rejected section 9 of the Veldra Personal "
                                    "Data Act 2016.")
    flags, notes = chk.check("L-02", PAPER)
    assert [(f["kind"], f["pair"]) for f in flags] == [("ABSENCE_CLAIM", ["K4", "S9"])] and notes == []


def test_a_pattern_with_no_pair_is_flagged_without_the_verifier(tmp_path: Path) -> None:
    md = "The notes list only these decisions and no others at all.\n"
    seen: list = []
    flags, _ = repair.Checker(setup(tmp_path, md), PILOT, LAW, fake(GOOD, seen)).check("L-02", md)
    assert [f["kind"] for f in flags] == ["pattern"] and seen == []


def test_a_repaired_paragraph_is_checked_again_and_kept(tmp_path: Path) -> None:
    s = setup(tmp_path)
    seen: list = []
    res = repair.Checker(s, PILOT, LAW, fake(GOOD, seen)).repair_paper("L-02", redo=lambda pid: None)
    assert res["status"] == "repaired"
    work = tmp_path / "work" / "L-02"
    assert (work / "paper.raw.md").read_text() == PAPER
    assert BAD not in (work / "paper.md").read_text() and GOOD in (work / "paper.md").read_text()
    assert "Pell v. Vantor Systems relied on Halden Mobile" in (work / "paper.md").read_text()
    log = json.loads((work / "paper.repairs.json").read_text())["log"]
    assert [x["step"] for x in log] == ["first:check", "first:repair", "first:recheck"]
    assert seen.count(("repair", "repair:L-02")) == 1


def test_two_failures_then_whole_paper_redo_then_failed(tmp_path: Path) -> None:
    s = setup(tmp_path)
    redos: list[str] = []

    def redo(pid: str) -> str:
        redos.append(pid)
        return PAPER                                     # the rewrite makes the same mistake
    res = repair.Checker(s, PILOT, LAW, fake(f"{BAD} {GOOD}")).repair_paper("L-02", redo)
    assert res["status"] == "failed" and redos == ["L-02"]
    assert repair.failed(tmp_path, "L-02")
    steps = [x["step"] for x in json.loads((tmp_path / "work" / "L-02" / "paper.repairs.json").read_text())["log"]]
    assert steps == ["first:check", "first:repair", "first:recheck", "redo", "after_redo:check",
                     "after_redo:repair", "after_redo:recheck"]


def test_repair_may_not_drop_a_planted_fact(tmp_path: Path) -> None:
    md = f"Pell v. Vantor Systems rejected section 9 as a ground, {BAD}\n"
    chk = repair.Checker(setup(tmp_path, md), PILOT, LAW, None)
    got = []

    def call(role, step, system, user, out, check=None):
        got.append(check({"paragraph": "Something else entirely about the case."}))
        return None
    chk.call = call
    assert chk.repair_unit("L-03", md, ["x"], PILOT["papers"]["L-03"]["claims"]) is None
    assert "keep the names of these facts" in got[0]


def test_an_ordinary_opening_sentence_is_not_flagged(tmp_path: Path) -> None:
    """Qwen smoke run (21 Nov 2026): "This paper examines ..." opened LAW-01 and was flagged by the old pattern
    "This (analysis|paper|...)"; the paper was repaired, rewritten and failed although nothing was wrong."""
    md = ("This paper examines the legal sufficiency of implied consent for the processing of sensitive personal "
          "data under the Data Privacy Act 2015.\n")
    for name in ("law", "llm", "medicine", "materials"):
        assert not any(re.search(p, md) for p in packs.field(name).raw["text"]["absence_patterns"]), name
    flags, _ = repair.Checker(setup(tmp_path, md), PILOT, LAW, fake(GOOD, [])).check("L-02", md)
    assert flags == []
