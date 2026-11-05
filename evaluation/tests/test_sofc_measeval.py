"""SOFC-Exp and MeasEval checks on hand-made fixtures in the layouts assumed in the modules (not release data)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from evaluation.realpapers import measeval, sofc
from evaluation.wholerun import Answer, score

DATA = Path(__file__).resolve().parent / "data"
SOFC, MEAS = DATA / "sofc_tiny", DATA / "measeval_tiny"


def test_sofc_label_check(tmp_path: Path) -> None:
    assert sofc.label_check(SOFC)["complete"] is True
    qs = sofc.questions(SOFC)
    assert [q.question for q in qs] == ["Which material gives the highest conductivity?"]   # p3 has no open text
    assert qs[0].gold["ranking"] == ["GDC", "YSZ", "LSM"] and qs[0].records and not sofc.LAYOUT_VERIFIED and qs[0].field == "materials" and qs[0].kind == "rank"
    assert score(Answer(ranking=["GDC", "YSZ", "LSM"]), qs[0])["top1"] == 1
    assert sofc.left_out(SOFC) == "left out: 1 of 3 (no open full text)"
    shutil.copytree(SOFC, tmp_path / "d")
    path = tmp_path / "d" / sofc.SOURCE_FILE
    data = json.loads(path.read_text())
    data["papers"][0]["values"][0]["material"] = None
    path.write_text(json.dumps(data))
    check = sofc.label_check(tmp_path / "d")
    assert check["complete"] is False and "experiment-frame" in check["why"]
    assert sofc.questions(tmp_path / "d") == []


def test_experiment_frames_score() -> None:
    assert sofc.experiment_frames(SOFC)["p1"][0]["slots"]["material"] == "YSZ"
    exp = lambda doc, label, **setting: {"document": doc, "label": label, "setting": setting}   # noqa: E731
    run = SimpleNamespace(experiments=[exp("p1", "YSZ run", material="YSZ", device="Button cell"),
                                       exp("p2", "other", material="LSM"), exp("p2", "extra", material="NiO")])
    s = sofc.score_experiments(run, SOFC)
    assert s["frames"] == 3 and s["recall"] == 2 / 3 and s["precision"] == 2 / 3
    assert s["count_agreement"] == 0.0       # p1 has 1 of 2, p2 has 2 of 1
    assert sofc.score_experiments([], SOFC)["recall"] == 0.0


def test_measeval_units() -> None:
    assert measeval.qudt("mg/L") == measeval.QUDT_BASE + "MilliGM-PER-L" and measeval.qudt("furlong") is None
    assert measeval.same_unit("milligram", "mg") and not measeval.same_unit("mg", "g") and measeval.same_unit(None, "")
    run = [{"document": "m1", "value": 5.0, "unit": "mg/l", "entity": "Lead"},
           {"document": "m1", "value": 300, "unit": "degC", "entity": "sample"}]
    s = measeval.values_check(run, MEAS)
    assert s == {"layout_verified": False, "subset": "as given", "excluded_quantities": 0, "quantities": 2,
                 "values_found": 1.0, "unit_correct": 0.5, "entity_correct": 1.0}
    assert measeval.values_check([], MEAS)["values_found"] == 0.0
    assert measeval.fields(MEAS) == {"layout_verified": False, "fields": [], "status": "unverified"}


def test_sofc_lower_is_better_and_units(tmp_path: Path) -> None:
    shutil.copytree(SOFC, tmp_path / "d")
    path = tmp_path / "d" / sofc.SOURCE_FILE
    data = json.loads(path.read_text())
    for p in data["papers"][:2]:
        for v in p["values"]:
            v["measure"] = "area specific resistance"
    data["papers"][0]["values"][1]["unit"] = "mS/cm"      # a second unit: its own question, one material only
    path.write_text(json.dumps(data))
    qs = sofc.questions(tmp_path / "d")
    assert len(qs) == 1 and qs[0].question.startswith("Which material gives the lowest area specific resistance")
    assert qs[0].gold["ranking"] == ["LSM", "YSZ"] and qs[0].gold["higher_is_better"] is False


def test_experiment_match_needs_whole_tokens() -> None:
    run = [{"document": "p2", "label": "", "setting": {"material": "LS"}}]   # "ls" is not the token "lsm"
    assert sofc.score_experiments(run, SOFC)["recall"] == 0.0
