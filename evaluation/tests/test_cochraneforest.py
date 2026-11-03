"""CochraneForest: the fixture (hand-made, in the layout assumed in the module) has 1 plot and 3 studies, one with
no open full text."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from evaluation.realpapers import cochraneforest as cf
from evaluation.wholerun import Answer, score

TINY = Path(__file__).resolve().parent / "data" / "cochrane_tiny"


def test_question_and_gold(tmp_path: Path) -> None:
    assert cf.check_release(TINY) == {"licence": "CC-BY-4.0", "released": True}
    compare, claims = cf.questions(TINY)
    assert compare.kind == "compare" and claims.kind == "claims" and compare.field == "medicine"
    assert compare.question == "Does drug X reduce mortality compared with placebo?"
    assert compare.gold["directions"] == {"s1": "improves", "s2": "no_effect"}   # s3 has no open text
    assert compare.gold["conclusion"] == "improves"
    s = score(Answer(directions={"s1": "improves", "s2": "no_effect"}, conclusion="improves"), compare)
    assert s["direction_agreement"] == 1.0
    c = score(Answer(claims=[{"about": "r1", "direction": "improves"}]), claims)
    assert c["precision"] == 1.0 and c["recall"] == 1.0
    out = cf.to_corpus(TINY, tmp_path / "c")
    manifest = json.loads((out / "r1" / "manifest.json").read_text())
    assert [p["id"] for p in manifest["papers"]] == ["s1", "s2"]
    assert json.loads((out / cf.SOURCE_FILE).read_text())["left_out_line"] == "left out: 1 of 3 (no open full text)"


@pytest.mark.parametrize("change", [{"released": False}, {"licence": "all rights reserved"}])
def test_refuses_unreleased(tmp_path: Path, change: dict) -> None:
    shutil.copytree(TINY, tmp_path / "d")
    path = tmp_path / "d" / cf.RELEASE_FILE
    path.write_text(json.dumps(json.loads(path.read_text()) | change))
    with pytest.raises(cf.NotReleased):
        cf.to_corpus(tmp_path / "d", tmp_path / "out")
    assert not (tmp_path / "out").exists()
